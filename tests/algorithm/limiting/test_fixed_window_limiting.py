from time import sleep
from tests.client import rate_limit
from pytest import mark

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=5000, unit="ms")

def test_below_max() -> None:
    assert (fixed_window.limit("fixed_window_1"))["is_allowed"] is True



def test_above_max() -> None:
    fixed_window.limit("fixed_window_2")

    sleep(0.5)
    
    assert (fixed_window.limit("fixed_window_2"))["is_allowed"] is False
    assert (fixed_window.limit("fixed_window_2"))["is_allowed"] is False



def test_after_window() -> None:
    # Exhaust the request limit.
    fixed_window.limit("fixed_window_3")

    # Wait for the reset.
    sleep(5)

    assert (fixed_window.limit("fixed_window_3"))["is_allowed"] is True



def test_with_non_ms_unit() -> None:
    fixed_window_with_seconds = rate_limit.fixed_window(
        max_number_of_requests=1, window=5, unit="s"
    )

    assert (fixed_window_with_seconds.limit("fixed_window_4"))[
        "is_allowed"
    ] is True

    # Exhaust the request limit.
    assert (fixed_window_with_seconds.limit("fixed_window_4"))[
        "is_allowed"
    ] is False

    sleep(5)

    assert (fixed_window_with_seconds.limit("fixed_window_4"))[
        "is_allowed"
    ] is True
