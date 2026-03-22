FROM python:3.11-slim

RUN useradd -m -u 1000 user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install deps directement (sans Poetry pour simplifier)
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    httpx==0.27.0 \
    pydantic==2.9.0 \
    pydantic-settings==2.5.0 \
    structlog==24.4.0 \
    python-dotenv==1.0.0 \
    langchain-core==0.3.20 \
    langgraph==0.2.55 \
    langchain-groq==0.2.1 \
    sentence-transformers==3.2.0 \
    rank-bm25==0.2.2 \
    duckduckgo-search==6.3.0 \
    aiosqlite==0.20.0 \
    sqlalchemy[asyncio]==2.0.35 \
    tenacity==9.0.0 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4

COPY --chown=user atlas/ ./atlas/

# .env pour HuggingFace (sans PostgreSQL/Redis/Qdrant)
RUN echo 'ENVIRONMENT=production\n\
DEBUG=false\n\
DATABASE_URL=sqlite+aiosqlite:///./atlas.db\n\
REDIS_URL=redis://localhost:6379/0\n\
QDRANT_URL=http://localhost:6333\n\
SECRET_KEY=atlas-hf-spaces-secret-key-production-32chars\n\
ATLAS_AGENT_NAME=ATLAS Orchestrator\n\
ATLAS_BASE_URL=https://achrafjarrou-atlas-orchestration.hf.space\n\
EMBEDDING_MODEL=all-MiniLM-L6-v2\n\
EMBEDDING_DIMENSION=384\n\
DEFAULT_LLM_MODEL=llama-3.1-8b-instant\n\
GROQ_API_KEY=\n\
ENABLE_AUDIT_TRAIL=true\n\
ENABLE_HITL=true\n\
QDRANT_COLLECTION_AGENTS=atlas_agents\n\
QDRANT_COLLECTION_KNOWLEDGE=atlas_knowledge' > .env

USER user

EXPOSE 7860

CMD ["uvicorn", "atlas.api.main:app", "--host", "0.0.0.0", "--port", "7860"]