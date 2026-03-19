# atlas/a2a/protocol.py
# A2A Protocol v0.3 — All message types and data structures
# Full spec: https://google.github.io/A2A/
#
# KEY CONCEPTS:
#   AgentCard  = /.well-known/agent.json — who am I, what can I do
#   Task       = unit of work sent between agents
#   Message    = content (role + parts: text/data/file)
#   Artifact   = output produced by an agent

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import Field
from atlas.core.models import ATLASBaseModel, generate_id, utc_now


class A2ATaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class A2AMessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"


class A2AArtifactType(str, Enum):
    TEXT = "text"
    CODE = "code"
    JSON = "json"
    FILE = "file"
    IMAGE = "image"


# Message Parts — multimodal support
class TextPart(ATLASBaseModel):
    type: Literal["text"] = "text"
    text: str

class DataPart(ATLASBaseModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]

class FilePart(ATLASBaseModel):
    type: Literal["file"] = "file"
    file_name: str
    mime_type: str
    data: str | None = None   # base64 content
    url: str | None = None    # or URL to fetch

MessagePart = TextPart | DataPart | FilePart


class A2AMessage(ATLASBaseModel):
    """A message in the A2A conversation (user or agent turn)."""
    role: A2AMessageRole
    parts: list[MessagePart] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def user(cls, text: str) -> "A2AMessage":
        return cls(role=A2AMessageRole.USER, parts=[TextPart(text=text)])

    @classmethod
    def agent(cls, text: str) -> "A2AMessage":
        return cls(role=A2AMessageRole.AGENT, parts=[TextPart(text=text)])

    @property
    def text(self) -> str:
        return " ".join(p.text for p in self.parts if isinstance(p, TextPart))


class A2AArtifact(ATLASBaseModel):
    id: str = Field(default_factory=lambda: generate_id("art"))
    artifact_type: A2AArtifactType
    name: str | None = None
    description: str | None = None
    content: str | dict[str, Any] = ""
    mime_type: str = "text/plain"
    index: int = 0
    append: bool = False
    last_chunk: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskStatus(ATLASBaseModel):
    state: A2ATaskState
    message: A2AMessage | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class A2ATask(ATLASBaseModel):
    """Core unit of work in A2A. Sent from agent to agent."""
    id: str = Field(default_factory=lambda: generate_id("task"))
    session_id: str = Field(default_factory=lambda: generate_id("session"))
    message: A2AMessage
    context_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class A2ATaskWithStatus(A2ATask):
    status: A2ATaskStatus = Field(
        default_factory=lambda: A2ATaskStatus(state=A2ATaskState.SUBMITTED))
    artifacts: list[A2AArtifact] = Field(default_factory=list)
    history: list[A2AMessage] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


# Agent Card — served at /.well-known/agent.json
class AgentProvider(ATLASBaseModel):
    organization: str
    url: str | None = None

class AgentCapabilitySpec(ATLASBaseModel):
    streaming: bool = True
    push_notifications: bool = False
    state_transition_history: bool = True

class A2ASkill(ATLASBaseModel):
    """Specific callable action an agent exposes.
    Keep descriptions detailed — they drive semantic routing accuracy."""
    id: str
    name: str
    description: str   # CRITICAL: detailed → better routing
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    input_modes: list[str] = Field(default_factory=lambda: ["text"])
    output_modes: list[str] = Field(default_factory=lambda: ["text", "data"])

class A2AAgentCard(ATLASBaseModel):
    """The A2A Agent Card served at /.well-known/agent.json.
    Other agents fetch this to discover: capabilities, auth, API URL."""
    name: str
    description: str
    url: str
    version: str = "0.1.0"
    provider: AgentProvider | None = None
    capabilities: AgentCapabilitySpec = Field(default_factory=AgentCapabilitySpec)
    authentication: dict[str, Any] = Field(
        default_factory=lambda: {"schemes": [{"scheme": "none"}]})
    default_input_modes: list[str] = Field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["text", "data"])
    skills: list[A2ASkill] = Field(default_factory=list)


# JSON-RPC 2.0 Envelope — A2A transport protocol
class A2ARequest(ATLASBaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str = Field(default_factory=lambda: generate_id("rpc"))
    method: str
    params: dict[str, Any] = Field(default_factory=dict)

class A2AResponse(ATLASBaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

class A2AError(ATLASBaseModel):
    code: int
    message: str
    data: Any | None = None
    TASK_NOT_FOUND = -32001
    TASK_NOT_CANCELLABLE = -32002
    AUTHENTICATION_REQUIRED = -32005