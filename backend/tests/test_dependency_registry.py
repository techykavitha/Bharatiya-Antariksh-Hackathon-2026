"""Tests for the dependency injection registry."""

import pytest

from backend.config.dependency_registry import DependencyRegistry, reset_registry
from backend.utils.errors import DependencyNotFoundError, DependencyRegistrationError


@pytest.fixture
def registry() -> DependencyRegistry:
    reg = DependencyRegistry()
    yield reg
    reg.clear()


def test_register_and_resolve_singleton(registry: DependencyRegistry) -> None:
    registry.register_singleton("config", {"env": "test"})
    assert registry.resolve("config") == {"env": "test"}


def test_register_factory(registry: DependencyRegistry) -> None:
    counter = {"n": 0}

    def factory() -> int:
        counter["n"] += 1
        return counter["n"]

    registry.register_factory("counter", factory)
    assert registry.resolve("counter") == 1
    assert registry.resolve("counter") == 2


def test_duplicate_registration_raises(registry: DependencyRegistry) -> None:
    registry.register_singleton("svc", object())
    with pytest.raises(DependencyRegistrationError):
        registry.register_singleton("svc", object())


def test_resolve_missing_raises(registry: DependencyRegistry) -> None:
    with pytest.raises(DependencyNotFoundError):
        registry.resolve("missing")


def test_reset_default_registry() -> None:
    reset_registry()
