# atlas/rag/store.py
# Qdrant vector store for RAG knowledge base
# Stores document chunks as embeddings for retrieval

import asyncio
import uuid
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from atlas.core.config import settings

logger = structlog.get_logger(__name__)


class KnowledgeStore:
    """
    Vector store for RAG knowledge base.

    Stores document chunks as embeddings.
    Used by the RAG pipeline to retrieve relevant context.

    Different from the agent registry:
    - agent_registry: stores agent CAPABILITIES (for routing)
    - knowledge_store: stores DOCUMENT CHUNKS (for RAG retrieval)
    """

    def __init__(self, qdrant: AsyncQdrantClient, embedder: SentenceTransformer) -> None:
        self.qdrant   = qdrant
        self.embedder = embedder
        self.collection = settings.qdrant_collection_knowledge

    async def initialize(self) -> None:
        """Create collection if it does not exist."""
        cols = await self.qdrant.get_collections()
        if self.collection not in [c.name for c in cols.collections]:
            await self.qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("knowledge_collection_created", collection=self.collection)

    async def add_documents(self, documents: list[dict[str, Any]]) -> int:
        """
        Add documents to the knowledge base.

        Each document: {"text": "...", "source": "...", "metadata": {...}}
        Returns number of chunks added.
        """
        if not documents:
            return 0

        texts = [d["text"] for d in documents]

        # Embed all texts (run in thread pool — encode() is sync)
        embeddings = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.embedder.encode(texts, batch_size=32).tolist()
        )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "text":     doc["text"],
                    "source":   doc.get("source", "unknown"),
                    "metadata": doc.get("metadata", {}),
                },
            )
            for doc, emb in zip(documents, embeddings)
        ]

        await self.qdrant.upsert(collection_name=self.collection, points=points)
        logger.info("documents_added", count=len(points))
        return len(points)

    async def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Search for relevant documents.
        Returns top_k most similar chunks with scores.
        """
        query_vec = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.embedder.encode(query).tolist()
        )

        hits = await self.qdrant.search(
            collection_name=self.collection,
            query_vector=query_vec,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "text":     h.payload["text"],
                "source":   h.payload.get("source", ""),
                "score":    round(h.score, 4),
                "metadata": h.payload.get("metadata", {}),
            }
            for h in hits
        ]