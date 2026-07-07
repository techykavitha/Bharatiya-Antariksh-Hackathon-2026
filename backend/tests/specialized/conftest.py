"""Shared fixtures for specialized agent framework tests."""

from __future__ import annotations

import pytest

from backend.agents.memory.memory_manager import MemoryManager


@pytest.fixture
async def memory_manager() -> MemoryManager:
    return await MemoryManager.create_in_memory()
