# ATLAS — Récapitulatif Complet du Projet
*Généré le 2026-03-17 20:39:07*

---

## Ce que tu as construit

**ATLAS** = Universal Multi-Agent Orchestration Platform  
**Tagline** = The infrastructure layer that makes autonomous agents interoperable, auditable, and production-ready.

---

## Stack Technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Agent-to-Agent | A2A Protocol v0.3 (Linux Foundation) | Communication entre agents de frameworks différents |
| Agent-to-Tool | MCP (Model Context Protocol) | Accès aux outils partagés (web_search, run_python) |
| Orchestration | LangGraph 0.2+ | State machine + HITL + checkpoint PostgreSQL |
| Compliance | SHA-256 Audit Chain | EU AI Act Article 9 — tamper-proof |
| API | FastAPI 0.115 async | 10 endpoints REST + SSE streaming |
| Vector DB | Qdrant | Routing sémantique par similarité cosinus |
| Embeddings | sentence-transformers | Local, gratuit, 384 dimensions |
| DB | PostgreSQL 16 | Audit records + LangGraph checkpoints |
| Cache | Redis 7 | Cache sémantique + task queue |
| Infrastructure | Docker Compose | PostgreSQL + Redis + Qdrant () |
| Frontend | React 18 + TypeScript + Tailwind | Dashboard AI Workstation 2026 |
| CI/CD | GitHub Actions | test + lint + docker build (gratuit) |
| LLM | Groq (llama-3.1-8b-instant) | Gratuit, 14 400 req/jour |

---

## Fichiers Clés

### Jour 1 — Core Infrastructure
- `atlas/core/config.py` — pydantic-settings, @lru_cache singleton, feature flags
- `atlas/core/models.py` — Pydantic v2 base models, enums, TypedDicts
- `atlas/core/audit.py` — SHA-256 chain: hash_N = SHA256(hash_{N-1} + data)
- `docker-compose.yml` — PostgreSQL + Redis + Qdrant, networking Docker
- `scripts/init_db.sql` — Tables audit_records, agent_registry, task_records

### Jour 2 — A2A Protocol
- `atlas/a2a/protocol.py` — A2AAgentCard, A2ATask, A2AMessage, JSON-RPC types
- `atlas/a2a/agent_card.py` — GET /.well-known/agent.json (discovery endpoint)
- `atlas/a2a/discovery.py` — AgentRegistry, embedding + Qdrant upsert, route()
- `atlas/a2a/server.py` — JSON-RPC 2.0 dispatcher: tasks/send, tasks/get, tasks/cancel + SSE

### Jour 3 — MCP + LangGraph + API
- `atlas/mcp/registry.py` — MCPRegistry singleton, call(), to_langchain_tools()
- `atlas/mcp/servers/search.py` — DuckDuckGo async (free, no API key)
- `atlas/mcp/servers/code.py` — Python sandbox (whitelist builtins, 10s timeout)
- `atlas/orchestrator/state.py` — ATLASState TypedDict, Annotated[list, operator.add]
- `atlas/orchestrator/nodes.py` — extract_intent, check_hitl, route_task, call_agent, synthesize
- `atlas/orchestrator/graph.py` — StateGraph, interrupt_before, MemorySaver/PostgresSaver
- `atlas/api/main.py` — FastAPI lifespan, Depends(), middleware, 10 endpoints

### Jour 4 — RAG Pipeline
- `atlas/rag/store.py` — KnowledgeStore: add_documents(), search()
- `atlas/rag/pipeline.py` — HyDE + RRF + Cross-Encoder reranking (+45% accuracy)
- `atlas/rag/dspy_optimizer.py` — DSPy MIPROv2: automated prompt optimization

### Jour 5 — Dashboard + Deploy
- `frontend/src/App.tsx` — React 18 + Tailwind: 6 panels, live updates, HITL UI
- `Dockerfile.spaces` — HuggingFace Spaces (port 7860)

---

## Endpoints API

| Method | URL | Description |
|--------|-----|-------------|
| GET | /health | Health check + services status |
| GET | / | Platform info |
| GET | /.well-known/agent.json | **A2A Agent Card** (discovery) |
| GET | /api/v1/agents | List registered agents |
| POST | /api/v1/agents/register | Register new A2A agent |
| POST | /api/v1/agents/route | **Semantic routing** |
| POST | /api/v1/tasks | Submit task (full pipeline) |
| GET | /api/v1/tasks/{id} | Get task status + result |
| POST | /api/v1/tasks/{id}/hitl | **HITL: approve/reject** |
| GET | /api/v1/tasks/{id}/stream | **SSE real-time** updates |
| GET | /api/v1/audit/records | List audit records |
| GET | /api/v1/audit/verify | **Verify SHA-256 chain** |
| GET | /api/v1/audit/compliance | **EU AI Act Art.9 report** |
| GET | /api/v1/metrics | Performance metrics |
| POST | /a2a | **A2A JSON-RPC 2.0** dispatcher |

---

## Concepts Clés

### SHA-256 Audit Chain
`
record_1: hash = SHA256("" + id + action + data)
record_2: hash = SHA256(record_1.hash + id + action + data)
record_3: hash = SHA256(record_2.hash + id + action + data)
→ Modifier record_1 casse tous les hashes suivants (preuve de falsification)
→ EU AI Act Article 9 : conforme
`

### A2A Protocol
`
GET /.well-known/agent.json  →  Agent Card (who I am, what I do)
POST /a2a                    →  JSON-RPC 2.0: tasks/send, tasks/get, tasks/cancel
→ Standard Linux Foundation, 150+ orgs (Google, Microsoft, SAP, Salesforce)
`

### LangGraph HITL
`
START → extract_intent → check_hitl → [PAUSE ← interrupt_before]
                                           ↓ human approves
                              route_task → call_agent → synthesize → END
→ State sauvegardé dans PostgreSQL → reprise après crash possible
`

### Semantic Routing
`
task_intent → sentence-transformers.encode() → 384-dim vector
             → Qdrant cosine_similarity → nearest agent
→ Zero règles hardcodées. "GDPR compliance" → THEMIS (0.94)
→ Target latency: <500ms
`

---

## Objectifs & Signal Recruteur

- **Cible** : CDI EU Amsterdam/Berlin €85-95K avec visa sponsorship
- **Remote US/CA** : -140K via Deel/Remote.com
- **Signal** : repo public GitHub "atlas-orchestration" → top résultat Google pour "A2A LangGraph MCP"
- **Différenciateur** : 0 projet open-source combine A2A + LangGraph + MCP + audit en production
- **LinkedIn** : Post #1 le Jour 5 → inbound recruteurs EU/US

---

## Commandes Essentielles
`powershell
# Démarrer tout
docker compose up -d
poetry run uvicorn atlas.api.main:app --port 8000 --reload
cd frontend && npm run dev

# Tester
Invoke-RestMethod "http://localhost:8000/health"
Invoke-RestMethod "http://localhost:8000/.well-known/agent.json"

# Tester une tâche
Invoke-RestMethod -Method POST "http://localhost:8000/api/v1/tasks" `
  -ContentType "application/json" `
  -Body '{"message":"analyze this contract for GDPR"}'

# Rapport EU AI Act
Invoke-RestMethod "http://localhost:8000/api/v1/audit/compliance"

# Push GitHub
git remote add origin https://github.com/achrafjarrou/atlas-orchestration
git push -u origin main
`

---

## URLs

- Dashboard : http://localhost:3000
- API Docs  : http://localhost:8000/docs
- Agent Card: http://localhost:8000/.well-known/agent.json
- Health    : http://localhost:8000/health
- Qdrant    : http://localhost:6333/dashboard

---

*Le seul critère de succès : un recruteur trouve ATLAS sur GitHub sans qu'Achraf ait posté sa candidature.*