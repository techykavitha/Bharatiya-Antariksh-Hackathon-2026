"""Training manager interface for future RL model training."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.memory.memory_manager import MemoryManager
from backend.agents.memory.memory_types import MemoryDomain, MemoryStoreRequest
from backend.decision.decision_request import DecisionRequest
from backend.decision.decision_response import DecisionResponse
from backend.rl.rl_registry import RLAlgorithm
from backend.config.logger import get_logger

logger = get_logger(__name__)


class TrainingStatus(StrEnum):
    """Status of a training job."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingEpisode(BaseModel):
    """Recorded episode for future training."""

    episode_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_id: str
    request_snapshot: dict[str, Any] = Field(default_factory=dict)
    response_snapshot: dict[str, Any] = Field(default_factory=dict)
    reward: float = 0.0
    algorithm: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrainingJob(BaseModel):
    """Scheduled training job metadata."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    algorithm: RLAlgorithm
    status: TrainingStatus = TrainingStatus.SCHEDULED
    episode_count: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RLTrainingManager(ABC):
    """Abstract training manager for RL model development."""

    @abstractmethod
    async def record_episode(
        self,
        request: DecisionRequest,
        response: DecisionResponse,
    ) -> TrainingEpisode:
        """Record an inference episode for future training."""

    @abstractmethod
    async def schedule_training(
        self,
        algorithm: RLAlgorithm,
        *,
        config: dict[str, Any] | None = None,
    ) -> TrainingJob:
        """Schedule a training job (not executed in current release)."""

    @abstractmethod
    async def list_episodes(self, *, limit: int = 100) -> list[TrainingEpisode]:
        """List recorded training episodes."""

    @abstractmethod
    async def list_jobs(self) -> list[TrainingJob]:
        """List scheduled training jobs."""


class InMemoryTrainingManager(RLTrainingManager):
    """
    Episode recorder and training job scheduler.

    Does not execute real model training — records episodes to memory
    for future offline training pipelines.
    """

    def __init__(self, *, memory: MemoryManager | None = None) -> None:
        self._memory = memory
        self._episodes: list[TrainingEpisode] = []
        self._jobs: list[TrainingJob] = []

    async def record_episode(
        self,
        request: DecisionRequest,
        response: DecisionResponse,
    ) -> TrainingEpisode:
        episode = TrainingEpisode(
            decision_id=request.decision_id,
            request_snapshot=request.to_rl_payload(),
            response_snapshot=response.model_dump(mode="json"),
            reward=response.reward or 0.0,
            algorithm=response.engine_id.replace("rl_", ""),
        )
        self._episodes.append(episode)

        if self._memory:
            await self._memory.store(
                MemoryStoreRequest(
                    domain=MemoryDomain.WORKING,
                    key=f"rl_episode:{episode.episode_id}",
                    value=episode.model_dump(mode="json"),
                    metadata={"type": "rl_training_episode"},
                ),
            )

        logger.debug("rl_episode_recorded", episode_id=episode.episode_id, reward=episode.reward)
        return episode

    async def schedule_training(
        self,
        algorithm: RLAlgorithm,
        *,
        config: dict[str, Any] | None = None,
    ) -> TrainingJob:
        job = TrainingJob(
            algorithm=algorithm,
            config=config or {},
            episode_count=len(self._episodes),
        )
        self._jobs.append(job)
        logger.info(
            "rl_training_scheduled",
            job_id=job.job_id,
            algorithm=algorithm.value,
            note="Training execution deferred — interface only",
        )
        return job

    async def list_episodes(self, *, limit: int = 100) -> list[TrainingEpisode]:
        return self._episodes[-limit:]

    async def list_jobs(self) -> list[TrainingJob]:
        return list(self._jobs)
