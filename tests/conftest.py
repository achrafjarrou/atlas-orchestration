# tests/conftest.py — Shared pytest fixtures (auto-available in all test files)
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from atlas.core.models import generate_id

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS audit_records (
                id TEXT PRIMARY KEY, record_id TEXT UNIQUE,
                action TEXT NOT NULL, agent_id TEXT NOT NULL,
                session_id TEXT, task_id TEXT, intent TEXT,
                input_data TEXT DEFAULT '{}', output_data TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}', previous_hash TEXT,
                record_hash TEXT NOT NULL, status TEXT DEFAULT 'success',
                error_message TEXT, duration_ms INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

@pytest_asyncio.fixture
async def audit_trail(db_session):
    from atlas.core.audit import AuditTrail
    return AuditTrail(db=db_session)

@pytest.fixture
def mock_embedder():
    e = MagicMock()
    e.encode.return_value = np.random.rand(384).astype(np.float32)
    return e

@pytest.fixture
def mock_qdrant():
    q = AsyncMock()
    q.get_collections.return_value = MagicMock(collections=[])
    q.create_collection.return_value = None
    q.upsert.return_value = None
    q.search.return_value = []
    return q

@pytest.fixture
def mock_registry(db_session, mock_qdrant, mock_embedder):
    from atlas.a2a.discovery import AgentRegistry
    return AgentRegistry(db=db_session, qdrant=mock_qdrant, embedder=mock_embedder)

@pytest.fixture
def sample_task_id(): return generate_id("task")

@pytest.fixture
def sample_session_id(): return generate_id("session")

@pytest.fixture
def sample_agent_card():
    from atlas.a2a.protocol import A2AAgentCard, A2ASkill, AgentProvider
    return A2AAgentCard(name="Test Agent", description="A test agent",
                        url="http://test-agent:8001", version="1.0.0",
                        provider=AgentProvider(organization="Test Org"),
                        skills=[A2ASkill(id="test_skill", name="Test Skill",
                                         description="Does test things with test data", tags=["test"])])