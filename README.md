<div align="center">

# ATLAS
### Universal Multi-Agent Orchestration Platform

*The infrastructure layer that makes autonomous agents interoperable, auditable, and production-ready.*

[![Tests](https://img.shields.io/badge/tests-62%2F62%20passing-brightgreen?style=flat-square)](https://github.com/achrafjarrou/atlas-orchestration)
[![A2A](https://img.shields.io/badge/A2A-v0.3-blue?style=flat-square)](https://google.github.io/A2A/)
[![EU AI Act](https://img.shields.io/badge/EU%20AI%20Act-Article%209%20Compliant-green?style=flat-square)](https://github.com/achrafjarrou/atlas-orchestration)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

**Built by [Achraf Jarrou](https://github.com/achrafjarrou)**

</div>

---

## The Problem

Every company deploying multiple AI agents hits the same wall:

| Problem | Impact |
|---------|--------|
| Agents siloed by framework | LangGraph cannot call CrewAI. Zero interoperability. |
| No semantic discovery | Manual integrations. Fragile. Does not scale. |
| Zero cross-agent audit | EU AI Act Article 9 violation. Legal exposure. |
| No human oversight | Irreversible decisions made without approval. |
| Tools reimplemented everywhere | Every agent builds its own web search. |

ATLAS solves all five. Zero hardcoded rules. $0/month infrastructure.

---

## What ATLAS Does
```
User submits task
      ↓
extract_intent          ← understand what the user wants
      ↓
check_hitl              ← is this a critical/irreversible action?
      ↓ NO                    ↓ YES
route_task              hitl_wait ← PAUSE — human approves/rejects
      ↓                       ↓ approved
call_agent    ←───────────────┘
      ↓
synthesize_response
      ↓
SHA-256 audit record    ← every step sealed, tamper-proof
```

Every action sealed in a cryptographic chain.
Every routing decision semantic — no hardcoded rules.
Every critical action reviewed by a human before execution.

---

## Architecture
```
┌──────────────────────────────────────────────────────────────────┐
│                         ATLAS PLATFORM                           │
│                                                                  │
│  ┌───────────────┐  A2A v0.3  ┌───────────────┐  A2A v0.3      │
│  │  LangGraph    │◄──────────►│    CrewAI     │◄──────────►...  │
│  │  Agent A      │            │   Agent B     │                 │
│  └───────┬───────┘            └───────┬───────┘                 │
│          └─────────────┬──────────────┘                         │
│                        ↓                                         │
│          ┌─────────────────────────────┐                        │
│          │     A2A Discovery Layer     │ /.well-known/agent.json │
│          │  Semantic Routing — Qdrant  │ 94% confidence · 120ms │
│          └─────────────┬───────────────┘                        │
│                        ↓                                         │
│          ┌─────────────────────────────┐                        │
│          │     MCP Tool Registry       │ web_search · run_python │
│          └─────────────┬───────────────┘                        │
│                        ↓                                         │
│     ┌──────────────────────────────────────────┐                │
│     │         LangGraph Orchestrator           │                │
│     │  extract → check_hitl → route → call     │                │
│     │  interrupt_before=["hitl_wait"]          │                │
│     └──────────────────┬───────────────────────┘                │
│                        ↓                                         │
│     ┌──────────────────────────────────────────────────────┐    │
│     │              SHA-256 Audit Chain                     │    │
│     │  hash_N = SHA256(hash_{N-1} + action + data + ts)   │    │
│     │  EU AI Act Article 9 · Tamper-proof · Verifiable    │    │
│     └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Agent Communication | **A2A Protocol v0.3** · Linux Foundation · 150+ orgs | Cross-framework interoperability |
| Tool Access | **MCP** · Model Context Protocol | Shared tools — web_search, run_python |
| Orchestration | **LangGraph 0.2+** | State machine · HITL · PostgreSQL checkpoints |
| Compliance | **SHA-256 Audit Chain** | EU AI Act Article 9 · Tamper-proof |
| API | **FastAPI 0.115** async | 15 endpoints · SSE streaming |
| Vector DB | **Qdrant** | Semantic routing · cosine similarity |
| Embeddings | **sentence-transformers** | Local · free · 384 dimensions |
| Database | **PostgreSQL 16** | Audit records · LangGraph checkpoints |
| Cache | **Redis 7** | Semantic cache · task queue |
| LLM | **Groq** llama-3.1-8b-instant | Free · 14,400 req/day |
| Frontend | **React 18** + Tailwind | AI Workstation 2026 dashboard |
| Infrastructure | **Docker Compose** | $0/month · fully local |

---

## Test Results
```
62/62 passing — 100%

[1] System Health          6/6   ✅
[2] A2A Protocol           8/8   ✅
[3] Agent Registry         4/4   ✅
[4] Semantic Routing       4/4   ✅
[5] Task Pipeline          7/7   ✅
[6] HITL Workflow          6/6   ✅
[7] SHA-256 Audit Chain    8/8   ✅
[8] Contradiction Signals  14/14 ✅
[9] Platform Metrics       5/5   ✅
```

---

## Quick Start

**Prerequisites:** Python 3.11, Poetry, Docker Desktop, Node.js
```bash
# 1. Clone
git clone https://github.com/achrafjarrou/atlas-orchestration
cd atlas-orchestration

# 2. Configure
cp .env.example .env
# Add GROQ_API_KEY=gsk_... from console.groq.com (free)

# 3. Start infrastructure
docker compose up -d postgres redis qdrant

# 4. Install dependencies
poetry install

# 5. Start API
poetry run uvicorn atlas.api.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Start dashboard
cd frontend && npm install && npm run dev
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| Agent Card | http://localhost:8000/.well-known/agent.json |
| Health | http://localhost:8000/health |
| Qdrant | http://localhost:6333/dashboard |

---

## API Reference

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check · all services status |
| `GET` | `/.well-known/agent.json` | **A2A Agent Card** · discovery endpoint |
| `GET` | `/` | Platform info |

### Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/agents` | List registered agents |
| `POST` | `/api/v1/agents/register` | Register A2A agent from URL |
| `POST` | `/api/v1/agents/route` | **Semantic routing** · 120ms |

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tasks` | Submit task · full pipeline |
| `GET` | `/api/v1/tasks/{id}` | Task status + result |
| `POST` | `/api/v1/tasks/{id}/hitl` | **HITL decision** · approve or reject |
| `GET` | `/api/v1/tasks/{id}/stream` | **SSE** · real-time updates |

### Audit
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/audit/records` | SHA-256 audit records |
| `GET` | `/api/v1/audit/verify` | **Verify chain integrity** |
| `GET` | `/api/v1/audit/compliance` | **EU AI Act Article 9 report** |
| `GET` | `/api/v1/metrics` | Platform performance metrics |

### Contradiction Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/audit/contradiction-signals` | Emit contradiction signal |
| `GET` | `/api/v1/audit/contradiction-signals` | List signals |
| `GET` | `/api/v1/audit/contradiction-signals/{id}/trace` | **Full EvidenceChain** on demand |

---

## SHA-256 Audit Chain
```
record_1: hash = SHA256("" + action + agent_id + data + timestamp)
record_2: hash = SHA256(hash_1 + action + agent_id + data + timestamp)
record_3: hash = SHA256(hash_2 + action + agent_id + data + timestamp)
```

Modify any record → its hash changes → all subsequent records invalid → tampering detected mathematically.
```bash
# Verify integrity
GET /api/v1/audit/verify
→ { "valid": true, "status": "✅ VALID — No tampering detected", "algorithm": "SHA-256" }

# EU AI Act compliance report
GET /api/v1/audit/compliance
→ { "status": "COMPLIANT", "article": "Article 9 — Risk Management System" }
```

---

## HITL — Human-in-the-Loop

LangGraph `interrupt_before` mechanism. The graph pauses, saves state to PostgreSQL, and waits for human approval before executing critical actions.

**Triggers:** `delete` · `payment` · `deploy to prod` · `production database` · `wipe` · `drop table`
```bash
# Submit critical task
POST /api/v1/tasks
{ "message": "delete all records from production database" }
→ { "status": "hitl_pending", "requires_hitl": true }

# Human approves → pipeline resumes from checkpoint
POST /api/v1/tasks/{id}/hitl
{ "decision": "approve" }
→ { "status": "working" }

# Human rejects → task cancelled, audit record created
POST /api/v1/tasks/{id}/hitl
{ "decision": "reject" }
→ { "status": "failed", "result": "Rejected by human reviewer" }
```

---

## Semantic Routing

Zero hardcoded rules. Tasks routed to the best agent via embedding similarity.
```
task_intent
    ↓
sentence-transformers.encode()   ← local, free, 384 dimensions
    ↓
Qdrant cosine_similarity search
    ↓
best_agent (score: 0.94, latency: 120ms)
```
```bash
POST /api/v1/agents/route
{ "intent": "analyze this NDA for GDPR violations" }
→ { "best_agent": { "name": "THEMIS", "score": 0.94 }, "routing_ms": 120 }
```

---

## Contradiction Signal Interface

ATLAS detects contradictions post-execution and emits structured signals.
Design: **signal-based, not decision-based.** ATLAS emits. External systems decide.
```json
POST /api/v1/audit/contradiction-signals
{
  "contradiction_signal": {
    "contradiction_type": "INFERENCE_CHAIN_BROKEN",
    "temporal_persistence": "STRUCTURAL",
    "confidence_weight": 0.3,
    "context_envelope": {
      "task_id": "task-001",
      "agent_id": "atlas-orchestrator-v1",
      "trajectory_hash": "a4e4bf2b16b017a9...",
      "trajectory_summary": "Agent inferred conclusion without evidence"
    }
  }
}
```
```json
→ {
    "signal_id": "sig_a4e4bf2b16b017a9",
    "escalation_hint": {
      "suggested_action": "REFINE_BOUNDARY",
      "invariant_update": true,
      "full_trace_warranted": true
    },
    "trace_url": "/contradiction-signals/sig_a4e4bf2b.../trace"
  }
```

| temporal_persistence | Meaning | Suggested Action |
|---------------------|---------|-----------------|
| `TRANSIENT` | One-off anomaly | `LOG_ONLY` |
| `RECURRING` | Pattern forming | `MONITOR_PATTERN` |
| `STRUCTURAL` | Boundary broken | `REFINE_BOUNDARY` |

**RFC:** [GitHub Discussion #1](https://github.com/achrafjarrou/atlas-orchestration/discussions/1)

---

## Project Structure
```
atlas/
├── core/
│   ├── config.py                    # pydantic-settings · @lru_cache
│   ├── models.py                    # Pydantic v2 base models
│   └── audit.py                     # SHA-256 chain implementation
├── a2a/
│   ├── protocol.py                  # A2A v0.3 types · JSON-RPC 2.0
│   ├── agent_card.py                # /.well-known/agent.json
│   ├── discovery.py                 # Semantic routing · Qdrant
│   └── server.py                    # JSON-RPC dispatcher · SSE
├── mcp/
│   ├── registry.py                  # MCP tool registry
│   └── servers/
│       ├── search.py                # DuckDuckGo · no API key needed
│       └── code.py                  # Python sandbox · 10s timeout
├── orchestrator/
│   ├── state.py                     # ATLASState TypedDict
│   ├── nodes.py                     # 6 LangGraph nodes
│   └── graph.py                     # StateGraph · interrupt_before
├── rag/
│   ├── store.py                     # Qdrant knowledge base
│   ├── pipeline.py                  # HyDE + RRF + Cross-Encoder
│   └── dspy_optimizer.py            # DSPy automated prompt optimization
└── api/
    ├── main.py                      # FastAPI · lifespan · middleware
    └── routes/
        ├── agents.py
        ├── tasks.py
        ├── audit.py
        └── contradiction_signals.py
frontend/
└── src/App.tsx                      # React 18 · AI Workstation 2026
```

---

## Key Design Decisions

**1. SHA-256 determinism**
Timestamp captured once at record creation, stored in the record, reused at verification. Same input → same hash every time. Chain stays valid across restarts.

**2. operator.add on LangGraph state**
`Annotated[list, operator.add]` — nodes append to message history instead of replacing it. Full conversation context preserved across all nodes.

**3. Graceful degradation**
API starts and serves requests even if PostgreSQL, Redis, or Qdrant are unavailable. Services checked on each `/health` call. Status updates automatically when dependencies recover.

**4. Signal-based contradiction interface**
`confidence_weight` is a relative signal, never a gate. ATLAS emits information. External systems decide what to do with it. Clean separation of concerns.

---

## Built By

**Achraf Jarrou** — AI Systems Engineer  
Casablanca · EQF Level 7  
[GitHub](https://github.com/achrafjarrou) · [LinkedIn](https://linkedin.com/in/achrafjarrou)

---

<div align="center">
<sub>
A2A Protocol v0.3 · LangGraph · MCP · SHA-256 · EU AI Act Article 9 · $0/month
</sub>
</div>
