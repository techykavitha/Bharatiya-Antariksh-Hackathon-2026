"""Graph-based reasoning for climate impact inference."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.knowledge_graph.entity_models import ClimateEntity, EntityType
from backend.knowledge_graph.graph_schema import CASCADE_RELATIONSHIPS, COMPOUND_EVENT_TYPES
from backend.knowledge_graph.relationship_models import (
    GraphReasoningResult,
    ReasoningInsight,
    RelationshipType,
)

if TYPE_CHECKING:
    from backend.knowledge_graph.graph_engine import GraphEngine


class GraphReasoningEngine:
    """Infers secondary impacts, cascades, compound disasters, and agent dependencies."""

    INFRASTRUCTURE_TYPES: set[EntityType] = {
        EntityType.HOSPITAL,
        EntityType.ROAD,
        EntityType.POWER_GRID,
        EntityType.RESERVOIR,
    }

    def __init__(self, engine: GraphEngine) -> None:
        self._engine = engine

    async def reason(self, entity_id: str) -> GraphReasoningResult:
        """Run full graph reasoning for an entity."""
        await self._engine._ensure_entity(entity_id)
        secondary = await self.infer_secondary_impacts(entity_id)
        cascading = await self.infer_cascading_failures(entity_id)
        compound = await self.infer_compound_disasters(entity_id)
        agents = await self.infer_multi_agent_dependencies(entity_id)

        self._engine._metrics and self._engine._metrics.record_reasoning()
        summary = (
            f"Inferred {len(secondary)} secondary impacts, "
            f"{len(cascading)} cascading failures, "
            f"{len(compound)} compound disaster risks, "
            f"{len(agents)} agent dependencies"
        )
        return GraphReasoningResult(
            source_entity_id=entity_id,
            secondary_impacts=secondary,
            cascading_failures=cascading,
            compound_disasters=compound,
            agent_dependencies=agents,
            summary=summary,
        )

    async def infer_secondary_impacts(self, entity_id: str) -> list[ReasoningInsight]:
        """Infer downstream impacts two hops from the source."""
        impact = await self._engine.query.impact_chain(
            entity_id,
            max_depth=2,
            relationships={RelationshipType.AFFECTS, RelationshipType.CAUSES},
        )
        insights: list[ReasoningInsight] = []
        for entity in impact.chain:
            if entity.entity_type in self.INFRASTRUCTURE_TYPES:
                category = "infrastructure_impact"
            elif entity.entity_type == EntityType.POPULATION:
                category = "population_impact"
            else:
                category = "secondary_impact"

            insights.append(ReasoningInsight(
                category=category,
                title=f"Secondary impact on {entity.name}",
                description=(
                    f"{entity.entity_type.value} '{entity.name}' may be affected "
                    f"as a downstream consequence"
                ),
                confidence=0.7,
                affected_entity_ids=[entity.entity_id],
                supporting_relationships=[r.relationship_id for r in impact.relationships[:3]],
            ))
        return insights

    async def infer_cascading_failures(self, entity_id: str) -> list[ReasoningInsight]:
        """Infer cascading failures along dependency and block chains."""
        impact = await self._engine.query.impact_chain(
            entity_id,
            max_depth=3,
            relationships=CASCADE_RELATIONSHIPS,
        )
        insights: list[ReasoningInsight] = []
        infra_hits = [e for e in impact.chain if e.entity_type in self.INFRASTRUCTURE_TYPES]

        if len(infra_hits) >= 2:
            insights.append(ReasoningInsight(
                category="cascading_failure",
                title="Multi-infrastructure cascade risk",
                description=(
                    f"Cascade may affect {len(infra_hits)} infrastructure nodes: "
                    f"{', '.join(e.name for e in infra_hits[:4])}"
                ),
                confidence=0.75,
                affected_entity_ids=[e.entity_id for e in infra_hits],
            ))

        blocked = await self._engine.query.neighbors(entity_id, relationship=RelationshipType.BLOCKS, direction="out")
        for neighbor in blocked:
            insights.append(ReasoningInsight(
                category="service_disruption",
                title=f"{neighbor.entity.name} disruption",
                description=f"{neighbor.entity.entity_type.value} may be blocked or degraded",
                confidence=0.8,
                affected_entity_ids=[neighbor.entity.entity_id],
                supporting_relationships=[neighbor.relationship.relationship_id],
            ))

        dependent = await self._engine.query.neighbors(entity_id, relationship=RelationshipType.DEPENDS_ON, direction="in")
        for neighbor in dependent:
            if neighbor.entity.entity_type in self.INFRASTRUCTURE_TYPES:
                insights.append(ReasoningInsight(
                    category="dependency_failure",
                    title=f"{neighbor.entity.name} dependency at risk",
                    description=(
                        f"{neighbor.entity.name} depends on affected resource; "
                        f"failure may propagate"
                    ),
                    confidence=0.65,
                    affected_entity_ids=[neighbor.entity.entity_id],
                ))

        return insights

    async def infer_compound_disasters(self, entity_id: str) -> list[ReasoningInsight]:
        """Detect compound disaster potential from co-occurring event types."""
        source = self._engine._entities[entity_id]
        if source.entity_type not in COMPOUND_EVENT_TYPES:
            return []

        insights: list[ReasoningInsight] = []
        shared_region = source.region_id
        co_occurring: list[ClimateEntity] = []

        for entity in self._engine._entities.values():
            if entity.entity_id == entity_id:
                continue
            if entity.entity_type not in COMPOUND_EVENT_TYPES:
                continue
            if shared_region and entity.region_id == shared_region:
                co_occurring.append(entity)

        if co_occurring:
            types = {source.entity_type.value} | {e.entity_type.value for e in co_occurring}
            insights.append(ReasoningInsight(
                category="compound_disaster",
                title=f"Compound {' + '.join(sorted(types))} risk",
                description=(
                    f"Multiple hazard types active in region {shared_region}: "
                    f"{source.name} with {len(co_occurring)} concurrent events"
                ),
                confidence=0.7,
                affected_entity_ids=[entity_id] + [e.entity_id for e in co_occurring],
                metadata={"hazard_types": list(types), "region_id": shared_region},
            ))

        if source.entity_type == EntityType.HEATWAVE:
            for entity in co_occurring:
                if entity.entity_type == EntityType.DROUGHT:
                    insights.append(ReasoningInsight(
                        category="compound_disaster",
                        title="Heat-drought compound event",
                        description="Concurrent heatwave and drought amplify water and health stress",
                        confidence=0.85,
                        affected_entity_ids=[entity_id, entity.entity_id],
                    ))
                if entity.entity_type == EntityType.FLOOD:
                    insights.append(ReasoningInsight(
                        category="compound_disaster",
                        title="Heat-flood compound event",
                        description="Post-flood humidity may compound heat stress; monitor water quality",
                        confidence=0.6,
                        affected_entity_ids=[entity_id, entity.entity_id],
                    ))

        return insights

    async def infer_multi_agent_dependencies(self, entity_id: str) -> list[ReasoningInsight]:
        """Infer which specialized agents should coordinate for an entity."""
        agent_result = await self._engine.query.affected_agents(entity_id)
        insights: list[ReasoningInsight] = []

        for agent in agent_result.agents:
            agent_id = agent.attributes.get("agent_id") or agent.name
            capabilities = agent.attributes.get("capabilities", agent.tags)
            insights.append(ReasoningInsight(
                category="agent_dependency",
                title=f"Agent coordination: {agent_id}",
                description=(
                    f"Specialized agent '{agent.name}' is connected to this entity "
                    f"and should be consulted"
                ),
                confidence=0.8,
                affected_entity_ids=[agent.entity_id],
                metadata={"agent_id": agent_id, "capabilities": capabilities},
            ))

        if len(agent_result.agents) >= 2:
            names = [a.name for a in agent_result.agents]
            insights.append(ReasoningInsight(
                category="multi_agent_coordination",
                title="Multi-agent response required",
                description=f"Coordinate across agents: {', '.join(names)}",
                confidence=0.75,
                affected_entity_ids=[a.entity_id for a in agent_result.agents],
            ))

        return insights
