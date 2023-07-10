import time

from pytest import mark, raises
from upstash_redis.asyncio import Redis

from tests.utils import random_id
from upstash_ratelimit.asyncio import FixedWindow, Ratelimit


@mark.asyncio()
async def test_invalid_timeout(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=1, window=1),
    )

    with raises(ValueError):
        await ratelimit.block_until_ready(random_id(), -1)


@mark.asyncio()
async def test_resolve_before_timeout(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=5, window=100),
    )

    timeout = 50

    start = time.time()
    response = await ratelimit.block_until_ready(random_id(), timeout)
    elapsed = time.time() - start

    assert elapsed < timeout
    assert response.allowed is True


@mark.asyncio()
async def test_resolve_before_timeout_when_window_resets(
    async_redis: Redis,
) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=1, window=3),
    )

    id = random_id()
    timeout = 100

    await ratelimit.limit(id)

    start = time.time()
    response = await ratelimit.block_until_ready(id, timeout)
    elapsed = time.time() - start

    assert elapsed < timeout
    assert response.allowed is True


@mark.asyncio()
async def test_reaching_timeout(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=1, window=1, unit="d"),
    )

    id = random_id()
    timeout = 2

    await ratelimit.limit(id)

    start = time.time()
    response = await ratelimit.block_until_ready(id, timeout)
    elapsed = time.time() - start

    assert elapsed >= timeout
    assert response.allowed is False
