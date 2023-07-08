import time

from upstash_redis import Redis

from tests.utils import random_id
from upstash_ratelimit import Ratelimit, TokenBucket
from upstash_ratelimit.utils import now_s


def test_max_tokens_are_not_reached(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=5, refill_rate=5, interval=1, unit="d"),
    )

    now = now_s()
    response = ratelimit.limit(random_id())

    assert response.allowed is True
    assert response.limit == 5
    assert response.remaining == 4
    assert response.reset >= now


def test_max_tokens_are_reached(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1, refill_rate=1, interval=1, unit="d"),
    )

    id = random_id()

    ratelimit.limit(id)

    now = now_s()
    response = ratelimit.limit(id)

    assert response.allowed is False
    assert response.limit == 1
    assert response.remaining == 0
    assert response.reset >= now


def test_refill(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1, refill_rate=1, interval=3),
    )

    id = random_id()

    ratelimit.limit(id)

    time.sleep(3)

    now = now_s()
    response = ratelimit.limit(id)

    assert response.allowed is True
    assert response.limit == 1
    assert response.remaining == 0
    assert response.reset >= now


def test_refill_multiple_times(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = ratelimit.limit(id)

    assert last_response is not None
    last_remaining = last_response.remaining

    time.sleep(3)

    response = ratelimit.limit(id)
    assert response.remaining >= last_remaining + 2


def test_get_remaining(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=10, refill_rate=10, interval=1, unit="d"),
    )

    id = random_id()
    assert ratelimit.get_remaining(id) == 10
    ratelimit.limit(id)
    assert ratelimit.get_remaining(id) == 9


def test_get_remaining_with_refills_that_should_be_made(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = ratelimit.limit(id)

    assert last_response is not None
    last_remaining = last_response.remaining

    time.sleep(3)

    assert ratelimit.get_remaining(id) >= last_remaining + 2


def test_get_reset(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()
    now = now_s()
    ratelimit.limit(id)

    assert ratelimit.get_reset(id) >= now + 0.9


def test_get_reset_with_refills_that_should_be_made(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=1000, refill_rate=1, interval=1),
    )

    id = random_id()

    last_response = None
    for _ in range(10):
        last_response = ratelimit.limit(id)

    assert last_response is not None
    last_reset = last_response.reset

    time.sleep(3)

    assert ratelimit.get_reset(id) >= last_reset + 2
