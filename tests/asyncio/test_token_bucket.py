import asyncio

from pytest import mark
from upstash_redis.asyncio import Redis

from tests.utils import random_id
from upstash_ratelimit.asyncio import Ratelimit, TokenBucket
from upstash_ratelimit.utils import now_s


@mark.asyncio()
async def test_max_tokens_are_not_reached(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=5, refill_rate=5, interval=1, unit="d"),
    )

    now = now_s()
    response = await ratelimit.limit(random_id())

    assert response.allowed is True
    assert response.limit == 5
    assert response.remaining == 4
    assert response.reset >= now


@mark.asyncio()
async def test_max_tokens_are_reached(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1, refill_rate=1, interval=1, unit="d"),
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
async def test_refill(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1, refill_rate=1, interval=3),
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
async def test_refill_multiple_times(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = await ratelimit.limit(id)

    assert last_response is not None
    last_remaining = last_response.remaining

    await asyncio.sleep(3)

    response = await ratelimit.limit(id)
    assert response.remaining >= last_remaining + 2


@mark.asyncio()
async def test_get_remaining(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=10, refill_rate=10, interval=1, unit="d"),
    )

    id = random_id()
    assert await ratelimit.get_remaining(id) == 10
    await ratelimit.limit(id)
    assert await ratelimit.get_remaining(id) == 9


@mark.asyncio()
async def test_get_remaining_with_refills_that_should_be_made(
    async_redis: Redis,
) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = await ratelimit.limit(id)

    assert last_response is not None
    last_remaining = last_response.remaining

    await asyncio.sleep(3)

    assert await ratelimit.get_remaining(id) >= last_remaining + 2


@mark.asyncio()
async def test_get_reset(async_redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()
    now = now_s()
    await ratelimit.limit(id)

    assert await ratelimit.get_reset(id) >= now + 0.9


@mark.asyncio()
async def test_get_reset_with_refills_that_should_be_made(
    async_redis: Redis,
) -> None:
    ratelimit = Ratelimit(
        redis=async_redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = await ratelimit.limit(id)

    assert last_response is not None
    last_reset = last_response.reset

    await asyncio.sleep(3)

    assert await ratelimit.get_reset(id) >= last_reset + 2
