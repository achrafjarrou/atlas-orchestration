# tests/test_rag.py — RAG pipeline tests
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np


class TestKnowledgeStore:
    @pytest.mark.asyncio
    async def test_add_documents(self, mock_qdrant, mock_embedder):
        from atlas.rag.store import KnowledgeStore
        store = KnowledgeStore(qdrant=mock_qdrant, embedder=mock_embedder)

        docs = [
            {"text": "A2A Protocol is a standard for agent communication", "source": "spec"},
            {"text": "LangGraph enables stateful agent workflows", "source": "docs"},
        ]
        count = await store.add_documents(docs)
        assert count == 2
        mock_qdrant.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_qdrant, mock_embedder):
        from atlas.rag.store import KnowledgeStore

        mock_hit = MagicMock()
        mock_hit.score = 0.88
        mock_hit.payload = {"text": "A2A is a protocol", "source": "spec", "metadata": {}}
        mock_qdrant.search.return_value = [mock_hit]

        store = KnowledgeStore(qdrant=mock_qdrant, embedder=mock_embedder)
        results = await store.search("what is A2A", top_k=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.88
        assert "A2A" in results[0]["text"]


class TestRRF:
    def test_rrf_combines_two_lists(self):
        from atlas.rag.pipeline import RAGPipeline
        list1 = [{"text": "doc_a", "score": 0.9}, {"text": "doc_b", "score": 0.7}]
        list2 = [{"text": "doc_b", "score": 0.8}, {"text": "doc_c", "score": 0.6}]

        result = RAGPipeline._reciprocal_rank_fusion([list1, list2], top_k=3)

        # doc_b appears in both lists → should rank higher
        texts = [r["text"] for r in result]
        assert "doc_b" in texts
        doc_b_idx = texts.index("doc_b")
        assert doc_b_idx <= 1   # should be in top-2

    def test_rrf_handles_empty_lists(self):
        from atlas.rag.pipeline import RAGPipeline
        result = RAGPipeline._reciprocal_rank_fusion([[], []], top_k=5)
        assert result == []