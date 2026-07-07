"""Serialization utilities for memory persistence."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class MemoryJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles Pydantic models, datetimes, and enums."""

    def default(self, o: Any) -> Any:
        if isinstance(o, BaseModel):
            return o.model_dump(mode="json")
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, set):
            return list(o)
        return super().default(o)


def serialize_value(value: Any) -> str:
    """Serialize a Python value to a JSON string for Redis/storage."""
    return json.dumps(value, cls=MemoryJSONEncoder, ensure_ascii=False)


def deserialize_value(raw: str | bytes | None) -> Any:
    """Deserialize a JSON string back to a Python value."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def pydantic_to_dict(value: Any) -> Any:
    """Recursively convert Pydantic models to plain dicts."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: pydantic_to_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [pydantic_to_dict(v) for v in value]
    return value
