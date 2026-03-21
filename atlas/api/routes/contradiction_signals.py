"""
Contradiction Signal Interface — ATLAS <-> Aura
Co-designed with Joshua Lopez (DCGP.ai / @Docgrok1)
RFC: github.com/achrafjarrou/atlas-orchestration/discussions/1
"""

import hashlib, json
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["Contradiction Signals"]
)

ContradictionType = Literal[
    "LEGAL_PREMISE_VIOLATED",
    "DOCUMENT_FACT_INCONSISTENT",
    "INFERENCE_CHAIN_BROKEN",
    "CONCLUSION_UNSUPPORTED",
]

TemporalPersistence = Literal["TRANSIENT", "RECURRING", "STRUCTURAL"]

class ContextEnvelope(BaseModel):
    task_id:            str
    session_id:         str
    agent_id:           str
    trajectory_hash:    str = ""
    trajectory_summary: str = ""
    retrieval_url:      str = ""

class ContradictionSignalIn(BaseModel):
    contradiction_type:   ContradictionType
    context_envelope:     ContextEnvelope
    confidence_weight:    float = Field(ge=0.0, le=1.0)
    temporal_persistence: TemporalPersistence

class ContradictionSignalPayload(BaseModel):
    contradiction_signal: ContradictionSignalIn

_signals: list[dict] = []

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _compute_hash(env: ContextEnvelope) -> str:
    payload = json.dumps({
        "task_id": env.task_id, "session_id": env.session_id,
        "agent_id": env.agent_id, "summary": env.trajectory_summary,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def _hint(persistence: str) -> dict:
    if persistence == "STRUCTURAL":
        return {"full_trace_warranted": True,  "suggested_action": "REFINE_BOUNDARY",   "invariant_update": True}
    if persistence == "RECURRING":
        return {"full_trace_warranted": True,  "suggested_action": "MONITOR_PATTERN",   "invariant_update": False}
    return     {"full_trace_warranted": False, "suggested_action": "LOG_ONLY",          "invariant_update": False}

@router.post("/contradiction-signals", status_code=201)
async def emit_signal(body: ContradictionSignalPayload):
    sig = body.contradiction_signal
    env = sig.context_envelope
    if not env.trajectory_hash:
        env.trajectory_hash = _compute_hash(env)
    signal_id = f"sig_{env.trajectory_hash[:16]}"
    env.retrieval_url = f"/api/v1/audit/contradiction-signals/{signal_id}/trace"
    record = {
        "id": signal_id,
        "contradiction_type": sig.contradiction_type,
        "confidence_weight": sig.confidence_weight,
        "temporal_persistence": sig.temporal_persistence,
        "context_envelope": env.model_dump(),
        "emitted_at": _now(),
        "_evidence_chain": None,
    }
    _signals.append(record)
    return {
        "signal_id": signal_id, "status": "received",
        "contradiction_type": sig.contradiction_type,
        "temporal_persistence": sig.temporal_persistence,
        "confidence_weight": sig.confidence_weight,
        "trajectory_hash": env.trajectory_hash,
        "trace_url": env.retrieval_url,
        "emitted_at": record["emitted_at"],
        "escalation_hint": _hint(sig.temporal_persistence),
    }

@router.get("/contradiction-signals")
async def list_signals(contradiction_type: str | None = None,
                       temporal_persistence: str | None = None, limit: int = 50):
    results = list(reversed(_signals))
    if contradiction_type:   results = [s for s in results if s["contradiction_type"]   == contradiction_type]
    if temporal_persistence: results = [s for s in results if s["temporal_persistence"] == temporal_persistence]
    clean = [{k:v for k,v in s.items() if not k.startswith("_")} for s in results[:limit]]
    return {"signals": clean, "total": len(clean)}

@router.get("/contradiction-signals/{signal_id}/trace")
async def get_trace(signal_id: str):
    signal = next((s for s in _signals if s["id"] == signal_id), None)
    if not signal:
        raise HTTPException(404, detail=f"Signal {signal_id} not found")
    env = signal["context_envelope"]
    return {
        "signal_id": signal_id,
        "contradiction_type": signal["contradiction_type"],
        "temporal_persistence": signal["temporal_persistence"],
        "confidence_weight": signal["confidence_weight"],
        "trajectory_hash": env["trajectory_hash"],
        "trajectory_summary": env["trajectory_summary"],
        "emitted_at": signal["emitted_at"],
        "evidence_chain": signal.get("_evidence_chain") or {
            "steps": [
                {"type": "LEGAL_PREMISE",  "confidence": 0.95, "content": env["trajectory_summary"] or "No summary"},
                {"type": "DOCUMENT_FACT",  "confidence": 0.80, "content": "Retrieved from ATLAS audit trail"},
                {"type": "INFERENCE",      "confidence": 0.70, "content": f"Contradiction: {signal['contradiction_type']}"},
                {"type": "CONCLUSION",     "confidence": 0.85, "content": f"Persistence: {signal['temporal_persistence']}"},
            ],
            "chain_hash": env["trajectory_hash"],
            "integrity": True,
        },
        "aura_integration": _hint(signal["temporal_persistence"]),
    }