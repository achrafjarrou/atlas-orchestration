# atlas/a2a/discovery.py
# Agent Registry + Semantic Routing
#
# REGISTRY: Stores all known A2A agents
#   - PostgreSQL: metadata (name, URL, status, health)
#   - Qdrant: capability embeddings (for semantic routing)
#
# ROUTING: Given a task intent → find best agent
#   - Embed the intent (sentence-transformers, local, free)
#   - Cosine similarity search in Qdrant
#   - Return top-K agents ranked by relevance

import asyncio
import json
import time
import uuid
from urllib.parse import urlparse
from typing import Any

import httpx
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.a2a.protocol import A2AAgentCard
from atlas.core.config import settings
from atlas.core.models import AgentCapability, AgentInfo, AgentStatus

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """Central registry of all A2A agents known to ATLAS.
    
    PostgreSQL stores metadata. Qdrant stores embeddings for semantic routing.
    Both stores are always in sync.
    """

    def __init__(self, db: AsyncSession, qdrant: AsyncQdrantClient, embedder: SentenceTransformer) -> None:
        self.db = db
        self.qdrant = qdrant
        self.embedder = embedder
        self._collection = settings.qdrant_collection_agents

    async def initialize(self) -> None:
        """Create Qdrant collection for agent embeddings (idempotent)."""
        collections = await self.qdrant.get_collections()
        names = [c.name for c in collections.collections]
        if self._collection not in names:
            await self.qdrant.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=settings.embedding_dimension, distance=Distance.COSINE),
            )
            logger.info("qdrant_collection_created", collection=self._collection)

    async def register(self, agent_card: A2AAgentCard) -> AgentInfo:
        """Register an agent. Embeds capabilities → Qdrant + PostgreSQL."""
        capability_text = self._build_capability_text(agent_card)
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.embedder.encode(capability_text).tolist()
        )
        agent_id = self._derive_agent_id(agent_card)

        # Write to Qdrant
        await self.qdrant.upsert(
            collection_name=self._collection,
            points=[PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, agent_card.url)),
                vector=embedding,
                payload={
                    "agent_id": agent_id, "name": agent_card.name,
                    "url": agent_card.url, "description": agent_card.description,
                    "capability_text": capability_text,
                },
            )],
        )

        # Write to PostgreSQL
        await self.db.execute(text("""
            INSERT INTO agent_registry (agent_id, name, base_url, capabilities, skills, version, provider, status)
            VALUES (:agent_id, :name, :base_url, :capabilities, :skills, :version, :provider, 'active')
            ON CONFLICT (agent_id) DO UPDATE SET
                name = EXCLUDED.name, base_url = EXCLUDED.base_url,
                capabilities = EXCLUDED.capabilities, skills = EXCLUDED.skills,
                updated_at = NOW(), status = 'active'
        """), {
            "agent_id": agent_id, "name": agent_card.name, "base_url": agent_card.url,
            "capabilities": json.dumps([{"id": s.id, "name": s.name, "description": s.description} for s in agent_card.skills]),
            "skills": json.dumps([s.model_dump() for s in agent_card.skills]),
            "version": agent_card.version,
            "provider": json.dumps(agent_card.provider.model_dump() if agent_card.provider else {}),
        })
        await self.db.commit()

        logger.info("agent_registered", agent_id=agent_id, name=agent_card.name, skills=len(agent_card.skills))
        return AgentInfo(
            agent_id=agent_id, name=agent_card.name, base_url=agent_card.url,
            capabilities=[AgentCapability(id=s.id, name=s.name, description=s.description) for s in agent_card.skills],
            version=agent_card.version, status=AgentStatus.ACTIVE,
        )

    async def register_from_url(self, agent_url: str) -> AgentInfo:
        """Register agent by fetching its Agent Card from {url}/.well-known/agent.json"""
        card_url = f"{agent_url.rstrip('/')}/.well-known/agent.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.get(card_url)
                r.raise_for_status()
                card = A2AAgentCard.model_validate(r.json())
            except Exception as e:
                raise ValueError(f"Failed to fetch agent card from {card_url}: {e}")
        return await self.register(card)

    async def route(self, intent: str, top_k: int = 3, min_score: float = 0.3) -> list[dict[str, Any]]:
        """Find best agents for a task using semantic similarity.
        
        1. Embed intent → 384-dim vector (local, free)
        2. Cosine similarity search in Qdrant
        3. Return top-K agents sorted by relevance score
        """
        query_vector = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.embedder.encode(intent).tolist()
        )
        hits = await self.qdrant.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=min_score,
            with_payload=True,
        )
        results = [{"agent_id": h.payload["agent_id"], "name": h.payload["name"],
                    "url": h.payload["url"], "score": round(h.score, 4),
                    "description": h.payload.get("description", "")} for h in hits]
        if results:
            logger.info("routing_done", intent=intent[:50], best=results[0]["name"], score=results[0]["score"])
        return results

    async def list_agents(self, status: str = "active") -> list[AgentInfo]:
        rows = (await self.db.execute(
            text("SELECT agent_id, name, base_url, capabilities, skills, version, status, health_score, last_heartbeat "
                 "FROM agent_registry WHERE status = :s ORDER BY name ASC"), {"s": status}
        )).fetchall()
        return [AgentInfo(
            agent_id=r.agent_id, name=r.name, base_url=r.base_url,
            capabilities=[AgentCapability(**c) for c in (r.capabilities or [])],
            version=r.version, status=AgentStatus(r.status), health_score=r.health_score or 1.0,
            last_heartbeat=r.last_heartbeat,
        ) for r in rows]

    async def health_check(self, agent_id: str) -> bool:
        row = (await self.db.execute(text("SELECT base_url FROM agent_registry WHERE agent_id = :id"), {"id": agent_id})).fetchone()
        if not row:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{row.base_url.rstrip('/')}/health")
                healthy = r.status_code == 200
        except Exception:
            healthy = False
        await self.db.execute(text("UPDATE agent_registry SET status = :s, last_heartbeat = NOW(), health_score = :h WHERE agent_id = :id"),
                              {"id": agent_id, "s": "active" if healthy else "inactive", "h": 1.0 if healthy else 0.0})
        await self.db.commit()
        return healthy

    @staticmethod
    def _build_capability_text(card: A2AAgentCard) -> str:
        """Rich text for embedding. More info = better routing."""
        parts = [f"Agent: {card.name}.", f"Description: {card.description}."]
        if card.skills:
            parts.append("Skills: " + ". ".join(f"{s.name}: {s.description}" for s in card.skills) + ".")
        return " ".join(parts)

    @staticmethod
    def _derive_agent_id(card: A2AAgentCard) -> str:
        hostname = urlparse(card.url).hostname or "unknown"
        return f"{card.name.lower().replace(' ', '-')[:30]}-{hostname}"