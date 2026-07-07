"""Shared fixtures for Climate Knowledge Graph tests."""

from __future__ import annotations

import pytest

from backend.knowledge_graph import ClimateGraphBuilder, GraphEngine


@pytest.fixture
async def graph_engine() -> GraphEngine:
    return await GraphEngine.create()


@pytest.fixture
async def india_climate_graph() -> GraphEngine:
    engine = await GraphEngine.create()
    await ClimateGraphBuilder(engine).build_india_climate_graph()
    return engine
