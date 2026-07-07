"""Serialization utilities for decision requests and responses."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.utils.errors import SchemaValidationError

T = TypeVar("T", bound=BaseModel)


class SerializationFormat:
    """Supported serialization format identifiers."""

    JSON = "json"
    PYDANTIC = "pydantic"
    DATABASE = "database"


class DecisionSerializer:
    """
    Serializes and deserializes decision artifacts across formats.

    Supports JSON (wire format), Pydantic (in-process), and database
    (flat record suitable for persistence layers).
    """

    DB_REQUEST_TABLE = "decision_requests"
    DB_RESPONSE_TABLE = "decision_responses"
    SCHEMA_VERSION = "1.0"

    def to_json(self, model: BaseModel, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(model), indent=indent, default=self._json_default)

    def from_json(self, data: str | bytes, model_cls: type[T]) -> T:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(
                f"Invalid JSON: {exc}",
                details={"error": str(exc)},
            ) from exc
        return self.from_dict(parsed, model_cls)

    def to_dict(self, model: BaseModel) -> dict[str, Any]:
        return model.model_dump(mode="json")

    def from_dict(self, data: dict[str, Any], model_cls: type[T]) -> T:
        try:
            return model_cls.model_validate(data)
        except Exception as exc:
            raise SchemaValidationError(
                f"Failed to validate {model_cls.__name__}: {exc}",
                details={"model": model_cls.__name__},
            ) from exc

    def to_pydantic(self, model: BaseModel) -> BaseModel:
        """Round-trip through dict to produce a clean Pydantic instance."""
        return type(model).model_validate(model.model_dump())

    def request_to_db_record(self, request: DecisionRequest) -> dict[str, Any]:
        """Flatten a decision request for database persistence."""
        now = datetime.now(timezone.utc).isoformat()
        payload = self.to_dict(request)
        return {
            "id": request.decision_id,
            "agent_id": request.agent_id,
            "decision_type": request.decision_type.value,
            "priority": int(request.priority),
            "status": request.status.value,
            "scenario_id": request.context.scenario.scenario_id,
            "climate_state_json": (
                json.dumps(self.to_dict(request.context.climate_state))
                if request.context.climate_state
                else None
            ),
            "forecast_id": request.forecast_reference,
            "simulation_id": request.simulation_reference,
            "objectives_json": json.dumps(payload.get("objectives", [])),
            "constraints_json": json.dumps(payload.get("constraints", {})),
            "actions_json": json.dumps(payload.get("possible_actions", [])),
            "risk_json": json.dumps(payload.get("risk", {})),
            "confidence": request.confidence,
            "expected_reward": request.expected_reward,
            "need_simulation": request.need_simulation,
            "need_other_agents_json": json.dumps(request.need_other_agents),
            "need_human": request.need_human,
            "need_rl": request.need_rl,
            "rationale_json": json.dumps(request.rationale),
            "metadata_json": json.dumps(request.metadata),
            "payload_json": json.dumps(payload),
            "schema_version": self.SCHEMA_VERSION,
            "created_at": request.created_at.isoformat(),
            "updated_at": request.updated_at.isoformat(),
            "record_type": "decision_request",
            "table": self.DB_REQUEST_TABLE,
            "persisted_at": now,
        }

    def request_from_db_record(self, record: dict[str, Any]) -> DecisionRequest:
        if "payload_json" in record:
            payload = record["payload_json"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            return self.from_dict(payload, DecisionRequest)

        reconstructed: dict[str, Any] = {
            "decision_id": record.get("id"),
            "agent_id": record.get("agent_id"),
            "decision_type": record.get("decision_type"),
            "priority": record.get("priority"),
            "status": record.get("status"),
            "confidence": record.get("confidence"),
            "expected_reward": record.get("expected_reward"),
            "need_simulation": record.get("need_simulation", False),
            "need_human": record.get("need_human", False),
            "need_rl": record.get("need_rl", False),
        }
        for field, key in (
            ("objectives", "objectives_json"),
            ("constraints", "constraints_json"),
            ("possible_actions", "actions_json"),
            ("risk", "risk_json"),
            ("rationale", "rationale_json"),
            ("metadata", "metadata_json"),
            ("need_other_agents", "need_other_agents_json"),
        ):
            raw = record.get(key)
            if raw:
                reconstructed[field] = json.loads(raw) if isinstance(raw, str) else raw

        if record.get("climate_state_json"):
            cs = record["climate_state_json"]
            reconstructed.setdefault("context", {})
            reconstructed["context"]["climate_state"] = (
                json.loads(cs) if isinstance(cs, str) else cs
            )

        return self.from_dict(reconstructed, DecisionRequest)

    def response_to_db_record(self, response: DecisionResponse) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload = self.to_dict(response)
        return {
            "id": response.response_id,
            "decision_id": response.decision_id,
            "status": response.status.value,
            "chosen_action_json": (
                json.dumps(self.to_dict(response.chosen_action))
                if response.chosen_action
                else None
            ),
            "ranking_json": json.dumps(payload.get("ranking", [])),
            "reward": response.reward,
            "confidence": response.confidence,
            "reason": response.reason,
            "rejected_actions_json": json.dumps(payload.get("rejected_actions", [])),
            "engine_id": response.engine_id,
            "processing_time_ms": response.processing_time_ms,
            "metadata_json": json.dumps(response.metadata),
            "payload_json": json.dumps(payload),
            "schema_version": self.SCHEMA_VERSION,
            "created_at": response.created_at.isoformat(),
            "record_type": "decision_response",
            "table": self.DB_RESPONSE_TABLE,
            "persisted_at": now,
        }

    def response_from_db_record(self, record: dict[str, Any]) -> DecisionResponse:
        if "payload_json" in record:
            payload = record["payload_json"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            return self.from_dict(payload, DecisionResponse)
        raise SchemaValidationError(
            "Database record missing payload_json",
            details={"record_id": record.get("id")},
        )

    def _json_default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
