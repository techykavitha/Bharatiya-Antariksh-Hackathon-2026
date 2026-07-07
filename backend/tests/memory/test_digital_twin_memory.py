"""Unit tests for digital twin memory."""

import pytest

from backend.agents.memory.digital_twin_memory import DigitalTwinMemoryStore
from backend.agents.memory.memory_types import TwinStateLayer
from backend.utils.errors import MemoryNotFoundError


@pytest.fixture
async def twin_with_data(twin_store: DigitalTwinMemoryStore) -> DigitalTwinMemoryStore:
    await twin_store.set_layer("twin-1", TwinStateLayer.CURRENT_CLIMATE, {"temp": 32.5, "humidity": 78})
    await twin_store.set_layer("twin-1", TwinStateLayer.FORECAST, {"temp_24h": 30.0})
    return twin_store


@pytest.mark.asyncio
async def test_twin_get_layer(twin_with_data: DigitalTwinMemoryStore) -> None:
    layer = await twin_with_data.get_layer("twin-1", TwinStateLayer.CURRENT_CLIMATE.value)
    assert layer is not None
    assert layer.value["temp"] == 32.5


@pytest.mark.asyncio
async def test_twin_checkpoint_and_rollback(twin_with_data: DigitalTwinMemoryStore) -> None:
    record = await twin_with_data.checkpoint("twin-1", label="before-sim")
    await twin_with_data.set_layer("twin-1", TwinStateLayer.SIMULATION, {"step": 100})
    await twin_with_data.rollback("twin-1", record.version)
    layer = await twin_with_data.get_layer("twin-1", TwinStateLayer.SIMULATION.value)
    assert layer is None or layer.value == {}


@pytest.mark.asyncio
async def test_twin_clone(twin_with_data: DigitalTwinMemoryStore) -> None:
    clone = await twin_with_data.clone_state("twin-1", "twin-1-clone")
    assert clone.key == "twin-1-clone"
    layer = await twin_with_data.get_layer("twin-1-clone", TwinStateLayer.CURRENT_CLIMATE.value)
    assert layer is not None
    assert layer.value["temp"] == 32.5


@pytest.mark.asyncio
async def test_twin_compare(twin_with_data: DigitalTwinMemoryStore) -> None:
    cp1 = await twin_with_data.checkpoint("twin-1")
    await twin_with_data.set_layer("twin-1", TwinStateLayer.CURRENT_CLIMATE, {"temp": 35.0})
    cp2 = await twin_with_data.checkpoint("twin-1")
    comparison = await twin_with_data.compare_state("twin-1", cp1.version, cp2.version)
    assert not comparison.identical
    assert TwinStateLayer.CURRENT_CLIMATE.value in comparison.changed_layers


@pytest.mark.asyncio
async def test_twin_merge_override(twin_with_data: DigitalTwinMemoryStore) -> None:
    other = {"layers": {TwinStateLayer.SIMULATION.value: {"step": 50}}}
    await twin_with_data.merge_state("twin-1", other, strategy="override")
    layer = await twin_with_data.get_layer("twin-1", TwinStateLayer.SIMULATION.value)
    assert layer is not None
    assert layer.value["step"] == 50


@pytest.mark.asyncio
async def test_twin_merge_deep(twin_with_data: DigitalTwinMemoryStore) -> None:
    await twin_with_data.merge_state(
        "twin-1",
        {"layers": {TwinStateLayer.CURRENT_CLIMATE.value: {"wind": 15.0}}},
        strategy="deep_merge",
    )
    layer = await twin_with_data.get_layer("twin-1", TwinStateLayer.CURRENT_CLIMATE.value)
    assert layer is not None
    assert layer.value["temp"] == 32.5
    assert layer.value["wind"] == 15.0


@pytest.mark.asyncio
async def test_twin_snapshot_not_found(twin_store: DigitalTwinMemoryStore) -> None:
    with pytest.raises(MemoryNotFoundError):
        await twin_store.snapshot("nonexistent")


@pytest.mark.asyncio
async def test_twin_list_checkpoints(twin_with_data: DigitalTwinMemoryStore) -> None:
    await twin_with_data.checkpoint("twin-1")
    await twin_with_data.checkpoint("twin-1")
    checkpoints = await twin_with_data.list_checkpoints("twin-1")
    assert len(checkpoints) == 2
