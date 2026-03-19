# atlas/orchestrator/nodes.py — LangGraph Node Implementations
# RULE: each node takes state → returns PARTIAL state update (only changed fields)
#
# GRAPH FLOW:
#   START → extract_intent → check_hitl → [hitl_wait] → route_task → call_agent → synthesize → END

import time
from functools import partial
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from atlas.core.config import settings
from atlas.orchestrator.state import ATLASState

logger = structlog.get_logger(__name__)


async def extract_intent(state: ATLASState) -> dict[str, Any]:
    """Node 1: Extract user intent from first message for semantic routing."""
    user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if not user_msgs:
        return {"intent": "unknown", "error": "No user message"}
    intent = user_msgs[0].content[:500]  # cap for embedding
    logger.info("intent_extracted", task=state["task_id"], preview=intent[:50])
    return {"intent": intent}


async def check_hitl_required(state: ATLASState) -> dict[str, Any]:
    """Node 2: Detect if human approval needed before proceeding.
    Triggers: payment, delete, production, send email, deploy
    """
    intent = state["intent"].lower()
    triggers = [
        ("payment", "Financial operation requires human approval"),
        ("delete", "Deletion requires human approval"),
        ("production", "Production system modification requires human approval"),
        ("send email", "Email sending requires human approval"),
        ("deploy", "Deployment requires human approval"),
    ]
    if settings.enable_hitl:
        for kw, reason in triggers:
            if kw in intent:
                logger.info("hitl_triggered", task=state["task_id"], reason=reason)
                return {"requires_hitl": True, "hitl_reason": reason}
    return {"requires_hitl": False, "hitl_reason": None}


async def hitl_wait(state: ATLASState) -> dict[str, Any]:
    """Node 3: HITL pause point. Graph pauses here via interrupt_before.
    Human approves/rejects via POST /api/v1/tasks/{id}/hitl
    """
    logger.info("hitl_waiting", task=state["task_id"], reason=state.get("hitl_reason"))
    return {"messages": [AIMessage(content=f"⏸️ Waiting for approval: {state.get('hitl_reason')}")]}


async def route_task(state: ATLASState, registry=None) -> dict[str, Any]:
    """Node 4: Semantic routing — find best agent for this intent."""
    if registry is None:
        return {"routed_to": settings.atlas_agent_id, "routing_score": 1.0, "routing_candidates": []}

    start = time.time()
    candidates = await registry.route(state["intent"], top_k=3, min_score=0.3)
    ms = int((time.time()-start)*1000)

    if not candidates:
        return {"routed_to": settings.atlas_agent_id, "routing_score": 0.0, "routing_candidates": [],
                "messages": [AIMessage(content="No specialized agent found. Processing directly.")]}

    best = candidates[0]
    logger.info("routed", task=state["task_id"], to=best["agent_id"], score=best["score"], ms=ms)
    return {"routed_to": best["agent_id"], "routing_score": best["score"],
            "routing_candidates": candidates,
            "messages": [AIMessage(content=f"→ {best['name']} (confidence: {best['score']:.0%})")]}


async def call_agent(state: ATLASState, a2a_client=None) -> dict[str, Any]:
    """Node 5: Send task to selected agent via A2A JSON-RPC."""
    if not a2a_client or not state.get("routed_to"):
        return {"agent_results": [], "messages": [AIMessage(content="No agent available")]}

    if state["routed_to"] == settings.atlas_agent_id:
        return {"agent_results": [{"agent": "self", "result": "Direct processing"}]}

    candidates = state.get("routing_candidates", [])
    agent_url = next((c["url"] for c in candidates if c["agent_id"] == state["routed_to"]), None)
    if not agent_url:
        return {"error": f"No URL for agent {state['routed_to']}", "agent_results": []}

    try:
        r = await a2a_client.post(f"{agent_url}/a2a", json={
            "jsonrpc": "2.0", "id": f"rpc-{state['task_id']}", "method": "tasks/send",
            "params": {"id": state["task_id"], "sessionId": state["session_id"],
                       "message": {"role": "user", "parts": [{"type": "text", "text": state["intent"]}]}}
        }, timeout=30.0)
        r.raise_for_status()
        result = r.json().get("result", {})
        return {"agent_results": [{"agent": state["routed_to"], "result": result}],
                "messages": [AIMessage(content=f"Agent {state['routed_to']} completed")]}
    except Exception as e:
        return {"error": f"Agent call failed: {e}", "messages": [AIMessage(content=f"Failed: {e}")]}


async def synthesize_response(state: ATLASState) -> dict[str, Any]:
    """Node 6: Format the final response from all agent results."""
    if state.get("error"):
        msg = f"Error: {state['error']}"
        return {"final_response": msg, "messages": [AIMessage(content=msg)]}

    results = state.get("agent_results", [])
    if not results:
        msg = "Task processed directly by ATLAS."
        return {"final_response": msg, "messages": [AIMessage(content=msg)]}

    parts = []
    for ar in results:
        agent_id = ar.get("agent", "unknown")
        result = ar.get("result", {})
        text = str(result.get("status", {}).get("message", result)) if isinstance(result, dict) else str(result)
        parts.append(f"[{agent_id}]: {text}")

    response = "\n\n".join(parts)
    return {"final_response": response, "messages": [AIMessage(content=response)]}


# Conditional edge functions
def should_require_hitl(state: ATLASState) -> str:
    return "hitl_wait" if state.get("requires_hitl") else "route_task"