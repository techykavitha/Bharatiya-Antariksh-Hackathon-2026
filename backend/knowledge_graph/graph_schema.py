"""Climate Knowledge Graph schema definitions and constraints."""

from __future__ import annotations

from enum import StrEnum

from backend.knowledge_graph.entity_models import EntityType
from backend.knowledge_graph.relationship_models import RelationshipType


class GraphSchemaVersion(StrEnum):
    """CKG schema version identifiers."""

    V1 = "1.0"


# Valid source entity -> relationship -> target entity type triples
ENTITY_RELATIONSHIP_CONSTRAINTS: dict[RelationshipType, dict[EntityType, set[EntityType]]] = {
    RelationshipType.CAUSES: {
        EntityType.RAINFALL: {EntityType.FLOOD, EntityType.WEATHER_EVENT},
        EntityType.CYCLONE: {EntityType.FLOOD, EntityType.RAINFALL, EntityType.WEATHER_EVENT},
        EntityType.HEATWAVE: {EntityType.DROUGHT, EntityType.WEATHER_EVENT},
        EntityType.FLOOD: {EntityType.WEATHER_EVENT},
        EntityType.RIVER: {EntityType.FLOOD},
        EntityType.RESERVOIR: {EntityType.FLOOD},
    },
    RelationshipType.AFFECTS: {
        EntityType.FLOOD: {
            EntityType.POPULATION, EntityType.HOSPITAL, EntityType.ROAD,
            EntityType.POWER_GRID, EntityType.AGRICULTURE, EntityType.URBAN_AREA,
            EntityType.DISTRICT, EntityType.RESERVOIR,
        },
        EntityType.HEATWAVE: {
            EntityType.POPULATION, EntityType.HOSPITAL, EntityType.POWER_GRID,
            EntityType.AGRICULTURE, EntityType.URBAN_AREA, EntityType.DISTRICT,
        },
        EntityType.CYCLONE: {
            EntityType.POPULATION, EntityType.ROAD, EntityType.POWER_GRID,
            EntityType.DISTRICT, EntityType.URBAN_AREA,
        },
        EntityType.DROUGHT: {
            EntityType.AGRICULTURE, EntityType.RESERVOIR, EntityType.POPULATION,
            EntityType.RIVER,
        },
        EntityType.RAINFALL: {EntityType.RESERVOIR, EntityType.RIVER, EntityType.AGRICULTURE},
    },
    RelationshipType.DEPENDS_ON: {
        EntityType.POPULATION: {EntityType.HOSPITAL, EntityType.POWER_GRID, EntityType.ROAD},
        EntityType.RESERVOIR: {EntityType.RIVER, EntityType.RAINFALL},
        EntityType.AGRICULTURE: {EntityType.RESERVOIR, EntityType.RIVER, EntityType.RAINFALL},
        EntityType.URBAN_AREA: {EntityType.POWER_GRID, EntityType.RESERVOIR},
        EntityType.SPECIALIZED_AGENT: {
            EntityType.FORECAST, EntityType.SIMULATION, EntityType.DIGITAL_TWIN,
        },
    },
    RelationshipType.LOCATED_IN: {
        EntityType.DISTRICT: {EntityType.STATE},
        EntityType.URBAN_AREA: {EntityType.DISTRICT, EntityType.STATE},
        EntityType.RIVER: {EntityType.DISTRICT, EntityType.STATE},
        EntityType.RESERVOIR: {EntityType.DISTRICT, EntityType.STATE, EntityType.RIVER},
        EntityType.HOSPITAL: {EntityType.DISTRICT, EntityType.URBAN_AREA},
        EntityType.POPULATION: {EntityType.DISTRICT, EntityType.URBAN_AREA},
        EntityType.FOREST: {EntityType.DISTRICT, EntityType.STATE},
        EntityType.AGRICULTURE: {EntityType.DISTRICT, EntityType.STATE},
        EntityType.FLOOD: {EntityType.DISTRICT, EntityType.URBAN_AREA},
        EntityType.HEATWAVE: {EntityType.DISTRICT, EntityType.URBAN_AREA},
        EntityType.CYCLONE: {EntityType.DISTRICT, EntityType.STATE},
    },
    RelationshipType.FEEDS: {
        EntityType.RIVER: {EntityType.RESERVOIR, EntityType.AGRICULTURE, EntityType.URBAN_AREA},
        EntityType.RESERVOIR: {EntityType.URBAN_AREA, EntityType.AGRICULTURE},
        EntityType.RAINFALL: {EntityType.RIVER, EntityType.RESERVOIR},
        EntityType.FORECAST: {EntityType.SPECIALIZED_AGENT, EntityType.SIMULATION},
    },
    RelationshipType.BLOCKS: {
        EntityType.FLOOD: {EntityType.ROAD, EntityType.HOSPITAL},
        EntityType.CYCLONE: {EntityType.ROAD, EntityType.POWER_GRID},
        EntityType.HEATWAVE: {EntityType.ROAD, EntityType.AGRICULTURE},
    },
    RelationshipType.MITIGATES: {
        EntityType.POLICY: {
            EntityType.FLOOD, EntityType.HEATWAVE, EntityType.CYCLONE, EntityType.DROUGHT,
        },
        EntityType.FOREST: {EntityType.HEATWAVE, EntityType.DROUGHT},
        EntityType.RESERVOIR: {EntityType.DROUGHT, EntityType.FLOOD},
        EntityType.SPECIALIZED_AGENT: {
            EntityType.FLOOD, EntityType.HEATWAVE, EntityType.DROUGHT,
        },
    },
    RelationshipType.SUPPORTS: {
        EntityType.SPECIALIZED_AGENT: {
            EntityType.FLOOD, EntityType.HEATWAVE, EntityType.DROUGHT,
            EntityType.RESERVOIR, EntityType.POPULATION,
        },
        EntityType.DIGITAL_TWIN: {
            EntityType.SPECIALIZED_AGENT, EntityType.SIMULATION, EntityType.FORECAST,
        },
        EntityType.FORECAST: {EntityType.SPECIALIZED_AGENT},
        EntityType.SIMULATION: {EntityType.SPECIALIZED_AGENT, EntityType.POLICY},
    },
    RelationshipType.CONNECTED_TO: {
        EntityType.ROAD: {EntityType.URBAN_AREA, EntityType.HOSPITAL, EntityType.DISTRICT},
        EntityType.POWER_GRID: {EntityType.HOSPITAL, EntityType.URBAN_AREA, EntityType.RESERVOIR},
        EntityType.RIVER: {EntityType.RESERVOIR, EntityType.URBAN_AREA},
        EntityType.DIGITAL_TWIN: {EntityType.SIMULATION, EntityType.FORECAST},
    },
    RelationshipType.HISTORICALLY_RELATED: {
        EntityType.FLOOD: {EntityType.FLOOD, EntityType.WEATHER_EVENT},
        EntityType.HEATWAVE: {EntityType.HEATWAVE, EntityType.WEATHER_EVENT},
        EntityType.CYCLONE: {EntityType.CYCLONE, EntityType.WEATHER_EVENT},
        EntityType.DROUGHT: {EntityType.DROUGHT, EntityType.WEATHER_EVENT},
        EntityType.WEATHER_EVENT: {EntityType.FLOOD, EntityType.HEATWAVE, EntityType.CYCLONE},
    },
}


IMPACT_RELATIONSHIPS: set[RelationshipType] = {
    RelationshipType.CAUSES,
    RelationshipType.AFFECTS,
    RelationshipType.BLOCKS,
    RelationshipType.FEEDS,
}

CASCADE_RELATIONSHIPS: set[RelationshipType] = {
    RelationshipType.CAUSES,
    RelationshipType.AFFECTS,
    RelationshipType.BLOCKS,
    RelationshipType.DEPENDS_ON,
}

AGENT_RELATIONSHIPS: set[RelationshipType] = {
    RelationshipType.SUPPORTS,
    RelationshipType.MITIGATES,
    RelationshipType.DEPENDS_ON,
    RelationshipType.AFFECTS,
}

COMPOUND_EVENT_TYPES: set[EntityType] = {
    EntityType.FLOOD,
    EntityType.HEATWAVE,
    EntityType.CYCLONE,
    EntityType.DROUGHT,
}


def is_valid_relationship(
    source_type: EntityType,
    relationship: RelationshipType,
    target_type: EntityType,
) -> bool:
    """Return True when the relationship triple is allowed by schema."""
    allowed_targets = ENTITY_RELATIONSHIP_CONSTRAINTS.get(relationship, {}).get(source_type)
    if allowed_targets is None:
        return True
    return target_type in allowed_targets
