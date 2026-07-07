"""Structured logging for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from backend.config.settings import GlobalConfig, get_config
from backend.utils.enums import LogLevel


def _resolve_log_level(level: LogLevel | str) -> int:
    """Convert a ``LogLevel`` or string to a stdlib logging level integer."""
    if isinstance(level, LogLevel):
        return getattr(logging, level.value)
    return getattr(logging, str(level).upper(), logging.INFO)


def configure_logging(config: GlobalConfig | None = None) -> None:
    """
    Configure structlog and stdlib logging for the application.

    Parameters
    ----------
    config:
        Optional ``GlobalConfig`` instance. When omitted, the cached
        singleton from ``get_config()`` is used.
    """
    cfg = config or get_config()
    log_level = _resolve_log_level(cfg.logging.level)
    use_json = cfg.logging.format.lower() == "json"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if cfg.logging.include_timestamp:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    if use_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet noisy third-party loggers in non-debug mode
    if not cfg.debug:
        for noisy in ("httpx", "httpcore", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


class Logger:
    """
    Application logger wrapper backed by structlog.

    Provides a consistent interface for structured logging across agents,
    tools, services, and infrastructure components.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger = structlog.get_logger(name)

    @property
    def name(self) -> str:
        """Return the bound logger name."""
        return self._name

    def bind(self, **kwargs: Any) -> Logger:
        """Return a new ``Logger`` with additional bound context fields."""
        bound = Logger(self._name)
        bound._logger = self._logger.bind(**kwargs)
        return bound

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message."""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info-level message."""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning-level message."""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message."""
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a critical-level message."""
        self._logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message with exception traceback."""
        self._logger.exception(message, **kwargs)


def get_logger(name: str) -> Logger:
    """
    Return a named ``Logger`` instance.

    Parameters
    ----------
    name:
        Typically ``__name__`` of the calling module.
    """
    return Logger(name)
