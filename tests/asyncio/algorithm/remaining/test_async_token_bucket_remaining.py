from tests.asyncio.client import rate_limit
from pytest import mark
from time import sleep

token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=1, refill_rate=1, interval=6000, unit="ms"
)


@mark.asyncio
async def test_before_the_first_request() -> None:
    assert await token_bucket.remaining("async_token_bucket_remaining_1") == 1


@mark.asyncio
async def test_after_the_first_request() -> None:
    await token_bucket.limit("async_token_bucket_remaining_2")

    sleep(2)

    assert await token_bucket.remaining("async_token_bucket_remaining_2") == 0


# Use a client that has different maximum number of tokens and refill rate.
burst_token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=2, refill_rate=1, interval=2000, unit="ms"
)


@mark.asyncio
async def test_after_burst() -> None:
    # Exhaust the request limit.
    await burst_token_bucket.limit("async_burst_token_bucket_remaining_1")
    await burst_token_bucket.limit("async_burst_token_bucket_remaining_1")

    # Wait for the refill.
    sleep(2)

    assert (
        await burst_token_bucket.remaining("async_burst_token_bucket_remaining_1") == 1
    )


@mark.asyncio
async def test_after_burst_with_positive_number_of_tokens_before_the_refill() -> None:
    await burst_token_bucket.limit("async_burst_token_bucket_remaining_2")

    """
    At this point the bucket should've had 1 token. 
    Since the refill adds another one, the identifier should have 2 requests left.
    """
    sleep(2)

    assert (
        await burst_token_bucket.remaining("async_burst_token_bucket_remaining_2") == 2
    )
