from tests.client import rate_limit
from pytest import mark, raises
from time import time_ns, sleep

token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=1, refill_rate=1, interval=3000, unit="ms"
)


@mark.asyncio
async def test_before_the_first_request() -> None:
    assert await token_bucket.reset("token_bucket_reset_1") == -1


@mark.asyncio
async def test_after_the_first_request() -> None:
    await token_bucket.limit("token_bucket_reset_2")

    now: int = int(time_ns() / 1000000)

    assert now + 3000 - await token_bucket.reset("token_bucket_reset_2") <= 500


@mark.asyncio
async def test_after_multiple_refills() -> None:
    await token_bucket.limit("token_bucket_reset_3")

    sleep(6)  # 2 refills.

    now: int = int(time_ns() / 1000000)

    assert now + 3000 - await token_bucket.reset("token_bucket_reset_3") <= 500
