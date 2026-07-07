"""Application configuration for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.utils.enums import Environment, LogLevel


class LLMConfig(BaseSettings):
    """Large language model connection and inference settings."""

    model_config = SettingsConfigDict(env_prefix="HYPERION_LLM_")

    provider: str = Field(default="openai", description="LLM provider identifier")
    model_name: str = Field(default="gpt-4o", description="Primary model name")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    api_key: SecretStr | None = Field(default=None, description="Provider API key")
    base_url: str | None = Field(default=None, description="Optional custom API base URL")
    timeout_seconds: int = Field(default=120, ge=1)


class EmbeddingConfig(BaseSettings):
    """Text embedding model configuration for vector memory."""

    model_config = SettingsConfigDict(env_prefix="HYPERION_EMBEDDING_")

    model_name: str = Field(default="text-embedding-3-small")
    dimension: int = Field(default=1536, ge=1)
    batch_size: int = Field(default=32, ge=1)


class RedisConfig(BaseSettings):
    """Redis connection settings for session and short-term memory."""

    model_config = SettingsConfigDict(env_prefix="HYPERION_REDIS_")

    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: SecretStr | None = Field(default=None)
    ssl: bool = Field(default=False)
    decode_responses: bool = Field(default=True)
    socket_timeout: float = Field(default=5.0, ge=0.1)


class QdrantConfig(BaseSettings):
    """Qdrant vector database connection settings."""

    model_config = SettingsConfigDict(env_prefix="HYPERION_QDRANT_")

    host: str = Field(default="localhost")
    port: int = Field(default=6333, ge=1, le=65535)
    grpc_port: int = Field(default=6334, ge=1, le=65535)
    api_key: SecretStr | None = Field(default=None)
    prefer_grpc: bool = Field(default=False)
    timeout_seconds: float = Field(default=30.0, ge=1.0)
    collection_climate: str = Field(default="climate_embeddings")
    collection_documents: str = Field(default="document_embeddings")
    collection_forecasts: str = Field(default="forecast_embeddings")


class LoggingConfig(BaseSettings):
    """Structured logging configuration."""

    model_config = SettingsConfigDict(env_prefix="HYPERION_LOG_")

    level: LogLevel = Field(default=LogLevel.INFO)
    format: str = Field(default="console", description="console or json")
    include_timestamp: bool = Field(default=True)
    include_caller: bool = Field(default=False)


class GlobalConfig(BaseSettings):
    """
    Root application configuration loaded from environment variables.

    Environment variable prefix: ``HYPERION_``
    Nested delimiter: ``__`` (e.g. ``HYPERION_LLM__MODEL_NAME``)
    """

    model_config = SettingsConfigDict(
        env_prefix="HYPERION_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @property
    def is_production(self) -> bool:
        """Return True when running in production environment."""
        return self.environment == Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_config() -> GlobalConfig:
    """
    Return a cached singleton ``GlobalConfig`` instance.

    Configuration is loaded once from environment variables and reused
    for the lifetime of the process.
    """
    return GlobalConfig()


def clear_config_cache() -> None:
    """Clear the cached configuration singleton (primarily for testing)."""
    get_config.cache_clear()
