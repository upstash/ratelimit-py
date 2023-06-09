from tests.client import rate_limit
from pytest import mark

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_first_request() -> None:
    assert await fixed_window.remaining("fixed_window_remaining_1") == 1


@mark.asyncio
async def test_after_the_first_request() -> None:
    await fixed_window.limit("fixed_window_remaining_2")

    assert await fixed_window.remaining("fixed_window_remaining_2") == 0
