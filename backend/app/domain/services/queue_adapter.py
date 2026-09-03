"""Domain contract for background job queues."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class Job:
    """A queue job claimable by one worker at a time."""

    id: UUID
    job_type: str
    payload: dict[str, Any]


class QueueAdapter(ABC):
    """Abstract queue contract used by application and worker layers."""

    @abstractmethod
    async def publish(self, job_type: str, payload: dict[str, Any]) -> Job:
        """Publish a job and return its queue identity."""
        raise NotImplementedError

    @abstractmethod
    async def claim(self) -> Job | None:
        """Claim one pending job, or return None when the queue is empty."""
        raise NotImplementedError

    @abstractmethod
    async def ack(self, job_id: UUID) -> None:
        """Permanently remove a claimed job."""
        raise NotImplementedError

    @abstractmethod
    async def nack(self, job_id: UUID) -> None:
        """Return a claimed job to the pending queue for retry."""
        raise NotImplementedError
