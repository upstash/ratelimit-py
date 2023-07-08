import time

from pytest import raises
from upstash_redis import Redis

from tests.utils import random_id
from upstash_ratelimit import FixedWindow, Ratelimit


def test_invalid_timeout(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=FixedWindow(max_requests=1, window=1),
    )

    with raises(ValueError):
        ratelimit.block_until_ready(random_id(), -1)


def test_resolve_before_timeout(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=FixedWindow(max_requests=5, window=100),
    )

    timeout = 50

    start = time.time()
    response = ratelimit.block_until_ready(random_id(), timeout)
    elapsed = time.time() - start

    assert elapsed < timeout
    assert response.allowed is True


def test_resolve_before_timeout_when_window_resets(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=FixedWindow(max_requests=1, window=3),
    )

    id = random_id()
    timeout = 100

    ratelimit.limit(id)

    start = time.time()
    response = ratelimit.block_until_ready(id, timeout)
    elapsed = time.time() - start

    assert elapsed < timeout
    assert response.allowed is True


def test_reaching_timeout(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=FixedWindow(max_requests=1, window=1, unit="d"),
    )

    id = random_id()
    timeout = 2

    ratelimit.limit(id)

    start = time.time()
    response = ratelimit.block_until_ready(id, timeout)
    elapsed = time.time() - start

    assert elapsed >= timeout
    assert response.allowed is False
