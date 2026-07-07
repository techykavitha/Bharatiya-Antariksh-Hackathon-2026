"""Application bootstrap and service wiring for Hyperion Climate Twin."""

from __future__ import annotations

from backend.config.dependency_registry import DependencyRegistry, get_registry
from backend.config.logger import configure_logging, get_logger
from backend.config.settings import GlobalConfig, get_config

logger = get_logger(__name__)

# Well-known dependency registry keys
CONFIG_KEY = "config"
REGISTRY_KEY = "registry"


def bootstrap(config: GlobalConfig | None = None) -> DependencyRegistry:
    """
    Initialize core application services and register them in the DI container.

    Call once at application startup before any agents are invoked.

    Parameters
    ----------
    config:
        Optional explicit configuration. Defaults to environment-loaded config.

    Returns
    -------
    DependencyRegistry
        The populated dependency registry.
    """
    cfg = config or get_config()
    configure_logging(cfg)

    registry = get_registry()
    registry.register_singleton(CONFIG_KEY, cfg)
    registry.register_singleton(REGISTRY_KEY, registry)

    logger.info(
        "application_bootstrapped",
        environment=cfg.environment.value,
        debug=cfg.debug,
    )
    return registry
