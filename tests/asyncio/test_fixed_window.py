import asyncio
from unittest.mock import patch

from pytest import approx, mark
from upstash_redis.asyncio import Redis

from tests.utils import random_id
from upstash_ratelimit.asyncio import FixedWindow, Ratelimit
from upstash_ratelimit.utils import now_s


@mark.asyncio()
async def test_max_requests_are_not_reached(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=5, window=10),
    )

    now = now_s()
    response = await ratelimit.limit(random_id())

    assert response.allowed is True
    assert response.limit == 5
    assert response.remaining == 4
    assert response.reset >= now


@mark.asyncio()
async def test_max_requests_are_reached(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=1, window=1, unit="d"),
    )

    id = random_id()

    await ratelimit.limit(id)

    now = now_s()
    response = await ratelimit.limit(id)

    assert response.allowed is False
    assert response.limit == 1
    assert response.remaining == 0
    assert response.reset >= now


@mark.asyncio()
async def test_window_reset(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=1, window=3),
    )

    id = random_id()

    await ratelimit.limit(id)

    await asyncio.sleep(3)

    now = now_s()
    response = await ratelimit.limit(id)

    assert response.allowed is True
    assert response.limit == 1
    assert response.remaining == 0
    assert response.reset >= now


@mark.asyncio()
async def test_get_remaining(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=10, window=1, unit="d"),
    )

    id = random_id()
    assert await ratelimit.get_remaining(id) == 10
    await ratelimit.limit(id)
    assert await ratelimit.get_remaining(id) == 9


@mark.asyncio()
async def test_get_reset(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=FixedWindow(max_requests=10, window=5),
    )

    with patch("time.time", return_value=1688910786.167):
        assert await ratelimit.get_reset(random_id()) == approx(1688910790.0)
