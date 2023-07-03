from tests.client import rate_limit
from pytest import mark, raises


fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


def test_before_timeout() -> None:
    # Exhaust the request limit.
    fixed_window.limit("timeout_1")

    assert (fixed_window.block_until_ready("timeout_1", 4000))["is_allowed"] is True


def test_after_timeout() -> None:
    # Exhaust the request limit.
    fixed_window.limit("timeout_2")

    assert (fixed_window.block_until_ready("timeout_2", 2000))["is_allowed"] is False


def test_with_negative_timeout() -> None:
    with raises(Exception) as exception:
        fixed_window.block_until_ready("timeout_3", -2)

    assert str(exception.value) == "Timeout must be greater than 0."
