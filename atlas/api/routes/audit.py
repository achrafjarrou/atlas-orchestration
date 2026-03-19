# atlas/api/routes/audit.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from atlas.core.audit import AuditTrail

audit_router = APIRouter(prefix="/api/v1/audit", tags=["Audit Trail"])
def get_db(): raise NotImplementedError

@audit_router.get("/records", summary="List Audit Records")
async def list_records(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       agent_id: str | None = None, db: AsyncSession = Depends(get_db)):
    offset = (page-1)*page_size
    conds, params = ["1=1"], {"limit": page_size, "offset": offset}
    if agent_id: conds.append("agent_id = :agent_id"); params["agent_id"] = agent_id
    where = " AND ".join(conds)
    rows = (await db.execute(text(f"SELECT * FROM audit_records WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"), params)).fetchall()
    total = (await db.execute(text(f"SELECT COUNT(*) FROM audit_records WHERE {where}"), {k:v for k,v in params.items() if k not in ("limit","offset")})).scalar()
    return {"records": [dict(r._mapping) for r in rows], "total": total, "page": page, "has_more": offset+page_size < total}

@audit_router.get("/sessions/{session_id}", summary="Session Trail")
async def session_trail(session_id: str, db: AsyncSession = Depends(get_db)):
    audit = AuditTrail(db)
    records = await audit.get_session_trail(session_id)
    return {"session_id": session_id, "records": [r.model_dump() for r in records], "total": len(records)}

@audit_router.get("/verify", summary="Verify Chain Integrity")
async def verify(limit: int = Query(1000), db: AsyncSession = Depends(get_db)):
    r = await AuditTrail(db).verify_chain(limit=limit)
    return {"valid": r["valid"], "status": "VALID" if r["valid"] else "BROKEN",
            "records_verified": r["records_checked"], "broken_at": r.get("broken_at"), "algorithm": "SHA-256"}

@audit_router.get("/compliance", summary="EU AI Act Article 9 Report")
async def compliance(db: AsyncSession = Depends(get_db)):
    return await AuditTrail(db).generate_compliance_report()