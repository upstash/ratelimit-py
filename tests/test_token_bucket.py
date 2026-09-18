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


def test_custom_rate(redis: Redis) -> None:
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=10, refill_rate=1, interval=1),
    )
    rate = 2

    id = random_id()

    ratelimit.limit(id)
    ratelimit.limit(id, rate)
    assert ratelimit.get_remaining(id) == 7

    ratelimit.limit(id, rate)
    assert ratelimit.get_remaining(id) == 5


def test_rate_larger_than_remaining_is_rejected_without_consuming(
    redis: Redis,
) -> None:
    # max_tokens > 1 so a single request can ask for more tokens than remain.
    ratelimit = Ratelimit(
        redis=redis,
        limiter=TokenBucket(max_tokens=10, refill_rate=10, interval=1, unit="d"),
    )

    id = random_id()

    # Leave 2 tokens in the bucket.
    first = ratelimit.limit(id, rate=8)
    assert first.allowed is True
    assert first.remaining == 2

    # 2 tokens left, ask for 5: must be rejected. It must NOT drive the bucket
    # negative (which would lock the identifier out long past this request).
    denied = ratelimit.limit(id, rate=5)
    assert denied.allowed is False

    # The 2 tokens the denied request must not have consumed are still spendable.
    ok = ratelimit.limit(id, rate=2)
    assert ok.allowed is True
    assert ok.remaining == 0
