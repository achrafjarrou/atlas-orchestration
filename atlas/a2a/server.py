# atlas/a2a/server.py
# A2A Protocol Server — JSON-RPC 2.0 dispatcher
#
# ENDPOINTS:
#   POST /a2a                     → JSON-RPC dispatcher (tasks/send, tasks/get, tasks/cancel)
#   GET  /a2a/tasks/{id}/stream   → SSE real-time updates

import asyncio
import json
import time
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.a2a.protocol import (A2AMessage, A2ARequest, A2ATaskState, A2ATaskStatus, A2ATaskWithStatus)
from atlas.core.audit import AuditTrail
from atlas.core.config import settings
from atlas.core.models import generate_id

logger = structlog.get_logger(__name__)

# In-memory store (replace with Redis in production)
_task_store: dict[str, A2ATaskWithStatus] = {}

a2a_router = APIRouter(prefix="/a2a", tags=["A2A Protocol"])


@a2a_router.post("", summary="A2A JSON-RPC 2.0")
async def a2a_jsonrpc(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """JSON-RPC 2.0 dispatcher for all A2A methods."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _err("unknown", -32700, "Parse error")

    try:
        rpc = A2ARequest.model_validate(body)
    except Exception as e:
        return _err(body.get("id", "unknown"), -32600, f"Invalid request: {e}")

    handlers = {
        "tasks/send": _handle_send,
        "tasks/get": _handle_get,
        "tasks/cancel": _handle_cancel,
    }

    if rpc.method not in handlers:
        return _err(rpc.id, -32601, f"Method not found: {rpc.method}")

    try:
        result = await handlers[rpc.method](rpc.params, db)
        return JSONResponse({"jsonrpc": "2.0", "id": rpc.id, "result": result})
    except ValueError as e:
        return _err(rpc.id, -32602, str(e))
    except Exception as e:
        logger.error("a2a_error", method=rpc.method, error=str(e))
        return _err(rpc.id, -32603, "Internal error")


async def _handle_send(params: dict[str, Any], db: AsyncSession) -> dict:
    audit = AuditTrail(db)
    try:
        task = A2ATaskWithStatus(
            id=params.get("id", generate_id("task")),
            session_id=params.get("sessionId", generate_id("session")),
            message=A2AMessage.model_validate(params["message"]),
            metadata=params.get("metadata", {}),
            status=A2ATaskStatus(state=A2ATaskState.SUBMITTED),
        )
    except KeyError as e:
        raise ValueError(f"Missing field: {e}")

    _task_store[task.id] = task
    await audit.record(action="task_received", agent_id=settings.atlas_agent_id,
                       session_id=task.session_id, task_id=task.id,
                       intent=task.message.text[:200],
                       input_data={"message": task.message.model_dump()},
                       output_data={"task_id": task.id, "status": "submitted"})

    asyncio.create_task(_process_task(task.id))
    logger.info("task_received", id=task.id, msg=task.message.text[:50])
    return task.model_dump(exclude_none=True)


async def _handle_get(params: dict[str, Any], db: AsyncSession) -> dict:
    task_id = params.get("id") or (_ for _ in ()).throw(ValueError("Missing: id"))
    task = _task_store.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    return task.model_dump(exclude_none=True)


async def _handle_cancel(params: dict[str, Any], db: AsyncSession) -> dict:
    task_id = params.get("id")
    if not task_id:
        raise ValueError("Missing: id")
    task = _task_store.get(task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")
    if task.status.state not in {A2ATaskState.SUBMITTED, A2ATaskState.WORKING}:
        raise ValueError(f"Cannot cancel task in state: {task.status.state}")
    task.status = A2ATaskStatus(state=A2ATaskState.CANCELLED,
                                 message=A2AMessage.agent("Cancelled by request"))
    _task_store[task_id] = task
    return task.model_dump(exclude_none=True)


@a2a_router.get("/tasks/{task_id}/stream", summary="Stream task updates (SSE)")
async def stream_task(task_id: str) -> StreamingResponse:
    return StreamingResponse(_sse_generator(task_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


async def _sse_generator(task_id: str) -> AsyncGenerator[str, None]:
    terminal = {A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELLED}
    last_state = None
    for _ in range(120):
        task = _task_store.get(task_id)
        if not task:
            yield f"data: {json.dumps({'error': 'not found'})}\n\n"
            break
        if task.status.state != last_state:
            yield f"data: {json.dumps(task.model_dump(exclude_none=True), default=str)}\n\n"
            last_state = task.status.state
        if task.status.state in terminal:
            break
        await asyncio.sleep(0.5)
    yield "data: [DONE]\n\n"


async def _process_task(task_id: str) -> None:
    """Background processor — replace with orchestrator.run() in Day 3+"""
    task = _task_store.get(task_id)
    if not task:
        return
    task.status = A2ATaskStatus(state=A2ATaskState.WORKING, message=A2AMessage.agent("Processing..."))
    await asyncio.sleep(0.1)
    task.status = A2ATaskStatus(
        state=A2ATaskState.COMPLETED,
        message=A2AMessage.agent(f"Completed: {task.message.text[:100]}"))
    _task_store[task_id] = task


def _err(rpc_id: str, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})


async def get_db():
    raise NotImplementedError("Overridden in api/main.py")