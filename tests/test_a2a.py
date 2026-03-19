# tests/test_a2a.py — A2A Protocol Tests
import pytest
from unittest.mock import MagicMock
from atlas.a2a.agent_card import build_atlas_agent_card
from atlas.a2a.protocol import A2AAgentCard, A2AMessage, A2AMessageRole, A2ARequest, A2ATask, A2ATaskState, A2ATaskWithStatus, TextPart, DataPart

class TestAgentCard:
    def test_atlas_card_valid(self):
        c = build_atlas_agent_card()
        assert c.name == "ATLAS Orchestrator" and len(c.skills) >= 4

    def test_serializes_to_dict(self):
        d = build_atlas_agent_card().model_dump(exclude_none=True)
        assert {"name", "url", "skills"}.issubset(d)

    def test_all_skills_have_descriptions(self):
        for s in build_atlas_agent_card().skills:
            assert len(s.description) > 20

class TestMessage:
    def test_user_convenience(self):
        m = A2AMessage.user("Hello")
        assert m.role == A2AMessageRole.USER and m.text == "Hello"

    def test_agent_convenience(self):
        assert A2AMessage.agent("Done").role == A2AMessageRole.AGENT

    def test_text_extracts_all_parts(self):
        m = A2AMessage(role=A2AMessageRole.USER, parts=[TextPart(text="A"), DataPart(data={}), TextPart(text="B")])
        assert "A" in m.text and "B" in m.text

class TestTask:
    def test_auto_ids(self):
        t1, t2 = A2ATask(message=A2AMessage.user("T1")), A2ATask(message=A2AMessage.user("T2"))
        assert t1.id != t2.id and t1.id.startswith("task_")

    def test_default_submitted_state(self):
        assert A2ATaskWithStatus(message=A2AMessage.user("Hi")).status.state == A2ATaskState.SUBMITTED

class TestRegistry:
    @pytest.mark.asyncio
    async def test_register_agent(self, mock_registry, sample_agent_card):
        info = await mock_registry.register(sample_agent_card)
        assert info.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_route_empty(self, mock_registry):
        assert await mock_registry.route("analyze legal docs") == []

    @pytest.mark.asyncio
    async def test_route_with_results(self, mock_registry, mock_qdrant):
        hit = MagicMock(); hit.score = 0.9
        hit.payload = {"agent_id": "ag1", "name": "Agent1", "url": "http://a:8001", "description": "test"}
        mock_qdrant.search.return_value = [hit]
        r = await mock_registry.route("compliance check")
        assert r[0]["agent_id"] == "ag1" and r[0]["score"] == 0.9