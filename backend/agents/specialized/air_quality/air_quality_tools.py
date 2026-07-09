"""Dedicated tools for atmospheric pollution and air quality analysis."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from backend.agents.specialized.air_quality.air_quality_context import AirQualityInputs
from backend.agents.specialized.air_quality.air_quality_models import (
    PM10_BREAKPOINTS,
    PM25_BREAKPOINTS,
    AQICategory,
    PollutantType,
    PollutionSourceType,
)
from backend.agents.tools.abstract_tool import AbstractTool, ToolInput
from backend.utils.enums import ToolCategory
from backend.utils.errors import ToolValidationError


def _extract_inputs(tool_input: ToolInput) -> AirQualityInputs:
    ctx = {**tool_input.context, **tool_input.parameters}
    return AirQualityInputs.from_request_context(ctx)


def _region(tool_input: ToolInput) -> str:
    return _extract_inputs(tool_input).region_id or "unknown_region"


def _schema(*properties: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {name: {"type": "number"} for name in properties},
    }


def _sub_index(concentration: float, breakpoints: list[tuple[float, float, int, int]]) -> int:
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= concentration <= c_high:
            return round(
                (i_high - i_low) / (c_high - c_low) * (concentration - c_low) + i_low,
            )
    return 500


def _aqi_category(aqi: int) -> AQICategory:
    if aqi <= 50:
        return AQICategory.GOOD
    if aqi <= 100:
        return AQICategory.SATISFACTORY
    if aqi <= 200:
        return AQICategory.MODERATE
    if aqi <= 300:
        return AQICategory.POOR
    if aqi <= 400:
        return AQICategory.VERY_POOR
    if aqi <= 500:
        return AQICategory.SEVERE
    return AQICategory.HAZARDOUS


class AQITool(AbstractTool):
    """Computes composite Air Quality Index from pollutant concentrations."""

    @property
    def name(self) -> str:
        return "aqi_tool"

    @property
    def description(self) -> str:
        return "Compute composite AQI and dominant pollutant from concentration data"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("pm2_5", "pm10", "no2", "so2", "o3", "co")

    def validate_input(self, tool_input: ToolInput) -> None:
        super().validate_input(tool_input)
        inputs = _extract_inputs(tool_input)
        if not inputs.pollutants:
            raise ToolValidationError(
                "AQI tool requires at least one pollutant concentration",
                details={"tool": self.name},
            )

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        p = inputs.pollutants
        pm25 = float(p.get("pm2_5", 0.0))
        pm10 = float(p.get("pm10", 0.0))
        no2 = float(p.get("no2", 0.0))
        so2 = float(p.get("so2", 0.0))
        o3 = float(p.get("o3", 0.0))
        co = float(p.get("co", 0.0))

        indices = {
            PollutantType.PM25.value: _sub_index(pm25, PM25_BREAKPOINTS),
            PollutantType.PM10.value: _sub_index(pm10, PM10_BREAKPOINTS),
            PollutantType.NO2.value: min(int(no2 * 1.2), 500),
            PollutantType.SO2.value: min(int(so2 * 1.5), 500),
            PollutantType.O3.value: min(int(o3 * 1.1), 500),
            PollutantType.CO.value: min(int(co * 0.8), 500),
        }
        dominant = max(indices, key=indices.get)  # type: ignore[arg-type]
        aqi = indices[dominant]
        category = _aqi_category(aqi)

        return {
            "region": _region(tool_input),
            "aqi": aqi,
            "category": category.value,
            "dominant_pollutant": dominant,
            "sub_indices": indices,
            "severe_aqi": aqi >= 301,
            "hazardous_aqi": aqi > 400,
            "aqi_score": round(min(aqi / 500.0, 1.0), 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class PMTool(AbstractTool):
    """Analyzes particulate matter PM2.5 and PM10."""

    @property
    def name(self) -> str:
        return "pm_tool"

    @property
    def description(self) -> str:
        return "Analyze PM2.5 and PM10 concentrations, ratios, and exceedance"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("pm2_5", "pm10")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        pm25 = float(inputs.pollutants.get("pm2_5", 0.0))
        pm10 = float(inputs.pollutants.get("pm10", 0.0))
        ratio = pm25 / pm10 if pm10 > 0 else 0.0
        coarse_dominant = ratio < 0.4 and pm10 > 150
        fine_dominant = ratio > 0.65 and pm25 > 60
        dust_indicator = ratio < 0.35 and pm10 > 200
        biomass_indicator = ratio >= 0.65 and pm25 > 80

        return {
            "region": _region(tool_input),
            "pm2_5_ug_m3": pm25,
            "pm10_ug_m3": pm10,
            "pm25_pm10_ratio": round(ratio, 3),
            "pm25_exceedance": pm25 > 60,
            "pm10_exceedance": pm10 > 100,
            "coarse_dominant": coarse_dominant,
            "fine_dominant": fine_dominant,
            "dust_indicator": dust_indicator,
            "biomass_burning_indicator": biomass_indicator,
            "pm25_score": round(min(pm25 / 250.0, 1.0), 3),
            "pm10_score": round(min(pm10 / 430.0, 1.0), 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class GasConcentrationTool(AbstractTool):
    """Analyzes gaseous pollutant concentrations (NO₂, SO₂, O₃, CO)."""

    @property
    def name(self) -> str:
        return "gas_concentration_tool"

    @property
    def description(self) -> str:
        return "Analyze NO2, SO2, O3, and CO concentrations and photochemical potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("no2", "so2", "o3", "co")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        no2 = float(inputs.pollutants.get("no2", 0.0))
        so2 = float(inputs.pollutants.get("so2", 0.0))
        o3 = float(inputs.pollutants.get("o3", 0.0))
        co = float(inputs.pollutants.get("co", 0.0))
        temp = inputs.meteorology.temperature_c or 30.0
        ozone_formation = o3 > 80 and temp > 32 and (inputs.meteorology.humidity_pct or 50) < 60
        industrial = no2 > 60 or so2 > 40

        return {
            "region": _region(tool_input),
            "no2_ug_m3": no2,
            "so2_ug_m3": so2,
            "o3_ug_m3": o3,
            "co_ug_m3": co,
            "ozone_formation_likely": ozone_formation,
            "industrial_gas_signature": industrial,
            "traffic_signature": no2 > 40 and so2 < 30,
            "gas_risk_score": round(min((no2 + so2 + o3) / 300.0, 1.0), 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class WindTool(AbstractTool):
    """Analyzes wind fields for pollution transport and dispersion."""

    @property
    def name(self) -> str:
        return "wind_tool"

    @property
    def description(self) -> str:
        return "Assess wind speed, direction, and transport potential"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("wind_speed_ms", "wind_direction_deg")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        speed = inputs.meteorology.wind_speed_ms
        direction = inputs.meteorology.wind_direction_deg
        calm = speed < 1.5
        strong = speed > 6.0
        transport_potential = min(speed / 8.0, 1.0) if not calm else 0.1
        stagnation = calm and inputs.meteorology.inversion_present

        return {
            "region": _region(tool_input),
            "wind_speed_ms": speed,
            "wind_direction_deg": direction,
            "calm_conditions": calm,
            "strong_wind": strong,
            "stagnation": stagnation,
            "transport_potential": round(transport_potential, 3),
            "dispersion_favorable": speed >= 2.5 and not inputs.meteorology.inversion_present,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class ForecastTool(AbstractTool):
    """Air quality and meteorological forecast analysis."""

    @property
    def name(self) -> str:
        return "forecast_tool"

    @property
    def description(self) -> str:
        return "Analyze forecast meteorology and projected AQI trends"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PREDICTION

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("forecast_aqi_24h", "forecast_aqi_72h", "forecast_wind_speed_ms")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        current_aqi = int(tool_input.parameters.get("aqi", tool_input.context.get("aqi", 0)))
        if not current_aqi and inputs.pollutants:
            pm25 = float(inputs.pollutants.get("pm2_5", 0.0))
            current_aqi = _sub_index(pm25, PM25_BREAKPOINTS)

        f24 = int(tool_input.parameters.get("forecast_aqi_24h", tool_input.context.get("forecast_aqi_24h", 0)))
        f72 = int(tool_input.parameters.get("forecast_aqi_72h", tool_input.context.get("forecast_aqi_72h", 0)))
        if not f24:
            wind = inputs.meteorology.forecast_wind_speed_ms or inputs.meteorology.wind_speed_ms
            delta = -15 if (wind or 0) > 4 else 10 if inputs.meteorology.inversion_present else 5
            f24 = max(current_aqi + delta, 0)
        if not f72:
            f72 = f24 + (5 if inputs.meteorology.inversion_present else -5)

        deteriorating = f24 > current_aqi * 1.05 or f72 > f24 * 1.05
        improving = f72 < current_aqi * 0.9

        return {
            "region": _region(tool_input),
            "current_aqi": current_aqi,
            "forecast_aqi_24h": f24,
            "forecast_aqi_72h": f72,
            "deteriorating_trend": deteriorating,
            "improving_trend": improving,
            "persistence_likely": deteriorating and inputs.meteorology.inversion_present,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class EmissionTool(AbstractTool):
    """Regional emission inventory analysis."""

    @property
    def name(self) -> str:
        return "emission_tool"

    @property
    def description(self) -> str:
        return "Analyze emission source inventory and hotspot attribution"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "traffic_share_pct": {"type": "number"},
                "industrial_share_pct": {"type": "number"},
                "biomass_burning_share_pct": {"type": "number"},
            },
        }

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        e = inputs.emissions
        shares = {
            PollutionSourceType.TRAFFIC.value: e.traffic_share_pct,
            PollutionSourceType.INDUSTRIAL.value: e.industrial_share_pct,
            PollutionSourceType.BIOMASS_BURNING.value: e.biomass_burning_share_pct,
            PollutionSourceType.DUST.value: e.dust_share_pct,
            PollutionSourceType.CONSTRUCTION.value: e.construction_share_pct,
        }
        dominant = max(shares, key=shares.get)  # type: ignore[arg-type]
        if e.dominant_source != PollutionSourceType.UNKNOWN:
            dominant = e.dominant_source.value

        return {
            "region": _region(tool_input),
            "source_shares": shares,
            "dominant_source": dominant,
            "biomass_burning_significant": e.biomass_burning_share_pct >= 25.0,
            "industrial_hotspot": e.industrial_share_pct >= 30.0,
            "traffic_hotspot": e.traffic_share_pct >= 35.0,
            "dust_significant": e.dust_share_pct >= 30.0,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class SatelliteAerosolTool(AbstractTool):
    """Satellite aerosol optical depth and fire/smoke detection."""

    @property
    def name(self) -> str:
        return "satellite_aerosol_tool"

    @property
    def description(self) -> str:
        return "Analyze satellite AOD, fire hotspots, and smoke/dust plumes"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("aod_550", "fire_hotspot_count", "biomass_burning_index")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        sat = inputs.satellite
        high_aod = sat.aod_550 >= 0.6
        active_fires = sat.fire_hotspot_count >= 5
        smoke = sat.smoke_plume_detected or (active_fires and sat.biomass_burning_index > 0.5)
        dust = sat.dust_plume_detected or (sat.aod_550 > 0.8 and not active_fires)

        return {
            "region": _region(tool_input),
            "aod_550": sat.aod_550,
            "fire_hotspot_count": sat.fire_hotspot_count,
            "biomass_burning_index": sat.biomass_burning_index,
            "high_aod": high_aod,
            "smoke_plume_detected": smoke,
            "dust_plume_detected": dust,
            "wildfire_smoke_risk": smoke and sat.biomass_burning_index > 0.6,
            "aerosol_score": round(min(sat.aod_550 / 2.0, 1.0), 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class HealthRiskTool(AbstractTool):
    """Population health risk assessment from air pollution exposure."""

    @property
    def name(self) -> str:
        return "health_risk_tool"

    @property
    def description(self) -> str:
        return "Quantify respiratory and cardiovascular health risks from AQI exposure"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("aqi", "population_total", "sensitive_population_pct")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        aqi = int(tool_input.parameters.get("aqi", tool_input.context.get("aqi", 0)))
        if not aqi and inputs.pollutants:
            pm25 = float(inputs.pollutants.get("pm2_5", 0.0))
            aqi = _sub_index(pm25, PM25_BREAKPOINTS)

        pop = inputs.population_total or int(inputs.population_density * 10)
        sensitive_pct = inputs.sensitive_population_pct
        risk_score = min(aqi / 400.0, 1.0)
        respiratory = min(pm25_risk := float(inputs.pollutants.get("pm2_5", 0)) / 200.0, 1.0)
        cardiovascular = min(risk_score * 0.85 + (inputs.pollutants.get("no2", 0) / 100.0) * 0.15, 1.0)
        exposed = int(pop * min(risk_score + 0.2, 1.0))
        sensitive = int(pop * sensitive_pct / 100.0)

        if aqi >= 400:
            level = "critical"
        elif aqi >= 301:
            level = "severe"
        elif aqi >= 201:
            level = "high"
        elif aqi >= 101:
            level = "moderate"
        else:
            level = "low"

        return {
            "region": _region(tool_input),
            "health_risk_level": level,
            "health_risk_score": round(risk_score, 3),
            "respiratory_risk": round(respiratory, 3),
            "cardiovascular_risk": round(cardiovascular, 3),
            "exposed_population": exposed,
            "sensitive_population": sensitive,
            "hospital_admission_risk_pct": round(risk_score * 12.0, 1),
            "vulnerable_groups": self._vulnerable_groups(aqi),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    def _vulnerable_groups(self, aqi: int) -> list[str]:
        groups = ["children", "elderly", "asthmatics"]
        if aqi >= 201:
            groups.append("outdoor_workers")
        if aqi >= 301:
            groups.extend(["pregnant_women", "cardiac_patients"])
        return groups


class DigitalTwinTool(AbstractTool):
    """Digital twin air quality layer integration."""

    @property
    def name(self) -> str:
        return "digital_twin_tool"

    @property
    def description(self) -> str:
        return "Retrieve air quality state from digital twin layers"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTEGRATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"twin_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        twin_state = tool_input.parameters.get("digital_twin_state") or tool_input.context.get("digital_twin_state", {})
        layers = twin_state.get("layers", {}) if isinstance(twin_state, dict) else {}
        aq_layer = layers.get("air_quality", layers.get("atmospheric", {}))
        if not isinstance(aq_layer, dict):
            aq_layer = {}

        return {
            "region": _region(tool_input),
            "twin_id": inputs.twin_id or twin_state.get("twin_id", "unknown"),
            "twin_available": bool(twin_state),
            "aqi_from_twin": aq_layer.get("aqi"),
            "pollution_hotspots": aq_layer.get("hotspots", []),
            "emission_sources_mapped": aq_layer.get("emission_sources", []),
            "layer_status": aq_layer.get("status", "unknown"),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class KnowledgeGraphTool(AbstractTool):
    """Climate Knowledge Graph query for pollution context."""

    @property
    def name(self) -> str:
        return "knowledge_graph_tool"

    @property
    def description(self) -> str:
        return "Query CKG for emission sources, historical pollution, and compound hazards"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTEGRATION

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"region_id": {"type": "string"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        ckg = tool_input.parameters.get("ckg_insights") or tool_input.context.get("ckg_insights", {})
        if not isinstance(ckg, dict):
            ckg = {}

        return {
            "region": _region(tool_input),
            "emission_sources": ckg.get("emission_sources", []),
            "historical_pollution": ckg.get("historical_pollution", []),
            "population_nodes": ckg.get("population_nodes", []),
            "compound_hazards": ckg.get("compound_hazards", []),
            "query_count": ckg.get("query_count", 0),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class PopulationTool(AbstractTool):
    """Population density and exposure zone analysis."""

    @property
    def name(self) -> str:
        return "population_tool"

    @property
    def description(self) -> str:
        return "Assess population density and exposure zones for air pollution"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return _schema("population_total", "population_density")

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        pop = inputs.population_total
        density = inputs.population_density
        high_density = density > 15000 or pop > 5_000_000
        exposure_zones = inputs.districts[:3] if inputs.districts else []

        return {
            "region": _region(tool_input),
            "population_total": pop,
            "population_density": density,
            "high_density_area": high_density,
            "exposure_zones": exposure_zones,
            "exposure_score": round(min(density / 20000.0, 1.0) if density else min(pop / 10_000_000, 1.0), 3),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


class HistoricalAQITool(AbstractTool):
    """Historical AQI trend and anomaly detection."""

    @property
    def name(self) -> str:
        return "historical_aqi_tool"

    @property
    def description(self) -> str:
        return "Analyze historical AQI trends, anomalies, and seasonal patterns"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    def get_input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"historical_aqi": {"type": "array"}}}

    async def _execute(self, tool_input: ToolInput) -> dict[str, Any]:
        inputs = _extract_inputs(tool_input)
        history = inputs.historical_aqi
        if not history:
            return {
                "region": _region(tool_input),
                "history_available": False,
                "mean_aqi": 0,
                "max_aqi": 0,
                "trend": "unknown",
                "anomaly_detected": False,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

        mean_aqi = sum(history) / len(history)
        max_aqi = max(history)
        current = history[-1] if history else 0
        trend = "rising" if len(history) >= 2 and history[-1] > history[-2] else "falling"
        anomaly = current > mean_aqi * 1.4

        return {
            "region": _region(tool_input),
            "history_available": True,
            "mean_aqi": round(mean_aqi, 1),
            "max_aqi": max_aqi,
            "current_aqi": current,
            "trend": trend,
            "anomaly_detected": anomaly,
            "severe_episode_count": sum(1 for v in history if v >= 301),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def create_air_quality_tools() -> list[AbstractTool]:
    return [
        AQITool(),
        PMTool(),
        GasConcentrationTool(),
        WindTool(),
        ForecastTool(),
        EmissionTool(),
        SatelliteAerosolTool(),
        HealthRiskTool(),
        DigitalTwinTool(),
        KnowledgeGraphTool(),
        PopulationTool(),
        HistoricalAQITool(),
    ]


ALL_AIR_QUALITY_TOOL_NAMES = [t().name for t in (
    AQITool, PMTool, GasConcentrationTool, WindTool, ForecastTool,
    EmissionTool, SatelliteAerosolTool, HealthRiskTool, DigitalTwinTool,
    KnowledgeGraphTool, PopulationTool, HistoricalAQITool,
)]
