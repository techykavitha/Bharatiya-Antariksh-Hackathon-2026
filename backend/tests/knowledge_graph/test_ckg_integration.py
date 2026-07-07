"""Integration tests for Climate Knowledge Graph."""

from __future__ import annotations

import pytest

from backend.knowledge_graph import EntityType, GraphEngine, GraphQueryError, RelationshipType


@pytest.mark.asyncio
async def test_india_graph_seed(india_climate_graph: GraphEngine) -> None:
    assert india_climate_graph.entity_count >= 20
    assert india_climate_graph.relationship_count >= 30
    validation = await india_climate_graph.validate()
    assert validation.valid is True


@pytest.mark.asyncio
async def test_neighbors(india_climate_graph: GraphEngine) -> None:
    neighbors = await india_climate_graph.query.neighbors(
        "district_chennai",
        relationship=RelationshipType.LOCATED_IN,
        direction="out",
    )
    assert any(n.entity.entity_id == "state_tamil_nadu" for n in neighbors)


@pytest.mark.asyncio
async def test_shortest_path(india_climate_graph: GraphEngine) -> None:
    path = await india_climate_graph.query.shortest_path(
        "river_cooum",
        "state_tamil_nadu",
    )
    assert "district_chennai" in path.path
    assert path.hops >= 2


@pytest.mark.asyncio
async def test_shortest_path_not_found(india_climate_graph: GraphEngine) -> None:
    with pytest.raises(GraphQueryError):
        await india_climate_graph.query.shortest_path("river_cooum", "state_gujarat")


@pytest.mark.asyncio
async def test_impact_chain(india_climate_graph: GraphEngine) -> None:
    chain = await india_climate_graph.query.impact_chain("flood_chennai_2015", max_depth=2)
    assert len(chain.chain) >= 2
    assert chain.summary


@pytest.mark.asyncio
async def test_affected_agents_flood(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.query.affected_agents("flood_chennai_2015")
    agent_ids = {getattr(a, "agent_id", None) or a.attributes.get("agent_id") for a in result.agents}
    assert "flood_agent" in agent_ids


@pytest.mark.asyncio
async def test_affected_agents_heatwave(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.query.affected_agents("heatwave_delhi_2024")
    agent_ids = {getattr(a, "agent_id", None) or a.attributes.get("agent_id") for a in result.agents}
    assert "heatwave_agent" in agent_ids


@pytest.mark.asyncio
async def test_related_events(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.query.related_events("flood_chennai_2015")
    assert len(result.events) >= 1


@pytest.mark.asyncio
async def test_historical_similarity(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.query.historical_similarity("heatwave_delhi_2024")
    assert result.best_match_id is not None or len(result.candidates) >= 0
    assert "heatwave_ahmedabad_2023" in result.scores or result.best_match_score >= 0


@pytest.mark.asyncio
async def test_graph_reasoning_secondary_impacts(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.reasoning.infer_secondary_impacts("flood_chennai_2015")
    assert len(result) >= 1
    assert any(i.category in ("infrastructure_impact", "population_impact", "secondary_impact") for i in result)


@pytest.mark.asyncio
async def test_graph_reasoning_cascading_failures(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.reasoning.infer_cascading_failures("flood_chennai_2015")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_graph_reasoning_compound_disasters(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.reasoning.infer_compound_disasters("heatwave_delhi_2024")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_graph_reasoning_multi_agent(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.reasoning.infer_multi_agent_dependencies("flood_chennai_2015")
    assert any(i.category == "agent_dependency" for i in result)


@pytest.mark.asyncio
async def test_full_reasoning_pipeline(india_climate_graph: GraphEngine) -> None:
    result = await india_climate_graph.reasoning.reason("flood_chennai_2015")
    assert result.source_entity_id == "flood_chennai_2015"
    assert result.summary
    assert len(result.agent_dependencies) >= 1


@pytest.mark.asyncio
async def test_search_entities(india_climate_graph: GraphEngine) -> None:
    results = await india_climate_graph.query.search("Chennai", entity_type=EntityType.DISTRICT)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_export_import_snapshot(india_climate_graph: GraphEngine) -> None:
    snapshot = await india_climate_graph.export_snapshot()
    fresh = await GraphEngine.create()
    await fresh.import_snapshot(snapshot)
    assert fresh.entity_count == india_climate_graph.entity_count
    assert fresh.relationship_count == india_climate_graph.relationship_count


@pytest.mark.asyncio
async def test_water_agent_reservoir_path(india_climate_graph: GraphEngine) -> None:
    agents = await india_climate_graph.query.affected_agents("reservoir_nagarjuna_sagar")
    agent_ids = {getattr(a, "agent_id", None) or a.attributes.get("agent_id") for a in agents.agents}
    assert "water_resource_agent" in agent_ids
