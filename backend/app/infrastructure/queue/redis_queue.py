"""Celery-over-Redis queue adapter."""

from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from celery import Celery
from kombu import Consumer, Queue  # type: ignore[import-untyped]

from app.domain.services.queue_adapter import Job, QueueAdapter


class CeleryRedisQueueAdapter(QueueAdapter):
    """Manual Celery broker consumer backed by Redis.

    Celery workers normally own acknowledgement. This adapter exposes the
    same lifecycle to the application layer by holding an unacked Kombu
    message until ``ack`` or ``nack`` is called.
    """

    def __init__(
        self,
        broker_url: str,
        *,
        queue_name: str = "sentinel-analysis",
        claim_timeout_seconds: int = 1,
    ) -> None:
        self.app = Celery("sentinel", broker=broker_url)
        self.queue_name = queue_name
        self.claim_timeout_seconds = claim_timeout_seconds
        self._claims: dict[UUID, tuple[Any, Any]] = {}
        self._claims_lock = Lock()

    async def publish(self, job_type: str, payload: dict[str, Any]) -> Job:
        job = Job(id=uuid4(), job_type=job_type, payload=payload)
        await asyncio.to_thread(
            self.app.send_task,
            job_type,
            args=[payload],
            task_id=str(job.id),
            queue=self.queue_name,
            serializer="json",
        )
        return job

    async def claim(self) -> Job | None:
        return await asyncio.to_thread(self._claim_sync)

    async def ack(self, job_id: UUID) -> None:
        await asyncio.to_thread(self._ack_sync, job_id)

    async def nack(self, job_id: UUID) -> None:
        await asyncio.to_thread(self._nack_sync, job_id)

    def _claim_sync(self) -> Job | None:
        connection = self.app.connection_for_read()
        consumer = Consumer(
            connection,
            queues=[Queue(self.queue_name)],
            accept=["json"],
        )
        messages: list[Any] = []
        consumer.register_callback(
            lambda body, message: messages.append((body, message))
        )
        consumer.consume()
        try:
            connection.drain_events(timeout=self.claim_timeout_seconds)
        except TimeoutError:
            consumer.cancel()
            connection.close()
            return None

        body, message = messages[0]
        job_id = UUID(message.headers["id"])
        job = Job(
            id=job_id,
            job_type=message.headers["task"],
            payload=body[0][0],
        )
        with self._claims_lock:
            self._claims[job_id] = (connection, message)
        return job

    def _ack_sync(self, job_id: UUID) -> None:
        claim = self._pop_claim(job_id)
        if claim is None:
            return
        connection, message = claim
        try:
            message.ack()
        finally:
            connection.close()

    def _nack_sync(self, job_id: UUID) -> None:
        claim = self._pop_claim(job_id)
        if claim is None:
            return
        connection, message = claim
        try:
            message.reject(requeue=True)
        finally:
            connection.close()

    def _pop_claim(self, job_id: UUID) -> tuple[Any, Any] | None:
        with self._claims_lock:
            return self._claims.pop(job_id, None)
