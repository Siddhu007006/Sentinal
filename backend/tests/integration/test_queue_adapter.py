from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.infrastructure.queue.redis_queue import CeleryRedisQueueAdapter


@pytest.mark.asyncio
async def test_published_job_is_claimed_once_and_acked() -> None:
    redis = Redis.from_url(
        "redis://localhost:6379/15",
        decode_responses=True,
    )
    queue_name = f"test:queue:{uuid4()}"
    first = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )
    second = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=queue_name,
    )

    try:
        await redis.ping()
    except Exception as exc:
        await redis.aclose()
        pytest.skip(f"Redis unavailable: {exc}")

    try:
        published = await first.publish("analysis.requested", {"asset_id": "asset-1"})
        claims = await asyncio.gather(first.claim(), second.claim())
        claimed = [claim for claim in claims if claim is not None]

        assert len(claimed) == 1
        assert claimed[0] == published
        claimer = first if claims[0] is not None else second

        await claimer.ack(published.id)
        assert await first.claim() is None
        assert await redis.llen(queue_name) == 0
    finally:
        await redis.delete(queue_name)
        await redis.aclose()


@pytest.mark.asyncio
async def test_nacked_job_is_retryable() -> None:
    redis = Redis.from_url(
        "redis://localhost:6379/15",
        decode_responses=True,
    )
    queue = CeleryRedisQueueAdapter(
        "redis://localhost:6379/15",
        queue_name=f"test:queue:{uuid4()}",
    )

    try:
        await redis.ping()
    except Exception as exc:
        await redis.aclose()
        pytest.skip(f"Redis unavailable: {exc}")

    try:
        published = await queue.publish("analysis.requested", {"attempt": 1})
        claimed = await queue.claim()
        assert claimed == published

        await queue.nack(published.id)
        retried = await queue.claim()
        assert retried == published
        await queue.ack(published.id)
    finally:
        await redis.delete(queue.queue_name)
        await redis.aclose()
