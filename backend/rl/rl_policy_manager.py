"""Policy lifecycle management for RL optimization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.rl.rl_registry import DEFAULT_ALGORITHM, PolicyMetadata, PolicyStatus, RLAlgorithm, RLRegistry
from backend.config.logger import get_logger

logger = get_logger(__name__)


class PolicyArtifact(BaseModel):
    """Serializable policy artifact for persistence."""

    metadata: PolicyMetadata
    weights: dict[str, Any] = Field(default_factory=dict)
    serialized_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyManager:
    """
    Load, save, version, and switch RL policies.

    Policies are stored as JSON artifacts. Inference uses algorithm-specific
    scoring parameters embedded in the artifact weights.
    """

    def __init__(
        self,
        *,
        registry: RLRegistry | None = None,
        storage_dir: str | Path | None = None,
    ) -> None:
        self._registry = registry or RLRegistry()
        self._storage_dir = Path(storage_dir) if storage_dir else Path(".rl_policies")
        self._artifacts: dict[str, PolicyArtifact] = {}
        self._initialize_defaults()

    @property
    def registry(self) -> RLRegistry:
        return self._registry

    def _initialize_defaults(self) -> None:
        for algorithm in RLAlgorithm:
            policy_id = f"default_{algorithm.value}_v1"
            if self._registry.get(policy_id) is None:
                meta = PolicyMetadata(
                    policy_id=policy_id,
                    name=f"Default {algorithm.value.upper()} Policy",
                    algorithm=algorithm,
                    version="1.0.0",
                    status=PolicyStatus.ACTIVE if algorithm == DEFAULT_ALGORITHM else PolicyStatus.STAGED,
                    description=f"Default inference policy for {algorithm.value}",
                    hyperparameters=self._registry.default_hyperparameters(algorithm),
                )
                artifact = PolicyArtifact(
                    metadata=meta,
                    weights=self._default_weights(algorithm),
                )
                self._registry.register(meta)
                self._artifacts[policy_id] = artifact

        if self._registry.active_policy_id is None:
            default = f"default_{DEFAULT_ALGORITHM.value}_v1"
            self._registry.set_active(default)

    def _default_weights(self, algorithm: RLAlgorithm) -> dict[str, Any]:
        return {
            "algorithm": algorithm.value,
            "exploration_bonus": 0.05 if algorithm == RLAlgorithm.DQN else 0.02,
            "entropy_coef": 0.01 if algorithm in (RLAlgorithm.PPO, RLAlgorithm.A2C) else 0.005,
            "value_baseline": 0.0,
            "temperature": 1.0 if algorithm == RLAlgorithm.SAC else 0.8,
            "cooperation_factor": 1.0 if algorithm == RLAlgorithm.MAPPO else 0.0,
        }

    def get_active_artifact(self) -> PolicyArtifact:
        active_id = self._registry.active_policy_id
        if not active_id or active_id not in self._artifacts:
            raise RuntimeError("No active policy configured")
        return self._artifacts[active_id]

    def get_artifact(self, policy_id: str) -> PolicyArtifact | None:
        return self._artifacts.get(policy_id)

    def switch(self, policy_id: str) -> PolicyMetadata:
        meta = self._registry.set_active(policy_id)
        logger.info("policy_switched", policy_id=policy_id, algorithm=meta.algorithm.value)
        return meta

    def save(self, policy_id: str, *, path: Path | None = None) -> Path:
        artifact = self._artifacts.get(policy_id)
        if artifact is None:
            raise KeyError(f"Policy artifact not found: {policy_id}")

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        target = path or self._storage_dir / f"{policy_id}.json"
        artifact.serialized_at = datetime.now(timezone.utc)
        target.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2), encoding="utf-8")
        logger.info("policy_saved", policy_id=policy_id, path=str(target))
        return target

    def load(self, path: Path) -> PolicyMetadata:
        data = json.loads(path.read_text(encoding="utf-8"))
        artifact = PolicyArtifact.model_validate(data)
        self._registry.register(artifact.metadata)
        self._artifacts[artifact.metadata.policy_id] = artifact
        logger.info("policy_loaded", policy_id=artifact.metadata.policy_id)
        return artifact.metadata

    def create_version(
        self,
        policy_id: str,
        *,
        version: str,
        weights: dict[str, Any] | None = None,
    ) -> PolicyMetadata:
        existing = self._artifacts.get(policy_id)
        if existing is None:
            raise KeyError(f"Policy not found: {policy_id}")

        new_id = f"{policy_id}_v{version.replace('.', '_')}"
        meta = PolicyMetadata(
            policy_id=new_id,
            name=f"{existing.metadata.name} ({version})",
            algorithm=existing.metadata.algorithm,
            version=version,
            status=PolicyStatus.STAGED,
            decision_types=list(existing.metadata.decision_types),
            description=existing.metadata.description,
            hyperparameters=dict(existing.metadata.hyperparameters),
        )
        artifact = PolicyArtifact(
            metadata=meta,
            weights=weights or dict(existing.weights),
        )
        self._registry.register(meta)
        self._artifacts[new_id] = artifact
        return meta

    def list_versions(self, algorithm: RLAlgorithm | None = None) -> list[PolicyMetadata]:
        return self._registry.list_policies(algorithm=algorithm)
