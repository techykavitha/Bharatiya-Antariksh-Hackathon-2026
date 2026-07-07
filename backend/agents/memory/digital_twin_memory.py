"""Digital twin state memory with checkpointing and rollback."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.agents.memory.interfaces import DigitalTwinMemory, MemoryEntry
from backend.agents.memory.memory_cache import AsyncLRUMemoryCache
from backend.agents.memory.memory_types import CheckpointRecord, StateComparisonResult, TwinStateLayer
from backend.agents.memory.serialization import pydantic_to_dict, serialize_value
from backend.utils.errors import MemoryNotFoundError, MemoryWriteError


class DigitalTwinMemoryStore(DigitalTwinMemory):
    """
    Digital twin memory maintaining climate, forecast, simulation, and replay states.

    Supports checkpoint/rollback, clone, compare, and merge operations with
    versioned layer storage.
    """

    def __init__(
        self,
        *,
        cache: AsyncLRUMemoryCache[MemoryEntry] | None = None,
    ) -> None:
        self._twins: dict[str, dict[str, Any]] = {}
        self._checkpoints: dict[str, list[CheckpointRecord]] = {}
        self._versions: dict[str, dict[str, dict[str, Any]]] = {}
        self._cache = cache or AsyncLRUMemoryCache[MemoryEntry](max_size=256)
        self._lock = asyncio.Lock()

    @property
    def backend_name(self) -> str:
        return "digital_twin"

    async def write(self, key: str, value: Any, *, metadata: dict[str, Any] | None = None) -> None:
        twin_id = (metadata or {}).get("twin_id", key)
        layer = (metadata or {}).get("layer", TwinStateLayer.CURRENT_CLIMATE.value)
        async with self._lock:
            twin = self._twins.setdefault(twin_id, self._empty_twin(twin_id))
            twin["layers"][layer] = pydantic_to_dict(value)
            twin["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._cache.delete(f"{twin_id}:{layer}")

    async def read(self, key: str) -> MemoryEntry | None:
        twin_id = key.split(":")[0] if ":" in key else key
        async with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                return None
            return MemoryEntry(key=twin_id, value=twin, metadata={"twin_id": twin_id})

    async def delete(self, key: str) -> bool:
        twin_id = key.split(":")[0] if ":" in key else key
        async with self._lock:
            if twin_id not in self._twins:
                return False
            del self._twins[twin_id]
            self._checkpoints.pop(twin_id, None)
            self._versions.pop(twin_id, None)
        await self._cache.invalidate_prefix(twin_id)
        return True

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        async with self._lock:
            for twin_id, twin in self._twins.items():
                if filters and twin.get("metadata", {}).get("region") != filters.get("region"):
                    continue
                if query_lower in twin_id.lower() or query_lower in serialize_value(twin).lower():
                    results.append(MemoryEntry(key=twin_id, value=twin, metadata=twin.get("metadata", {})))
                if len(results) >= limit:
                    break
        return results

    async def clear(self, namespace: str | None = None) -> int:
        async with self._lock:
            if namespace:
                if namespace in self._twins:
                    del self._twins[namespace]
                    self._checkpoints.pop(namespace, None)
                    self._versions.pop(namespace, None)
                    return 1
                return 0
            count = len(self._twins)
            self._twins.clear()
            self._checkpoints.clear()
            self._versions.clear()
        await self._cache.clear()
        return count

    async def snapshot(self, twin_id: str) -> MemoryEntry:
        async with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                raise MemoryNotFoundError(f"Digital twin '{twin_id}' not found")
            version = str(uuid4())
            snapshot = copy.deepcopy(twin)
            snapshot["version"] = version
            snapshot["captured_at"] = datetime.now(timezone.utc).isoformat()
            versions = self._versions.setdefault(twin_id, {})
            versions[version] = snapshot
            record = CheckpointRecord(
                twin_id=twin_id,
                version=version,
                layers=copy.deepcopy(twin.get("layers", {})),
            )
            self._checkpoints.setdefault(twin_id, []).append(record)
        return MemoryEntry(
            key=f"{twin_id}:{version}",
            value=snapshot,
            metadata={"twin_id": twin_id, "version": version},
        )

    async def restore(self, twin_id: str, version: str) -> MemoryEntry:
        async with self._lock:
            versions = self._versions.get(twin_id, {})
            snapshot = versions.get(version)
            if snapshot is None:
                raise MemoryNotFoundError(
                    f"Version '{version}' not found for twin '{twin_id}'",
                )
            self._twins[twin_id] = copy.deepcopy(snapshot)
        await self._cache.invalidate_prefix(twin_id)
        return MemoryEntry(key=twin_id, value=snapshot, metadata={"version": version})

    async def get_layer(self, twin_id: str, layer_name: str) -> MemoryEntry | None:
        cache_key = f"{twin_id}:{layer_name}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        async with self._lock:
            twin = self._twins.get(twin_id)
            if twin is None:
                return None
            layer_data = twin.get("layers", {}).get(layer_name)
            if layer_data is None:
                return None
            entry = MemoryEntry(
                key=cache_key,
                value=layer_data,
                metadata={"twin_id": twin_id, "layer": layer_name},
            )
        await self._cache.set(cache_key, entry)
        return entry

    async def checkpoint(self, twin_id: str, *, label: str | None = None) -> CheckpointRecord:
        entry = await self.snapshot(twin_id)
        record = CheckpointRecord(
            twin_id=twin_id,
            version=entry.metadata["version"],
            label=label,
            layers=entry.value.get("layers", {}),
        )
        return record

    async def rollback(self, twin_id: str, version: str) -> MemoryEntry:
        return await self.restore(twin_id, version)

    async def clone_state(self, twin_id: str, new_twin_id: str) -> MemoryEntry:
        async with self._lock:
            source = self._twins.get(twin_id)
            if source is None:
                raise MemoryNotFoundError(f"Source twin '{twin_id}' not found")
            clone = copy.deepcopy(source)
            clone["twin_id"] = new_twin_id
            clone["cloned_from"] = twin_id
            clone["created_at"] = datetime.now(timezone.utc).isoformat()
            self._twins[new_twin_id] = clone
        return MemoryEntry(key=new_twin_id, value=clone, metadata={"cloned_from": twin_id})

    async def compare_state(self, twin_id: str, version_a: str, version_b: str) -> StateComparisonResult:
        async with self._lock:
            versions = self._versions.get(twin_id, {})
            state_a = versions.get(version_a)
            state_b = versions.get(version_b)
            if state_a is None or state_b is None:
                raise MemoryNotFoundError(
                    f"Versions not found for twin '{twin_id}'",
                    details={"version_a": version_a, "version_b": version_b},
                )
            layers_a = state_a.get("layers", {})
            layers_b = state_b.get("layers", {})
            changed = [k for k in set(layers_a) | set(layers_b) if layers_a.get(k) != layers_b.get(k)]
            diff = {layer: {"a": layers_a.get(layer), "b": layers_b.get(layer)} for layer in changed}
            return StateComparisonResult(
                twin_id=twin_id,
                version_a=version_a,
                version_b=version_b,
                identical=len(changed) == 0,
                changed_layers=changed,
                diff=diff,
            )

    async def merge_state(
        self,
        twin_id: str,
        other_state: dict[str, Any],
        *,
        strategy: str = "override",
    ) -> MemoryEntry:
        async with self._lock:
            twin = self._twins.setdefault(twin_id, self._empty_twin(twin_id))
            other_layers = other_state.get("layers", other_state)
            for layer_name, layer_data in other_layers.items():
                if strategy == "preserve" and layer_name in twin["layers"]:
                    continue
                if strategy == "deep_merge" and layer_name in twin["layers"]:
                    existing = twin["layers"][layer_name]
                    if isinstance(existing, dict) and isinstance(layer_data, dict):
                        twin["layers"][layer_name] = {**existing, **layer_data}
                        continue
                twin["layers"][layer_name] = copy.deepcopy(layer_data)
            twin["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._cache.invalidate_prefix(twin_id)
        return MemoryEntry(key=twin_id, value=twin, metadata={"twin_id": twin_id})

    async def set_layer(self, twin_id: str, layer: TwinStateLayer, data: Any) -> None:
        await self.write(
            twin_id,
            data,
            metadata={"twin_id": twin_id, "layer": layer.value},
        )

    async def list_checkpoints(self, twin_id: str) -> list[CheckpointRecord]:
        return list(self._checkpoints.get(twin_id, []))

    @staticmethod
    def _empty_twin(twin_id: str) -> dict[str, Any]:
        return {
            "twin_id": twin_id,
            "version": "0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "layers": {
                TwinStateLayer.CURRENT_CLIMATE.value: {},
                TwinStateLayer.PAST_CLIMATE.value: {},
                TwinStateLayer.FORECAST.value: {},
                TwinStateLayer.SIMULATION.value: {},
                TwinStateLayer.HISTORICAL_REPLAY.value: {},
            },
            "metadata": {},
        }
