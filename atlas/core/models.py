# atlas/core/models.py
# All Pydantic v2 base models. Used across the entire ATLAS codebase.
# Pattern: every module inherits from ATLASBaseModel for consistency.

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Always UTC — no timezone ambiguity."""
    return datetime.now(timezone.utc)


def generate_id(prefix: str = "") -> str:
    """Generate unique ID: generate_id("task") → "task_a3f2b1c4d5e6f7g8" """
    uid = str(uuid.uuid4()).replace("-", "")[:16]
    return f"{prefix}_{uid}" if prefix else uid


class ATLASBaseModel(BaseModel):
    """Base class for all ATLAS models."""
    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )


class TaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    HITL_PENDING = "hitl_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


class AuditStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


class AgentCapability(ATLASBaseModel):
    id: str
    name: str
    description: str


class AgentSkill(ATLASBaseModel):
    id: str
    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)


class AgentInfo(ATLASBaseModel):
    agent_id: str
    name: str
    base_url: str
    capabilities: list[AgentCapability] = Field(default_factory=list)
    skills: list[AgentSkill] = Field(default_factory=list)
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.ACTIVE
    health_score: float = Field(ge=0.0, le=1.0, default=1.0)
    last_heartbeat: datetime = Field(default_factory=utc_now)


class Message(ATLASBaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(ATLASBaseModel):
    id: str = Field(default_factory=lambda: generate_id("task"))
    session_id: str = Field(default_factory=lambda: generate_id("session"))
    message: Message
    context_id: str | None = None
    status: TaskStatus = TaskStatus.SUBMITTED
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class TaskResult(ATLASBaseModel):
    task_id: str
    status: TaskStatus
    agent_id: str
    result: dict[str, Any]
    duration_ms: int
    audit_record_id: str
    created_at: datetime = Field(default_factory=utc_now)


class AuditRecord(ATLASBaseModel):
    """One record in the SHA-256 tamper-proof chain.
    hash_N = SHA256(hash_{N-1} + record_id + action + timestamp + data)
    """
    id: str = Field(default_factory=lambda: generate_id("rec"))
    action: str
    agent_id: str
    session_id: str | None = None
    task_id: str | None = None
    intent: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str | None = None
    record_hash: str = ""
    status: AuditStatus = AuditStatus.SUCCESS
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class HealthResponse(ATLASBaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    environment: str = "development"
    services: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class ErrorResponse(ATLASBaseModel):
    error: str
    detail: str | None = None
    code: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)