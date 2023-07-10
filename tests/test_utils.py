from unittest.mock import patch

from pytest import approx, mark, raises

from upstash_ratelimit.typing import UnitT
from upstash_ratelimit.utils import ms_to_s, now_ms, now_s, s_to_ms, to_ms


@mark.parametrize(
    "value,unit,expected",
    [
        (1, "d", 86_400_000),
        (4, "h", 14_400_000),
        (2, "m", 120_000),
        (33, "s", 33_000),
        (42, "ms", 42),
    ],
)
def test_to_ms(value: int, unit: UnitT, expected: int) -> None:
    assert to_ms(value, unit) == expected


def test_to_ms_invalid_unit() -> None:
    with raises(ValueError):
        to_ms(42, "invalid")  # type: ignore[arg-type]


def test_now_ms() -> None:
    with patch("time.time", return_value=42.5):
        assert now_ms() == 42_500


def test_now_s() -> None:
    with patch("time.time", return_value=42.5):
        assert now_s() == 42.5


def test_s_to_ms() -> None:
    assert s_to_ms(12.5) == 12_500


def test_ms_to_s() -> None:
    assert ms_to_s(44_123) == approx(44.123)
