from tests.client import rate_limit
from pytest import mark
from time import sleep

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_below_max() -> None:
    assert (await fixed_window.limit("fixed_window_1"))["is_allowed"] is True


@mark.asyncio
async def test_above_max() -> None:
    await fixed_window.limit("fixed_window_2")

    assert (await fixed_window.limit("fixed_window_2"))["is_allowed"] is False
    assert (await fixed_window.limit("fixed_window_2"))["is_allowed"] is False


@mark.asyncio
async def test_after_window() -> None:
    # Exhaust the request limit.
    await fixed_window.limit("fixed_window_3")

    # Wait for the reset.
    sleep(3)

    assert (await fixed_window.limit("fixed_window_3"))["is_allowed"] is True


@mark.asyncio
async def test_with_non_ms_unit() -> None:
    fixed_window_with_seconds = rate_limit.fixed_window(max_number_of_requests=1, window=3, unit="s")

    assert (await fixed_window_with_seconds.limit("fixed_window_4"))["is_allowed"] is True

    # Exhaust the request limit.
    assert (await fixed_window_with_seconds.limit("fixed_window_4"))["is_allowed"] is False

    # Wait for the reset.
    sleep(3)

    assert (await fixed_window_with_seconds.limit("fixed_window_4"))["is_allowed"] is True
