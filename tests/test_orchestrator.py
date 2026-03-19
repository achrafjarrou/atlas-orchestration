# tests/test_orchestrator.py — LangGraph Orchestrator Tests
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from atlas.orchestrator.nodes import check_hitl_required, extract_intent, should_require_hitl, synthesize_response
from atlas.orchestrator.state import initial_state

def mk_state(intent, tid, sid):
    s = initial_state(tid, sid, HumanMessage(content=intent))
    s["intent"] = intent
    return s

class TestState:
    def test_defaults(self, sample_task_id, sample_session_id):
        s = initial_state(sample_task_id, sample_session_id, HumanMessage(content="Hi"))
        assert s["requires_hitl"] is False and s["error"] is None and s["tool_calls"] == []

class TestExtractIntent:
    @pytest.mark.asyncio
    async def test_extracts(self, sample_task_id, sample_session_id):
        s = initial_state(sample_task_id, sample_session_id, HumanMessage(content="Analyze for GDPR"))
        u = await extract_intent(s)
        assert "GDPR" in u["intent"]

    @pytest.mark.asyncio
    async def test_truncates_long(self, sample_task_id, sample_session_id):
        s = initial_state(sample_task_id, sample_session_id, HumanMessage(content="A"*1000))
        u = await extract_intent(s)
        assert len(u["intent"]) <= 500

class TestHITL:
    @pytest.mark.asyncio
    async def test_no_hitl_safe(self, sample_task_id, sample_session_id):
        u = await check_hitl_required(mk_state("analyze document", sample_task_id, sample_session_id))
        assert u["requires_hitl"] is False

    @pytest.mark.asyncio
    async def test_hitl_payment(self, sample_task_id, sample_session_id):
        u = await check_hitl_required(mk_state("process payment", sample_task_id, sample_session_id))
        assert u["requires_hitl"] is True

    @pytest.mark.asyncio
    async def test_hitl_delete(self, sample_task_id, sample_session_id):
        u = await check_hitl_required(mk_state("delete all records", sample_task_id, sample_session_id))
        assert u["requires_hitl"] is True

    def test_routing_hitl(self, sample_task_id, sample_session_id):
        s = mk_state("t", sample_task_id, sample_session_id); s["requires_hitl"] = True
        assert should_require_hitl(s) == "hitl_wait"

    def test_routing_no_hitl(self, sample_task_id, sample_session_id):
        s = mk_state("t", sample_task_id, sample_session_id); s["requires_hitl"] = False
        assert should_require_hitl(s) == "route_task"

class TestGraph:
    def test_compiles(self):
        from atlas.orchestrator.graph import compile_graph_in_memory
        assert compile_graph_in_memory() is not None

    @pytest.mark.asyncio
    async def test_full_run(self, sample_task_id, sample_session_id):
        from atlas.orchestrator.graph import ATLASOrchestrator
        o = ATLASOrchestrator(use_memory=True)
        await o.initialize()
        r = await o.run(task_id=sample_task_id, message="summarize this", session_id=sample_session_id)
        assert r.get("final_response") is not None and r.get("requires_hitl") is False

    @pytest.mark.asyncio
    async def test_hitl_pauses(self, sample_task_id, sample_session_id):
        from atlas.orchestrator.graph import ATLASOrchestrator
        o = ATLASOrchestrator(use_memory=True)
        await o.initialize()
        r = await o.run(task_id=sample_task_id, message="delete all production records", session_id=sample_session_id)
        assert r.get("requires_hitl") is True