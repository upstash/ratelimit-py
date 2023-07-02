from tests.asyncio.client import rate_limit
from pytest import mark
from time import time_ns
from math import floor

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_before_the_first_request() -> None:
    assert await fixed_window.reset("async_fixed_window_reset_1") == -1


@mark.asyncio
async def test_after_the_first_request() -> None:
    await fixed_window.limit("async_fixed_window_reset_2")

    assert (
        await fixed_window.reset("async_fixed_window_reset_2")
        == floor((time_ns() / 1000000) / 3000) * 3000 + 3000
    )
