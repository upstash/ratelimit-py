from tests.client import rate_limit
from pytest import mark
from asyncio import sleep

# Mimic the behavior of fixed window.
token_bucket = rate_limit.token_bucket(max_number_of_tokens=1, refill_rate=1, interval=3000, unit="ms")


@mark.asyncio
async def test_below_max():
    assert await token_bucket.is_allowed("token_bucket_1") is True
    

@mark.asyncio
async def test_above_max():
    await token_bucket.is_allowed("token_bucket_2")

    assert await token_bucket.is_allowed("token_bucket_2") is False
    assert await token_bucket.is_allowed("token_bucket_2") is False


@mark.asyncio
async def test_after_window():
    # Exhaust the request limit.
    await token_bucket.is_allowed("token_bucket_3")
    await sleep(3)

    assert await token_bucket.is_allowed("token_bucket_3") is True


@mark.asyncio
async def test_with_non_ms_unit():
    token_bucket_with_seconds = rate_limit.token_bucket(max_number_of_tokens=1, refill_rate=1, interval=3, unit="s")

    # Exhaust the request limit.
    assert await token_bucket_with_seconds.is_allowed("token_bucket_4") is True

    assert await token_bucket_with_seconds.is_allowed("token_bucket_4") is False

    # Wait for the refill.
    await sleep(3)

    assert await token_bucket_with_seconds.is_allowed("token_bucket_4") is True

# Use a client that has different maximum number of tokens and refill rate.
burst_token_bucket = rate_limit.token_bucket(max_number_of_tokens=2, refill_rate=1, interval=3000, unit="ms")


@mark.asyncio
async def test_burst():
    # Exhaust the request limit.
    assert await burst_token_bucket.is_allowed("burst_token_bucket_1") is True
    assert await burst_token_bucket.is_allowed("burst_token_bucket_1") is True

    # Wait for the refill.
    await sleep(3)

    assert await burst_token_bucket.is_allowed("burst_token_bucket_1") is True
    assert await burst_token_bucket.is_allowed("burst_token_bucket_1") is False
    assert await burst_token_bucket.is_allowed("burst_token_bucket_1") is False


@mark.asyncio
async def test_with_positive_number_of_tokens_before_refill():
    assert await burst_token_bucket.is_allowed("burst_token_bucket_2") is True

    await sleep(3)
    """
    At this point the bucket should've had 1 token. 
    Since the refill adds another one, the next two requests should pass.
    """

    assert await burst_token_bucket.is_allowed("burst_token_bucket_2") is True
    assert await burst_token_bucket.is_allowed("burst_token_bucket_2") is True
    assert await burst_token_bucket.is_allowed("burst_token_bucket_2") is False
