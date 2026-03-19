# atlas/api/routes/agents.py
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from atlas.a2a.discovery import AgentRegistry
from atlas.core.models import AgentInfo

agents_router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])
def get_db(): raise NotImplementedError
def get_registry(): raise NotImplementedError

@agents_router.get("", response_model=list[AgentInfo], summary="List Agents")
async def list_agents(status: str = "active", db: AsyncSession = Depends(get_db), registry: AgentRegistry = Depends(get_registry)):
    registry.db = db
    if status == "all":
        return await registry.list_agents("active") + await registry.list_agents("inactive")
    return await registry.list_agents(status)

@agents_router.post("/register", response_model=AgentInfo, summary="Register Agent", status_code=201)
async def register_agent(url: str = Body(..., embed=True), db: AsyncSession = Depends(get_db), registry: AgentRegistry = Depends(get_registry)):
    registry.db = db
    try:
        return await registry.register_from_url(url)
    except ValueError as e:
        raise HTTPException(400, str(e))

@agents_router.get("/{agent_id}", response_model=AgentInfo, summary="Get Agent")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db), registry: AgentRegistry = Depends(get_registry)):
    registry.db = db
    agents = await registry.list_agents("active") + await registry.list_agents("inactive")
    agent = next((a for a in agents if a.agent_id == agent_id), None)
    if not agent: raise HTTPException(404, f"Agent not found: {agent_id}")
    return agent

@agents_router.post("/{agent_id}/health", summary="Health Check Agent")
async def check_health(agent_id: str, db: AsyncSession = Depends(get_db), registry: AgentRegistry = Depends(get_registry)):
    registry.db = db
    healthy = await registry.health_check(agent_id)
    return {"agent_id": agent_id, "healthy": healthy, "status": "active" if healthy else "inactive"}

@agents_router.post("/route", summary="Semantic Route Task")
async def route(intent: str = Body(..., embed=True), top_k: int = Body(3, embed=True),
                db: AsyncSession = Depends(get_db), registry: AgentRegistry = Depends(get_registry)):
    registry.db = db
    candidates = await registry.route(intent=intent, top_k=top_k)
    return {"intent": intent, "candidates": candidates, "best_agent": candidates[0] if candidates else None}