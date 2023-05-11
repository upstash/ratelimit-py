from tests.client import rate_limit
from pytest import mark
from asyncio import sleep

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_below_max():
    assert await fixed_window.is_allowed("fixed_window_1") is True


@mark.asyncio
async def test_above_max():
    await fixed_window.is_allowed("fixed_window_2")

    assert await fixed_window.is_allowed("fixed_window_2") is False
    assert await fixed_window.is_allowed("fixed_window_2") is False


@mark.asyncio
async def test_after_window():
    # Exhaust the request limit.
    await fixed_window.is_allowed("fixed_window_3")
    await sleep(3)

    assert await fixed_window.is_allowed("fixed_window_3") is True


@mark.asyncio
async def test_with_non_ms_unit():
    fixed_window_with_seconds = rate_limit.fixed_window(max_number_of_requests=1, window=3, unit="s")

    assert await fixed_window_with_seconds.is_allowed("fixed_window_4") is True

    # Exhaust the request limit.
    assert await fixed_window_with_seconds.is_allowed("fixed_window_4") is False
    await sleep(3)

    assert await fixed_window_with_seconds.is_allowed("fixed_window_4") is True
