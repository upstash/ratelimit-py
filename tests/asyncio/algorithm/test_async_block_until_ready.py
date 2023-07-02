from tests.asyncio.client import rate_limit
from pytest import mark, raises


fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


@mark.asyncio
async def test_before_timeout() -> None:
    # Exhaust the request limit.
    await fixed_window.limit("timeout_1")

    assert (await fixed_window.block_until_ready("timeout_1", 4000))[
        "is_allowed"
    ] is True


@mark.asyncio
async def test_after_timeout() -> None:
    # Exhaust the request limit.
    await fixed_window.limit("timeout_2")

    assert (await fixed_window.block_until_ready("timeout_2", 2000))[
        "is_allowed"
    ] is False


@mark.asyncio
async def test_with_negative_timeout() -> None:
    with raises(Exception) as exception:
        await fixed_window.block_until_ready("timeout_3", -2)

    assert str(exception.value) == "Timeout must be greater than 0."
