# atlas/orchestrator/state.py — LangGraph State TypedDict
# STATE = the "memory" flowing through the graph.
# Annotated[list, operator.add] = APPEND (not replace) when nodes update lists.

import operator
from typing import Annotated, Any, TypedDict
from langchain_core.messages import AnyMessage


class ATLASState(TypedDict):
    # Core
    task_id: str
    session_id: str
    intent: str
    # Messages — operator.add = accumulate across nodes (not replace)
    messages: Annotated[list[AnyMessage], operator.add]
    # Routing
    routed_to: str | None
    routing_score: float | None
    routing_candidates: list[dict[str, Any]]
    # Tools & Results
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    agent_results: Annotated[list[dict[str, Any]], operator.add]
    # Output
    final_response: str | None
    # HITL
    requires_hitl: bool
    hitl_reason: str | None
    hitl_decision: str | None
    hitl_modified_input: str | None
    # Error
    error: str | None
    retry_count: int
    metadata: dict[str, Any]


def initial_state(task_id: str, session_id: str, first_message: AnyMessage, metadata: dict | None = None) -> ATLASState:
    """Create a clean initial state for a new task."""
    return ATLASState(
        task_id=task_id, session_id=session_id, intent="",
        messages=[first_message], routed_to=None, routing_score=None,
        routing_candidates=[], tool_calls=[], agent_results=[],
        final_response=None, requires_hitl=False, hitl_reason=None,
        hitl_decision=None, hitl_modified_input=None,
        error=None, retry_count=0, metadata=metadata or {},
    )