from tests.asyncio.client import rate_limit
from pytest import mark
from time import sleep

# Mimic the behavior of fixed window.
token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=1, refill_rate=1, interval=3000, unit="ms"
)


@mark.asyncio
async def test_below_max() -> None:
    assert (await token_bucket.limit("async_token_bucket_1"))["is_allowed"] is True


@mark.asyncio
async def test_above_max() -> None:
    await token_bucket.limit("async_token_bucket_2")

    assert (await token_bucket.limit("async_token_bucket_2"))["is_allowed"] is False
    assert (await token_bucket.limit("async_token_bucket_2"))["is_allowed"] is False


@mark.asyncio
async def test_after_window() -> None:
    # Exhaust the request limit.
    await token_bucket.limit("async_token_bucket_3")

    # Wait for the refill.
    sleep(3)

    assert (await token_bucket.limit("async_token_bucket_3"))["is_allowed"] is True


@mark.asyncio
async def test_with_non_ms_unit() -> None:
    token_bucket_with_seconds = rate_limit.token_bucket(
        max_number_of_tokens=1, refill_rate=1, interval=3, unit="s"
    )

    # Exhaust the request limit.
    assert (await token_bucket_with_seconds.limit("async_token_bucket_4"))[
        "is_allowed"
    ] is True

    assert (await token_bucket_with_seconds.limit("async_token_bucket_4"))[
        "is_allowed"
    ] is False

    # Wait for the refill.
    sleep(3)

    assert (await token_bucket_with_seconds.limit("async_token_bucket_4"))[
        "is_allowed"
    ] is True


# Use a client that has different maximum number of tokens and refill rate.
burst_token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=2, refill_rate=1, interval=2000, unit="ms"
)


@mark.asyncio
async def test_burst() -> None:
    # Exhaust the request limit.
    await burst_token_bucket.limit("async_burst_token_bucket_1")
    await burst_token_bucket.limit("async_burst_token_bucket_1")

    # Wait for the refill.
    sleep(2)

    assert (await burst_token_bucket.limit("async_burst_token_bucket_1"))[
        "is_allowed"
    ] is True
    assert (await burst_token_bucket.limit("async_burst_token_bucket_1"))[
        "is_allowed"
    ] is False
    assert (await burst_token_bucket.limit("async_burst_token_bucket_1"))[
        "is_allowed"
    ] is False


@mark.asyncio
async def test_with_positive_number_of_tokens_before_the_refill() -> None:
    await burst_token_bucket.limit("async_burst_token_bucket_2")

    """
    At this point the bucket should've had 1 token. 
    Since the refill adds another one, the next two requests should pass.
    """
    sleep(2)

    assert (await burst_token_bucket.limit("async_burst_token_bucket_2"))[
        "is_allowed"
    ] is True
    assert (await burst_token_bucket.limit("async_burst_token_bucket_2"))[
        "is_allowed"
    ] is True
    assert (await burst_token_bucket.limit("async_burst_token_bucket_2"))[
        "is_allowed"
    ] is False


@mark.asyncio
async def test_multiple_refills() -> None:
    # Exhaust the request limit.
    await burst_token_bucket.limit("async_burst_token_bucket_3")
    await burst_token_bucket.limit("async_burst_token_bucket_3")

    # Wait for 2 refills.
    sleep(4)

    assert (await burst_token_bucket.limit("async_burst_token_bucket_3"))[
        "is_allowed"
    ] is True
    assert (await burst_token_bucket.limit("async_burst_token_bucket_3"))[
        "is_allowed"
    ] is True
    assert (await burst_token_bucket.limit("async_burst_token_bucket_3"))[
        "is_allowed"
    ] is False
