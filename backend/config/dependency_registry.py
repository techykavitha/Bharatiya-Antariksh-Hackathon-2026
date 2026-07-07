"""Dependency injection registry for the Hyperion Climate Twin AI layer."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar, overload

from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError

T = TypeVar("T")


class DependencyRegistry:
    """
    Thread-safe service locator and dependency injection container.

    Supports registration of singleton instances and factory callables.
    Future agents, tools, and memory backends register themselves here
    at application startup.
    """

    def __init__(self) -> None:
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()

    def register_singleton(self, name: str, instance: Any) -> None:
        """
        Register a pre-constructed singleton instance.

        Raises
        ------
        DependencyRegistrationError
            If the name is already registered.
        """
        with self._lock:
            if name in self._singletons or name in self._factories:
                raise DependencyRegistrationError(
                    f"Dependency '{name}' is already registered",
                    details={"name": name},
                )
            self._singletons[name] = instance

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory callable that produces a new instance on each resolve.

        Raises
        ------
        DependencyRegistrationError
            If the name is already registered.
        """
        with self._lock:
            if name in self._singletons or name in self._factories:
                raise DependencyRegistrationError(
                    f"Dependency '{name}' is already registered",
                    details={"name": name},
                )
            self._factories[name] = factory

    def register(self, name: str, instance: Any) -> None:
        """Alias for ``register_singleton``."""
        self.register_singleton(name, instance)

    @overload
    def resolve(self, name: str) -> Any: ...

    @overload
    def resolve(self, name: str, expected_type: type[T]) -> T: ...

    def resolve(self, name: str, expected_type: type[T] | None = None) -> T | Any:
        """
        Resolve a registered dependency by name.

        Parameters
        ----------
        name:
            The registration key.
        expected_type:
            Optional type hint used for static analysis; not enforced at runtime.

        Raises
        ------
        DependencyNotFoundError
            If no dependency is registered under ``name``.
        """
        with self._lock:
            if name in self._singletons:
                return self._singletons[name]
            if name in self._factories:
                return self._factories[name]()

            raise DependencyNotFoundError(
                f"Dependency '{name}' is not registered",
                details={"name": name},
            )

    def has(self, name: str) -> bool:
        """Return True if a dependency is registered under ``name``."""
        with self._lock:
            return name in self._singletons or name in self._factories

    def unregister(self, name: str) -> None:
        """Remove a registered dependency."""
        with self._lock:
            self._singletons.pop(name, None)
            self._factories.pop(name, None)

    def clear(self) -> None:
        """Remove all registered dependencies."""
        with self._lock:
            self._singletons.clear()
            self._factories.clear()

    def list_registered(self) -> list[str]:
        """Return sorted list of all registered dependency names."""
        with self._lock:
            return sorted(set(self._singletons) | set(self._factories))


# Module-level default registry
_default_registry = DependencyRegistry()


def get_registry() -> DependencyRegistry:
    """Return the process-wide default dependency registry."""
    return _default_registry


def reset_registry() -> None:
    """Reset the default registry (primarily for testing)."""
    _default_registry.clear()
