# atlas/orchestrator/graph.py — LangGraph State Machine
#
# TOPOLOGY:
#   START → extract_intent → check_hitl → [hitl_wait] → route_task → call_agent → synthesize → END
#
# KEY CONCEPTS:
#   StateGraph + compile() = locked, runnable graph
#   checkpointer = saves state to PostgreSQL/memory after each node (crash recovery + HITL)
#   interrupt_before = pause graph before a node (HITL)
#   partial() = bind dependencies (registry, a2a_client) to nodes

from functools import partial
from typing import Any

import structlog
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from atlas.orchestrator.nodes import (call_agent, check_hitl_required, extract_intent,
                                       hitl_wait, route_task, should_require_hitl, synthesize_response)
from atlas.orchestrator.state import ATLASState, initial_state
from atlas.core.models import generate_id

logger = structlog.get_logger(__name__)


def build_graph(registry=None, a2a_client=None) -> StateGraph:
    """Wire all nodes and edges. Returns uncompiled graph."""
    g = StateGraph(ATLASState)

    g.add_node("extract_intent", extract_intent)
    g.add_node("check_hitl_required", check_hitl_required)
    g.add_node("hitl_wait", hitl_wait)
    g.add_node("route_task", partial(route_task, registry=registry))
    g.add_node("call_agent", partial(call_agent, a2a_client=a2a_client))
    g.add_node("synthesize", synthesize_response)

    g.add_edge(START, "extract_intent")
    g.add_edge("extract_intent", "check_hitl_required")
    g.add_conditional_edges("check_hitl_required", should_require_hitl,
                            {"hitl_wait": "hitl_wait", "route_task": "route_task"})
    g.add_edge("hitl_wait", "route_task")
    g.add_edge("route_task", "call_agent")
    g.add_edge("call_agent", "synthesize")
    g.add_edge("synthesize", END)

    return g


def compile_graph_in_memory(registry=None, a2a_client=None):
    """Compile with MemorySaver. For dev/tests — no PostgreSQL needed."""
    g = build_graph(registry=registry, a2a_client=a2a_client)
    compiled = g.compile(checkpointer=MemorySaver(), interrupt_before=["hitl_wait"])
    logger.info("graph_compiled", mode="memory")
    return compiled


async def compile_graph_with_postgres(db_url: str, registry=None, a2a_client=None):
    """Compile with PostgreSQL checkpointer. For production — crash recovery."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    g = build_graph(registry=registry, a2a_client=a2a_client)
    async with AsyncPostgresSaver.from_conn_string(db_url) as cp:
        await cp.setup()
        compiled = g.compile(checkpointer=cp, interrupt_before=["hitl_wait"])
    logger.info("graph_compiled", mode="postgres")
    return compiled


class ATLASOrchestrator:
    """High-level wrapper. Used by the API layer."""

    def __init__(self, registry=None, a2a_client=None, use_memory: bool = True, db_url: str | None = None):
        self.registry = registry
        self.a2a_client = a2a_client
        self.use_memory = use_memory
        self.db_url = db_url
        self._graph = None

    async def initialize(self) -> None:
        if self.use_memory:
            self._graph = compile_graph_in_memory(registry=self.registry, a2a_client=self.a2a_client)
        else:
            self._graph = await compile_graph_with_postgres(self.db_url, self.registry, self.a2a_client)
        logger.info("orchestrator_ready", mode="memory" if self.use_memory else "postgres")

    async def run(self, task_id: str, message: str, session_id: str | None = None, metadata: dict | None = None) -> dict[str, Any]:
        if not self._graph: await self.initialize()
        sid = session_id or generate_id("session")
        state = initial_state(task_id, sid, HumanMessage(content=message), metadata)
        config = {"configurable": {"thread_id": f"{sid}:{task_id}"}}
        logger.info("run_start", task=task_id, msg=message[:50])
        result = await self._graph.ainvoke(state, config=config)
        logger.info("run_done", task=task_id, hitl=result.get("requires_hitl"))
        return result

    async def approve_hitl(self, task_id: str, session_id: str, decision: str, modified_input: str | None = None) -> dict[str, Any]:
        if not self._graph: raise RuntimeError("Not initialized")
        config = {"configurable": {"thread_id": f"{session_id}:{task_id}"}}
        await self._graph.aupdate_state(config, {
            "hitl_decision": decision, "hitl_modified_input": modified_input,
            "error": "Rejected by human" if decision == "reject" else None,
        })
        if decision == "reject": return {"status": "rejected", "task_id": task_id}
        return await self._graph.ainvoke(None, config=config)

    async def get_state(self, task_id: str, session_id: str) -> dict[str, Any]:
        if not self._graph: raise RuntimeError("Not initialized")
        snap = await self._graph.aget_state({"configurable": {"thread_id": f"{session_id}:{task_id}"}})
        if snap is None: raise ValueError(f"No state for task {task_id}")
        return dict(snap.values)