from upstash_ratelimit.utils.time import to_milliseconds
from pytest import raises


def test_with_seconds() -> None:
    assert to_milliseconds(2, "s") == 2000


def test_with_minutes() -> None:
    assert to_milliseconds(2, "m") == 120000


def test_with_hours() -> None:
    assert to_milliseconds(2, "h") == 7200000


def test_with_days() -> None:
    assert to_milliseconds(2, "d") == 172800000


def test_with_invalid() -> None:
    with raises(Exception) as exception:
        to_milliseconds(2, "x")

    assert str(exception.value) == "Unsupported unit."
