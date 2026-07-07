"""Climate Knowledge Graph builder with India domain seed data."""

from __future__ import annotations

from backend.knowledge_graph.entity_models import (
    AgricultureEntity,
    DistrictEntity,
    FloodEntity,
    ForecastEntity,
    HeatwaveEntity,
    HospitalEntity,
    PopulationEntity,
    PowerGridEntity,
    ReservoirEntity,
    RiverEntity,
    SpecializedAgentEntity,
    StateEntity,
    UrbanAreaEntity,
    DigitalTwinEntity,
    RainfallEntity,
)
from backend.knowledge_graph.graph_engine import GraphEngine
from backend.knowledge_graph.relationship_models import RelationshipType


class ClimateGraphBuilder:
    """Builds and seeds the Climate Knowledge Graph."""

    def __init__(self, engine: GraphEngine) -> None:
        self._engine = engine

    async def build_india_climate_graph(self) -> GraphEngine:
        """Seed CKG with India climate domain entities and relationships."""
        self._engine.start_metrics(operation="build_india_climate_graph")

        # States
        tamil_nadu = await self._engine.add_entity(StateEntity(
            entity_id="state_tamil_nadu",
            name="Tamil Nadu",
            region_id="tamil_nadu",
            population=72_000_000,
        ))
        delhi = await self._engine.add_entity(StateEntity(
            entity_id="state_delhi",
            name="Delhi",
            region_id="delhi",
            population=20_000_000,
        ))
        gujarat = await self._engine.add_entity(StateEntity(
            entity_id="state_gujarat",
            name="Gujarat",
            region_id="gujarat",
            population=70_000_000,
        ))

        # Districts / urban areas
        chennai = await self._engine.add_entity(DistrictEntity(
            entity_id="district_chennai",
            name="Chennai",
            region_id="chennai",
            state_code="TN",
            population=7_000_000,
            latitude=13.0827,
            longitude=80.2707,
        ))
        delhi_central = await self._engine.add_entity(DistrictEntity(
            entity_id="district_delhi_central",
            name="Central Delhi",
            region_id="delhi",
            state_code="DL",
            population=2_000_000,
            latitude=28.6139,
            longitude=77.2090,
        ))
        ahmedabad = await self._engine.add_entity(UrbanAreaEntity(
            entity_id="urban_ahmedabad",
            name="Ahmedabad",
            region_id="ahmedabad",
            latitude=23.0225,
            longitude=72.5714,
            urban_density=0.92,
            impervious_fraction=0.68,
        ))

        # Rivers and reservoirs
        cooum = await self._engine.add_entity(RiverEntity(
            entity_id="river_cooum",
            name="Cooum River",
            region_id="chennai",
            length_km=72.0,
            discharge_m3s=45.0,
            bank_level_m=4.5,
        ))
        krishna = await self._engine.add_entity(RiverEntity(
            entity_id="river_krishna",
            name="Krishna River",
            region_id="krishna_basin",
            length_km=1400.0,
            discharge_m3s=1200.0,
        ))
        chembarambakkam = await self._engine.add_entity(ReservoirEntity(
            entity_id="reservoir_chembarambakkam",
            name="Chembarambakkam Reservoir",
            region_id="chennai",
            capacity_mcm=364.0,
            current_level_pct=85.0,
        ))
        nagarjuna_sagar = await self._engine.add_entity(ReservoirEntity(
            entity_id="reservoir_nagarjuna_sagar",
            name="Nagarjuna Sagar",
            region_id="krishna_basin",
            capacity_mcm=8100.0,
            current_level_pct=72.0,
        ))

        # Infrastructure
        chennai_hospitals = await self._engine.add_entity(HospitalEntity(
            entity_id="hospital_chennai_cluster",
            name="Chennai Healthcare Cluster",
            region_id="chennai",
            bed_capacity=15000,
            critical_care_beds=1200,
        ))
        delhi_power = await self._engine.add_entity(PowerGridEntity(
            entity_id="power_grid_delhi",
            name="Delhi Power Grid",
            region_id="delhi",
            capacity_mw=6500.0,
            load_pct=88.0,
        ))
        chennai_power = await self._engine.add_entity(PowerGridEntity(
            entity_id="power_grid_chennai",
            name="Chennai Power Grid",
            region_id="chennai",
            capacity_mw=4200.0,
            load_pct=76.0,
        ))
        chennai_pop = await self._engine.add_entity(PopulationEntity(
            entity_id="population_chennai",
            name="Chennai Metropolitan Population",
            region_id="chennai",
            total=10_900_000,
            vulnerable_fraction=0.22,
        ))
        delhi_pop = await self._engine.add_entity(PopulationEntity(
            entity_id="population_delhi",
            name="Delhi NCR Population",
            region_id="delhi",
            total=19_000_000,
            vulnerable_fraction=0.25,
        ))
        tn_agriculture = await self._engine.add_entity(AgricultureEntity(
            entity_id="agriculture_tn_delta",
            name="Tamil Nadu Delta Agriculture",
            region_id="tamil_nadu",
            crop_area_ha=2_500_000.0,
            primary_crop="paddy",
            irrigation_source="reservoir",
        ))

        # Weather events
        chennai_flood_2015 = await self._engine.add_entity(FloodEntity(
            entity_id="flood_chennai_2015",
            name="Chennai Flood 2015",
            region_id="chennai",
            peak_depth_m=1.8,
            affected_population=50_000,
            year=2015,
            attributes={"rainfall_mm": 490.0},
        ))
        delhi_heatwave_2024 = await self._engine.add_entity(HeatwaveEntity(
            entity_id="heatwave_delhi_2024",
            name="Delhi Heatwave 2024",
            region_id="delhi",
            peak_temp_c=46.8,
            duration_days=9,
            heat_index_c=52.0,
            attributes={"year": 2024},
        ))
        ahmedabad_uhi_2023 = await self._engine.add_entity(HeatwaveEntity(
            entity_id="heatwave_ahmedabad_2023",
            name="Ahmedabad UHI Event 2023",
            region_id="ahmedabad",
            peak_temp_c=44.5,
            duration_days=5,
            attributes={"uhi_intensity_c": 7.0, "year": 2023},
        ))
        heavy_rain_chennai = await self._engine.add_entity(RainfallEntity(
            entity_id="rainfall_chennai_2024",
            name="Chennai Heavy Rainfall Dec 2024",
            region_id="chennai",
            amount_mm=320.0,
            duration_hours=48.0,
            intensity_mm_per_hr=18.0,
        ))

        # Forecast, digital twin, agents
        imd_forecast = await self._engine.add_entity(ForecastEntity(
            entity_id="forecast_imd_gfs",
            name="IMD GFS Forecast",
            region_id="india",
            model_name="imd_gfs",
            horizon_hours=72,
        ))
        twin_chennai = await self._engine.add_entity(DigitalTwinEntity(
            entity_id="twin_chennai_01",
            name="Chennai Digital Twin",
            region_id="chennai",
            twin_id="twin-chennai-01",
            version="1.2.0",
            layers=["flood", "water", "thermal"],
        ))
        twin_delhi = await self._engine.add_entity(DigitalTwinEntity(
            entity_id="twin_delhi_01",
            name="Delhi Digital Twin",
            region_id="delhi",
            twin_id="twin-delhi-01",
            version="1.1.0",
            layers=["thermal", "air_quality"],
        ))

        flood_agent = await self._engine.add_entity(SpecializedAgentEntity(
            entity_id="agent_flood",
            name="Flood Agent",
            agent_id="flood_agent",
            domain="environmental",
            capabilities=["flood_risk_assessment", "river_flood_analysis", "urban_flood_analysis"],
            tags=["flood", "inundation"],
        ))
        heatwave_agent = await self._engine.add_entity(SpecializedAgentEntity(
            entity_id="agent_heatwave",
            name="Heatwave Agent",
            agent_id="heatwave_agent",
            domain="environmental",
            capabilities=["heatwave_detection", "urban_heat_island", "heat_stress_assessment"],
            tags=["heatwave", "thermal"],
        ))
        water_agent = await self._engine.add_entity(SpecializedAgentEntity(
            entity_id="agent_water_resource",
            name="Water Resource Agent",
            agent_id="water_resource_agent",
            domain="environmental",
            capabilities=["reservoir_monitoring", "water_availability_forecast"],
            tags=["water", "reservoir"],
        ))

        # Geographic relationships
        await self._link_many([
            (chennai.entity_id, tamil_nadu.entity_id, RelationshipType.LOCATED_IN),
            (cooum.entity_id, chennai.entity_id, RelationshipType.LOCATED_IN),
            (chembarambakkam.entity_id, chennai.entity_id, RelationshipType.LOCATED_IN),
            (chennai_hospitals.entity_id, chennai.entity_id, RelationshipType.LOCATED_IN),
            (chennai_pop.entity_id, chennai.entity_id, RelationshipType.LOCATED_IN),
            (delhi_central.entity_id, delhi.entity_id, RelationshipType.LOCATED_IN),
            (delhi_power.entity_id, delhi.entity_id, RelationshipType.LOCATED_IN),
            (delhi_pop.entity_id, delhi.entity_id, RelationshipType.LOCATED_IN),
            (ahmedabad.entity_id, gujarat.entity_id, RelationshipType.LOCATED_IN),
            (nagarjuna_sagar.entity_id, krishna.entity_id, RelationshipType.LOCATED_IN),
            (tn_agriculture.entity_id, tamil_nadu.entity_id, RelationshipType.LOCATED_IN),
        ])

        # Hydrological relationships
        await self._link_many([
            (cooum.entity_id, chembarambakkam.entity_id, RelationshipType.FEEDS),
            (krishna.entity_id, nagarjuna_sagar.entity_id, RelationshipType.FEEDS),
            (nagarjuna_sagar.entity_id, tn_agriculture.entity_id, RelationshipType.FEEDS),
            (heavy_rain_chennai.entity_id, cooum.entity_id, RelationshipType.FEEDS),
            (heavy_rain_chennai.entity_id, chembarambakkam.entity_id, RelationshipType.FEEDS),
        ])

        # Causal and impact relationships
        await self._link_many([
            (heavy_rain_chennai.entity_id, chennai_flood_2015.entity_id, RelationshipType.CAUSES),
            (cooum.entity_id, chennai_flood_2015.entity_id, RelationshipType.CAUSES),
            (chennai_flood_2015.entity_id, chennai_pop.entity_id, RelationshipType.AFFECTS),
            (chennai_flood_2015.entity_id, chennai_hospitals.entity_id, RelationshipType.AFFECTS),
            (chennai_flood_2015.entity_id, chembarambakkam.entity_id, RelationshipType.AFFECTS),
            (chennai_flood_2015.entity_id, chennai.entity_id, RelationshipType.AFFECTS),
            (delhi_heatwave_2024.entity_id, delhi_pop.entity_id, RelationshipType.AFFECTS),
            (delhi_heatwave_2024.entity_id, delhi_power.entity_id, RelationshipType.AFFECTS),
            (delhi_heatwave_2024.entity_id, delhi_central.entity_id, RelationshipType.AFFECTS),
            (ahmedabad_uhi_2023.entity_id, ahmedabad.entity_id, RelationshipType.AFFECTS),
            (heavy_rain_chennai.entity_id, chennai_flood_2015.entity_id, RelationshipType.HISTORICALLY_RELATED),
            (delhi_heatwave_2024.entity_id, ahmedabad_uhi_2023.entity_id, RelationshipType.HISTORICALLY_RELATED),
        ])

        # Dependency and cascade
        await self._link_many([
            (chennai_hospitals.entity_id, chennai_power.entity_id, RelationshipType.DEPENDS_ON),
            (chennai_pop.entity_id, chennai_hospitals.entity_id, RelationshipType.DEPENDS_ON),
            (delhi_pop.entity_id, delhi_power.entity_id, RelationshipType.DEPENDS_ON),
            (tn_agriculture.entity_id, nagarjuna_sagar.entity_id, RelationshipType.DEPENDS_ON),
            (chennai_flood_2015.entity_id, chennai_hospitals.entity_id, RelationshipType.BLOCKS),
        ])

        # Agent relationships
        await self._link_many([
            (flood_agent.entity_id, chennai_flood_2015.entity_id, RelationshipType.SUPPORTS),
            (flood_agent.entity_id, heavy_rain_chennai.entity_id, RelationshipType.SUPPORTS),
            (flood_agent.entity_id, chembarambakkam.entity_id, RelationshipType.SUPPORTS),
            (heatwave_agent.entity_id, delhi_heatwave_2024.entity_id, RelationshipType.SUPPORTS),
            (heatwave_agent.entity_id, ahmedabad_uhi_2023.entity_id, RelationshipType.SUPPORTS),
            (heatwave_agent.entity_id, delhi_pop.entity_id, RelationshipType.MITIGATES),
            (water_agent.entity_id, nagarjuna_sagar.entity_id, RelationshipType.SUPPORTS),
            (water_agent.entity_id, chembarambakkam.entity_id, RelationshipType.SUPPORTS),
            (water_agent.entity_id, krishna.entity_id, RelationshipType.SUPPORTS),
            (flood_agent.entity_id, water_agent.entity_id, RelationshipType.CONNECTED_TO),
            (heatwave_agent.entity_id, water_agent.entity_id, RelationshipType.CONNECTED_TO),
            (flood_agent.entity_id, imd_forecast.entity_id, RelationshipType.DEPENDS_ON),
            (heatwave_agent.entity_id, imd_forecast.entity_id, RelationshipType.DEPENDS_ON),
            (water_agent.entity_id, imd_forecast.entity_id, RelationshipType.DEPENDS_ON),
            (twin_chennai.entity_id, flood_agent.entity_id, RelationshipType.SUPPORTS),
            (twin_delhi.entity_id, heatwave_agent.entity_id, RelationshipType.SUPPORTS),
            (imd_forecast.entity_id, flood_agent.entity_id, RelationshipType.FEEDS),
            (imd_forecast.entity_id, heatwave_agent.entity_id, RelationshipType.FEEDS),
        ])

        await self._engine.finalize_metrics()
        return self._engine

    async def _link_many(self, links: list[tuple[str, str, RelationshipType]]) -> None:
        for source_id, target_id, rel_type in links:
            await self._engine.link(source_id, target_id, rel_type)
