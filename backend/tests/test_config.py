"""Tests for application configuration."""

from backend.config.settings import GlobalConfig, clear_config_cache, get_config


def test_global_config_defaults() -> None:
    clear_config_cache()
    config = GlobalConfig()
    assert config.environment.value == "development"
    assert config.llm.model_name == "gpt-4o"
    assert config.embedding.dimension == 1536
    assert config.redis.port == 6379
    assert config.qdrant.port == 6333


def test_get_config_is_cached() -> None:
    clear_config_cache()
    first = get_config()
    second = get_config()
    assert first is second
