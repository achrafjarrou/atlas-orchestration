# tests/test_audit.py — SHA-256 Audit Trail Tests
import hashlib, json
import pytest
from atlas.core.audit import AuditTrail, audit_context
from atlas.core.models import AuditStatus

class TestRecording:
    @pytest.mark.asyncio
    async def test_creates_record(self, audit_trail, sample_session_id):
        r = await audit_trail.record(action="test", agent_id="agent-1", session_id=sample_session_id)
        assert r.id and r.action == "test" and r.status == AuditStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_hash_is_64_chars(self, audit_trail):
        r = await audit_trail.record(action="test", agent_id="agent-1")
        assert len(r.record_hash) == 64

    @pytest.mark.asyncio
    async def test_first_record_no_prev_hash(self, audit_trail):
        r = await audit_trail.record(action="first", agent_id="agent-1")
        assert r.previous_hash is None

    @pytest.mark.asyncio
    async def test_chain_links(self, audit_trail):
        r1 = await audit_trail.record(action="a1", agent_id="a")
        r2 = await audit_trail.record(action="a2", agent_id="a")
        assert r2.previous_hash == r1.record_hash

    @pytest.mark.asyncio
    async def test_different_data_different_hash(self, audit_trail):
        r1 = await audit_trail.record(action="a", agent_id="ag1", input_data={"x": 1})
        r2 = await audit_trail.record(action="b", agent_id="ag2", input_data={"x": 2})
        assert r1.record_hash != r2.record_hash

class TestChain:
    @pytest.mark.asyncio
    async def test_empty_chain_valid(self, audit_trail):
        r = await audit_trail.verify_chain()
        assert r["valid"] is True and r["records_checked"] == 0

    @pytest.mark.asyncio
    async def test_valid_chain(self, audit_trail):
        for i in range(5): await audit_trail.record(action=f"act{i}", agent_id="ag")
        r = await audit_trail.verify_chain(limit=10)
        assert r["valid"] is True and r["records_checked"] == 5

class TestContext:
    @pytest.mark.asyncio
    async def test_records_failure(self, audit_trail):
        with pytest.raises(ValueError, match="test error"):
            async with audit_context(audit_trail, "op", "ag") as ctx:
                raise ValueError("test error")

class TestCompliance:
    @pytest.mark.asyncio
    async def test_report_generated(self, audit_trail):
        r = await audit_trail.generate_compliance_report()
        assert r["status"] == "COMPLIANT"
        assert "evidence" in r