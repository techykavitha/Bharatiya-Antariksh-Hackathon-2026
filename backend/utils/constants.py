"""Shared constants for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------
APP_NAME: str = "hyperion-climate-twin"
APP_VERSION: str = "0.1.0"
DEFAULT_TIMEZONE: str = "UTC"

# ---------------------------------------------------------------------------
# Agent defaults
# ---------------------------------------------------------------------------
DEFAULT_AGENT_TIMEOUT_SECONDS: int = 120
MAX_AGENT_RETRIES: int = 3
MAX_TOOL_CALLS_PER_INVOCATION: int = 10
MAX_REASONING_ITERATIONS: int = 5

# ---------------------------------------------------------------------------
# Conversation & memory
# ---------------------------------------------------------------------------
MAX_CONVERSATION_HISTORY: int = 50
DEFAULT_MEMORY_TTL_SECONDS: int = 86_400  # 24 hours
VECTOR_SEARCH_TOP_K: int = 10
KNOWLEDGE_GRAPH_MAX_DEPTH: int = 3

# ---------------------------------------------------------------------------
# Climate & simulation
# ---------------------------------------------------------------------------
DEFAULT_FORECAST_HORIZON_HOURS: int = 72
DEFAULT_SPATIAL_RESOLUTION_KM: float = 1.0
MAX_SIMULATION_STEPS: int = 1_000

# ---------------------------------------------------------------------------
# Redis key prefixes
# ---------------------------------------------------------------------------
REDIS_KEY_PREFIX: str = "hyperion"
REDIS_SESSION_PREFIX: str = f"{REDIS_KEY_PREFIX}:session"
REDIS_MEMORY_PREFIX: str = f"{REDIS_KEY_PREFIX}:memory"
REDIS_AGENT_PREFIX: str = f"{REDIS_KEY_PREFIX}:agent"

# ---------------------------------------------------------------------------
# Qdrant collection names
# ---------------------------------------------------------------------------
QDRANT_COLLECTION_CLIMATE: str = "climate_embeddings"
QDRANT_COLLECTION_DOCUMENTS: str = "document_embeddings"
QDRANT_COLLECTION_FORECASTS: str = "forecast_embeddings"

# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------
DI_REGISTRY_NAMESPACE: str = "hyperion.di"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
DEFAULT_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
JSON_LOG_FORMAT: str = "json"
