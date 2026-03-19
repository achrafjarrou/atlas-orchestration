-- ATLAS Database Initialization
-- Runs automatically on first docker compose up

CREATE TABLE IF NOT EXISTS audit_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id       VARCHAR(64) UNIQUE NOT NULL,
    action          VARCHAR(100) NOT NULL,
    agent_id        VARCHAR(100) NOT NULL,
    session_id      VARCHAR(100),
    task_id         VARCHAR(100),
    intent          TEXT,
    input_data      JSONB DEFAULT '{}',
    output_data     JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    previous_hash   VARCHAR(64),
    record_hash     VARCHAR(64) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_agent_id   ON audit_records(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_records(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_task_id    ON audit_records(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_records(created_at DESC);

CREATE TABLE IF NOT EXISTS agent_registry (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                VARCHAR(100) UNIQUE NOT NULL,
    name                    VARCHAR(200) NOT NULL,
    base_url                VARCHAR(500) NOT NULL,
    capabilities            JSONB NOT NULL DEFAULT '[]',
    skills                  JSONB NOT NULL DEFAULT '[]',
    version                 VARCHAR(20) DEFAULT '1.0.0',
    provider                JSONB,
    authentication          JSONB DEFAULT '{"schemes": []}',
    capability_embedding    float[],
    status                  VARCHAR(20) DEFAULT 'active',
    last_heartbeat          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    health_score            FLOAT DEFAULT 1.0,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_status  ON agent_registry(status);
CREATE INDEX IF NOT EXISTS idx_agent_updated ON agent_registry(updated_at DESC);

CREATE TABLE IF NOT EXISTS task_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         VARCHAR(100) UNIQUE NOT NULL,
    session_id      VARCHAR(100),
    input_message   TEXT NOT NULL,
    routed_to_agent VARCHAR(100),
    routing_score   FLOAT,
    status          VARCHAR(30) NOT NULL DEFAULT 'submitted',
    result          JSONB,
    error           TEXT,
    requires_hitl   BOOLEAN DEFAULT FALSE,
    hitl_approved   BOOLEAN,
    hitl_approved_by VARCHAR(100),
    hitl_approved_at TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    duration_ms     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_task_session ON task_records(session_id);
CREATE INDEX IF NOT EXISTS idx_task_status  ON task_records(status);

-- Seed: register ATLAS itself
INSERT INTO agent_registry (agent_id, name, base_url, capabilities, skills, version)
VALUES (
    'atlas-orchestrator-v1',
    'ATLAS Orchestrator',
    'http://localhost:8000',
    '[{"id": "orchestration", "name": "Multi-agent orchestration", "description": "Route and coordinate tasks across agents"},
      {"id": "audit", "name": "Audit trail", "description": "SHA-256 tamper-proof EU AI Act compliance"},
      {"id": "discovery", "name": "Agent discovery", "description": "Semantic routing to best agent for any task"}]',
    '[{"id": "route_task", "name": "Route Task", "description": "Route a task to the best available agent"},
      {"id": "audit_report", "name": "Audit Report", "description": "EU AI Act Article 9 compliance report"}]',
    '0.1.0'
) ON CONFLICT (agent_id) DO NOTHING;