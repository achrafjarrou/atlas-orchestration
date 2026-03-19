# atlas/api/routes/tasks.py
import asyncio
import json
from typing import AsyncGenerator
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from atlas.core.models import generate_id
from atlas.orchestrator.graph import ATLASOrchestrator

logger = structlog.get_logger(__name__)
tasks_router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])
def get_orchestrator(): raise NotImplementedError

_results: dict[str, dict] = {}

@tasks_router.post("", status_code=202, summary="Submit Task")
async def submit(message: str = Body(..., embed=True), session_id: str | None = Body(None, embed=True),
                 metadata: dict | None = Body(None, embed=True), orch: ATLASOrchestrator = Depends(get_orchestrator)):
    task_id = generate_id("task")
    sid = session_id or generate_id("session")
    async def run():
        try:
            r = await orch.run(task_id=task_id, message=message, session_id=sid, metadata=metadata or {})
            _results[task_id] = {"task_id": task_id, "session_id": sid,
                "status": "hitl_pending" if r.get("requires_hitl") else "completed",
                "result": r.get("final_response"), "requires_hitl": r.get("requires_hitl", False),
                "hitl_reason": r.get("hitl_reason"), "routing": {"agent": r.get("routed_to"), "score": r.get("routing_score")}}
        except Exception as e:
            _results[task_id] = {"task_id": task_id, "session_id": sid, "status": "failed", "error": str(e)}
    asyncio.create_task(run())
    return {"task_id": task_id, "session_id": sid, "status": "submitted",
            "stream_url": f"/api/v1/tasks/{task_id}/stream"}

@tasks_router.get("/{task_id}", summary="Get Task")
async def get_task(task_id: str):
    return _results.get(task_id, {"task_id": task_id, "status": "working", "result": None})

@tasks_router.post("/{task_id}/hitl", summary="HITL Decision")
async def hitl(task_id: str, decision: str = Body(..., embed=True),
               modified_input: str | None = Body(None, embed=True), orch: ATLASOrchestrator = Depends(get_orchestrator)):
    data = _results.get(task_id)
    if not data: raise HTTPException(404, f"Task not found: {task_id}")
    if data.get("status") != "hitl_pending": raise HTTPException(400, f"Task not pending HITL")
    if decision not in ("approve", "reject"): raise HTTPException(400, "decision must be approve|reject")
    result = await orch.approve_hitl(task_id=task_id, session_id=data.get("session_id",""), decision=decision, modified_input=modified_input)
    _results[task_id]["status"] = "failed" if decision == "reject" else "completed"
    _results[task_id]["result"] = None if decision == "reject" else result.get("final_response")
    return {"task_id": task_id, "decision": decision, "status": _results[task_id]["status"]}

@tasks_router.get("/{task_id}/stream", summary="SSE Task Stream")
async def stream(task_id: str):
    async def gen() -> AsyncGenerator[str, None]:
        terminal = {"completed", "failed", "cancelled"}
        last = None
        for _ in range(120):
            data = _results.get(task_id, {"task_id": task_id, "status": "working"})
            if data.get("status") != last:
                yield f"data: {json.dumps(data, default=str)}\n\n"
                last = data.get("status")
            if data.get("status") in terminal: break
            await asyncio.sleep(0.5)
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})