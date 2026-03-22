# atlas/core/config.py
# Central configuration — reads ALL settings from environment variables.
# One source of truth: every setting documented, typed, validated.
# Usage: from atlas.core.config import settings

from functools import lru_cache
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All ATLAS configuration. Reads from .env file + environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    database_url: str = "sqlite+aiosqlite:///./atlas.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection_agents: str = "atlas_agents"
    qdrant_collection_knowledge: str = "atlas_knowledge"

    # LLM
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    default_llm_provider: Literal["groq", "openai"] = "groq"
    default_llm_model: str = "llama-3.1-8b-instant"

    # Embeddings — runs locally, no API key
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Security
    secret_key: str = "atlas-dev-secret-key-change-in-production-minimum-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # A2A Protocol
    atlas_agent_id: str = "atlas-orchestrator-v1"
    atlas_agent_name: str = "ATLAS Orchestrator"
    atlas_base_url: str = "http://localhost:8000"
    a2a_auth_enabled: bool = False

    # Observability
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "atlas-orchestration"
    langfuse_secret_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Feature Flags
    enable_audit_trail: bool = True
    enable_semantic_cache: bool = True
    enable_hitl: bool = True
    enable_dspy_optimization: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()