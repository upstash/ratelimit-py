from typing import Literal


def to_milliseconds(window: int, unit: Literal["s", "m", "h", "d"]) -> int:
    match unit:
        case "s":
            return window * 1000
        case "m":
            return window * 1000 * 60
        case "h":
            return window * 1000 * 60 * 60
        case "d":
            return window * 1000 * 60 * 60 * 24
