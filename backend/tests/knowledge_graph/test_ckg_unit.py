"""Unit tests for Climate Knowledge Graph components."""

from __future__ import annotations

import pytest

from backend.knowledge_graph import (
    EntityType,
    FloodEntity,
    GraphEngine,
    GraphRelationship,
    GraphSerializer,
    GraphValidator,
    RelationshipType,
    SpecializedAgentEntity,
    create_entity,
    is_valid_relationship,
)


@pytest.mark.asyncio
async def test_create_entity_factory() -> None:
    entity = create_entity(EntityType.FLOOD, name="Test Flood", region_id="test")
    assert entity.entity_type == EntityType.FLOOD
    assert entity.name == "Test Flood"


@pytest.mark.asyncio
async def test_graph_add_entity_and_relationship(graph_engine: GraphEngine) -> None:
    flood = await graph_engine.add_entity(FloodEntity(
        entity_id="flood_test",
        name="Test Flood",
        region_id="chennai",
        peak_depth_m=1.2,
    ))
    agent = await graph_engine.add_entity(SpecializedAgentEntity(
        entity_id="agent_test",
        name="Test Agent",
        agent_id="test_agent",
    ))
    rel = await graph_engine.link(
        agent.entity_id,
        flood.entity_id,
        RelationshipType.SUPPORTS,
    )
    assert rel.relationship_type == RelationshipType.SUPPORTS
    assert graph_engine.entity_count == 2
    assert graph_engine.relationship_count == 1


@pytest.mark.asyncio
async def test_schema_relationship_validation() -> None:
    assert is_valid_relationship(EntityType.RAINFALL, RelationshipType.CAUSES, EntityType.FLOOD)
    assert not is_valid_relationship(EntityType.RAINFALL, RelationshipType.CAUSES, EntityType.HOSPITAL)


@pytest.mark.asyncio
async def test_graph_validator_entity() -> None:
    validator = GraphValidator()
    result = validator.validate_entity(FloodEntity(name="", region_id="x"))
    assert result.valid is False
    assert any("name" in (i.field or "") for i in result.errors)


@pytest.mark.asyncio
async def test_graph_validator_self_reference(graph_engine: GraphEngine) -> None:
    entity = await graph_engine.add_entity(FloodEntity(entity_id="f1", name="F1"))
    validator = GraphValidator()
    rel = GraphRelationship(source_id="f1", target_id="f1", relationship_type=RelationshipType.AFFECTS)
    result = validator.validate_relationship(rel, entity, entity)
    assert result.valid is False


@pytest.mark.asyncio
async def test_graph_serializer_roundtrip(graph_engine: GraphEngine) -> None:
    await graph_engine.add_entity(FloodEntity(entity_id="flood_ser", name="Serialize Flood", year=2020))
    snapshot = await graph_engine.export_snapshot()
    serializer = GraphSerializer()
    entities, relationships = serializer.import_snapshot(snapshot)
    assert len(entities) == 1
    assert entities[0].entity_id == "flood_ser"


@pytest.mark.asyncio
async def test_remove_entity(graph_engine: GraphEngine) -> None:
    entity = await graph_engine.add_entity(FloodEntity(entity_id="temp", name="Temp"))
    assert await graph_engine.remove_entity(entity.entity_id) is True
    assert await graph_engine.get_entity(entity.entity_id) is None
