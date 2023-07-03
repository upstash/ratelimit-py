from tests.client import rate_limit
from pytest import mark

fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=3000, unit="ms")


def test_before_the_first_request() -> None:
    assert fixed_window.remaining("fixed_window_remaining_1") == 1


def test_after_the_first_request() -> None:
    fixed_window.limit("fixed_window_remaining_2")

    assert fixed_window.remaining("fixed_window_remaining_2") == 0
