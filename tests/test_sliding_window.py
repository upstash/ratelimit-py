import time
from typing import List
from unittest.mock import patch

from pytest import approx
from upstash_redis import Redis

from tests.utils import random_id
from upstash_ratelimit import Ratelimit, Response, SlidingWindow
from upstash_ratelimit.utils import now_s


def test_max_requests_are_not_reached(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=5, window=10),
    )

    now = now_s()
    response = ratelimit.limit(random_id())

    assert response.allowed is True
    assert response.limit == 5
    assert response.remaining == 4
    assert response.reset >= now


def test_max_requests_are_reached(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=1, window=1, unit="d"),
    )

    id = random_id()

    ratelimit.limit(id)

    now = now_s()
    response = ratelimit.limit(id)

    assert response.allowed is False
    assert response.limit == 1
    assert response.remaining == 0
    assert response.reset >= now


def test_window_reset(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=1, window=3),
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


def test_sliding(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=5, window=3),
    )

    id = random_id()

    responses: List[Response] = []

    while True:
        response = ratelimit.limit(id)
        responses.append(response)

        if len(responses) > 5 and responses[-2].reset != response.reset:
            break

    last_response = responses[-1]

    # We should consider some items from the last window so the
    # remaining should not be equal to max_requests - 1
    assert last_response.remaining != 4


def test_get_remaining(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=10, window=1, unit="d"),
    )

    id = random_id()
    assert ratelimit.get_remaining(id) == 10
    ratelimit.limit(id)
    assert ratelimit.get_remaining(id) == 9


def test_get_remaining_with_sliding(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=5, window=3),
    )

    id = random_id()

    responses: List[Response] = []

    while True:
        response = ratelimit.limit(id)
        responses.append(response)

        if len(responses) > 5 and responses[-2].reset != response.reset:
            break

    last_response = responses[-1]
    assert ratelimit.get_remaining(id) >= last_response.remaining


def test_get_reset(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=SlidingWindow(max_requests=10, window=5),
    )

    with patch("time.time", return_value=1688910786.167):
        assert ratelimit.get_reset(random_id()) == approx(1688910790.0)
