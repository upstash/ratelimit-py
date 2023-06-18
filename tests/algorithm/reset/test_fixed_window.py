from tests.client import rate_limit
from pytest import mark, raises
from time import time_ns

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_before_the_first_request() -> None:
    with raises(Exception) as exception:
        await fixed_window.reset("fixed_window_reset_1")

    assert str(exception.value) == "The specified identifier is not rate-limited."


@mark.asyncio
async def test_after_the_first_request() -> None:
    await fixed_window.limit("fixed_window_reset_2")

    now: int = int(time_ns() / 1000000)  # Transform in milliseconds.

    assert now + 3000 - await fixed_window.reset("fixed_window_reset_2") <= 500
