from typing import Literal


def to_milliseconds(window: int, unit: Literal["s", "m", "h", "d"]) -> int:
    if unit == "s":
        return window * 1000
    elif unit == "m":
        return window * 1000 * 60
    elif unit == "h":
        return window * 1000 * 60 * 60
    elif unit == "d":
        return window * 1000 * 60 * 60 * 24
    else:
        raise Exception("Unsupported unit.")
