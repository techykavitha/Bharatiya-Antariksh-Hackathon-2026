# Simulation Engine

> **Status:** ⬜ Not Started  
> **Version:** —  
> **Last Updated:** 2026-07-07

---

## Purpose

The Simulation Engine will integrate climate models (including Prithvi WxC APIs) to run what-if scenarios, generate forecasts, and feed results into the digital twin memory store.

---

## Current State

No simulation engine implementation exists. Related infrastructure:

| Component | Status |
|-----------|--------|
| `ClimateState` model | ✅ Defined |
| `DigitalTwinMemoryStore` | ✅ Implemented (in-process) |
| `DigitalTwinInterface` | ✅ Protocol defined |
| `SimulationStatus` enum | ✅ Defined |
| `ScenarioType` enum | ✅ Defined |
| Prithvi WxC integration | ⬜ Not started |
| PostGIS persistence | ⬜ Not started |

### DigitalTwinInterface Methods (Defined)

| Method | Description |
|--------|-------------|
| `get_twin_state(twin_id)` | Retrieve current twin state |
| `update_twin_state(twin_id, updates)` | Apply state updates |
| `create_twin_scenario(twin_id, scenario)` | Create new scenario |
| `compare_twin_scenarios(twin_id, a, b)` | Compare scenarios |

---

## Planned Architecture

```
ClimateSupervisor
    └── DigitalTwinInterface
            └── SimulationEngine (planned)
                    ├── PrithviWxCAdapter
                    ├── ScenarioRunner
                    ├── PostGISStore
                    └── TwinStateManager
```

---

## Dependencies

| Dependency | Status |
|------------|--------|
| Prithvi WxC API access | ⬜ Not configured |
| PostGIS / PostgreSQL | ⬜ Not in requirements.txt |
| Digital twin persistence | ⬜ In-process only |
| Geospatial data pipeline | ⬜ Not started |

---

## Related Documents

- [Shared Memory](../memory/shared_memory.md)
- [State Management](../architecture/state_management.md)
- [Progress Tracker](../engineering/progress_tracker.md)
