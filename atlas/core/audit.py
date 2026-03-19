# atlas/core/audit.py
# SHA-256 Cryptographic Audit Trail — EU AI Act Article 9
#
# CHAIN STRUCTURE:
#   record_1: hash = SHA256("" + id + action + timestamp + data)
#   record_2: hash = SHA256(record_1.hash + id + action + timestamp + data)
#   → Modifying any record breaks all subsequent hashes (tamper-proof)

import hashlib
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.config import settings
from atlas.core.models import AuditRecord, AuditStatus, generate_id

logger = structlog.get_logger(__name__)


class AuditTrail:
    """SHA-256 chained audit log. One record per agent action."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        action: str,
        agent_id: str,
        session_id: str | None = None,
        task_id: str | None = None,
        intent: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> AuditRecord:
        """Create one tamper-proof audit record.

        Steps:
        1. Fetch previous record hash (the chain link)
        2. Compute this record hash = SHA256(prev_hash + payload)
        3. Persist to PostgreSQL
        4. Return the record
        """
        if not settings.enable_audit_trail:
            return AuditRecord(action=action, agent_id=agent_id, metadata={"audit_disabled": True})

        start = time.time()
        previous_hash = await self._get_latest_hash()
        record_id = generate_id("rec")
        now = datetime.now(timezone.utc)

        record_hash = self._compute_hash(
            previous_hash=previous_hash,
            record_id=record_id,
            action=action,
            agent_id=agent_id,
            timestamp=now.isoformat(),
            input_data=input_data or {},
            output_data=output_data or {},
        )

        record = AuditRecord(
            id=record_id,
            action=action,
            agent_id=agent_id,
            session_id=session_id,
            task_id=task_id,
            intent=intent,
            input_data=input_data or {},
            output_data=output_data or {},
            metadata=metadata or {},
            previous_hash=previous_hash,
            record_hash=record_hash,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            created_at=now,
        )

        await self._write_record(record)

        logger.info("audit_record", id=record_id, action=action, agent=agent_id,
                    hash=record_hash[:8], ms=int((time.time()-start)*1000))
        return record

    async def verify_chain(self, limit: int = 100) -> dict[str, Any]:
        """Re-compute all hashes. Returns valid=True if chain is intact."""
        q = text("SELECT id, action, agent_id, created_at, input_data, output_data, "
                 "previous_hash, record_hash FROM audit_records ORDER BY created_at ASC LIMIT :l")
        rows = (await self.db.execute(q, {"l": limit})).fetchall()

        if not rows:
            return {"valid": True, "records_checked": 0}

        broken_at = None
        prev_hash: str | None = None

        for row in rows:
            expected = self._compute_hash(
                previous_hash=prev_hash,
                record_id=row.id,
                action=row.action,
                agent_id=row.agent_id,
                timestamp=row.created_at.isoformat(),
                input_data=row.input_data or {},
                output_data=row.output_data or {},
            )
            if expected != row.record_hash:
                broken_at = row.id
                break
            prev_hash = row.record_hash

        return {
            "valid": broken_at is None,
            "records_checked": len(rows),
            "first_record_id": rows[0].id,
            "last_record_id": rows[-1].id,
            "broken_at": broken_at,
        }

    async def get_session_trail(self, session_id: str) -> list[AuditRecord]:
        q = text("SELECT * FROM audit_records WHERE session_id = :s ORDER BY created_at ASC")
        rows = (await self.db.execute(q, {"s": session_id})).fetchall()
        return [AuditRecord.model_validate(dict(r._mapping)) for r in rows]

    async def generate_compliance_report(self) -> dict[str, Any]:
        """EU AI Act Article 9 compliance report."""
        total = (await self.db.execute(text("SELECT COUNT(*) FROM audit_records"))).scalar()
        latest = (await self.db.execute(text("SELECT MAX(created_at) FROM audit_records"))).scalar()
        chain = await self.verify_chain(limit=1000)
        actions = {r.action: r.count for r in (await self.db.execute(
            text("SELECT action, COUNT(*) as count FROM audit_records GROUP BY action")
        )).fetchall()}

        return {
            "report_type": "EU_AI_Act_Article_9_Compliance",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system": "ATLAS Universal Multi-Agent Orchestration Platform v0.1.0",
            "article": "Article 9 — Risk Management System",
            "status": "COMPLIANT" if chain["valid"] else "NON_COMPLIANT",
            "evidence": {
                "audit_trail_active": settings.enable_audit_trail,
                "total_records": total,
                "chain_integrity": chain["valid"],
                "records_verified": chain["records_checked"],
                "hash_algorithm": "SHA-256",
                "chain_broken_at": chain.get("broken_at"),
                "last_record_at": latest.isoformat() if latest else None,
                "hitl_enabled": settings.enable_hitl,
                "actions_recorded": actions,
            },
        }

    @staticmethod
    def _compute_hash(previous_hash, record_id, action, agent_id, timestamp, input_data, output_data) -> str:
        """SHA-256(previous_hash + record_id + action + agent_id + timestamp + input + output)"""
        payload = {
            "previous_hash": previous_hash or "",
            "record_id": record_id,
            "action": action,
            "agent_id": agent_id,
            "timestamp": timestamp,
            "input_data": input_data,
            "output_data": output_data,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    async def _get_latest_hash(self) -> str | None:
        q = text("SELECT record_hash FROM audit_records ORDER BY created_at DESC LIMIT 1")
        row = (await self.db.execute(q)).fetchone()
        return row.record_hash if row else None

    async def _write_record(self, r: AuditRecord) -> None:
        await self.db.execute(text("""
            INSERT INTO audit_records (
                id, record_id, action, agent_id, session_id, task_id,
                intent, input_data, output_data, metadata,
                previous_hash, record_hash, status, error_message, duration_ms, created_at
            ) VALUES (
                :id, :id, :action, :agent_id, :session_id, :task_id,
                :intent, :input_data, :output_data, :metadata,
                :previous_hash, :record_hash, :status, :error_message, :duration_ms, :created_at
            )
        """), {
            "id": r.id, "action": r.action, "agent_id": r.agent_id,
            "session_id": r.session_id, "task_id": r.task_id, "intent": r.intent,
            "input_data": json.dumps(r.input_data), "output_data": json.dumps(r.output_data),
            "metadata": json.dumps(r.metadata), "previous_hash": r.previous_hash,
            "record_hash": r.record_hash, "status": r.status,
            "error_message": r.error_message, "duration_ms": r.duration_ms,
            "created_at": r.created_at,
        })
        await self.db.commit()


@asynccontextmanager
async def audit_context(audit, action, agent_id, session_id=None, task_id=None, intent=None, input_data=None):
    """Context manager: records success or failure automatically with timing."""
    start = time.time()
    ctx: dict[str, Any] = {"output": {}}
    try:
        yield ctx
        await audit.record(action=action, agent_id=agent_id, session_id=session_id,
                           task_id=task_id, intent=intent, input_data=input_data or {},
                           output_data=ctx.get("output", {}), status=AuditStatus.SUCCESS,
                           duration_ms=int((time.time()-start)*1000))
    except Exception as e:
        await audit.record(action=action, agent_id=agent_id, session_id=session_id,
                           task_id=task_id, intent=intent, input_data=input_data or {},
                           status=AuditStatus.FAILURE, error_message=str(e),
                           duration_ms=int((time.time()-start)*1000))
        raise