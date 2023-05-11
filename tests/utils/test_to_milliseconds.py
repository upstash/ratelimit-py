from ratelimit_python.utils.time import to_milliseconds


def test_with_seconds() -> None:
    assert to_milliseconds(2, "s") == 2000


def test_with_minutes() -> None:
    assert to_milliseconds(2, "m") == 120000


def test_with_hours() -> None:
    assert to_milliseconds(2, "h") == 7200000


def test_with_days() -> None:
    assert to_milliseconds(2, "d") == 172800000
