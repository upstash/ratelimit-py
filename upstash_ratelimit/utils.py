import time
from typing import Any

from upstash_ratelimit import __version__
from upstash_ratelimit.typing import UnitT


def merge_telemetry(redis: Any) -> None:
    if (
        not hasattr(redis, "_allow_telemetry")
        or not redis._allow_telemetry
        or not hasattr(redis, "_headers")
    ):
        return

    sdk = redis._headers.get("Upstash-Telemetry-Sdk")
    if not sdk:
        return

    sdk = f"{sdk}, py-upstash-ratelimit@v{__version__}"
    redis._headers["Upstash-Telemetry-Sdk"] = sdk


def ms_to_s(value: int) -> float:
    return value / 1_000


def s_to_ms(value: float) -> int:
    return int(value * 1_000)


def now_s() -> float:
    return time.time()


def now_ms() -> int:
    return int(time.time() * 1_000)


def to_ms(value: int, unit: UnitT) -> int:
    if unit == "ms":
        return value
    elif unit == "s":
        return value * 1_000
    elif unit == "m":
        return value * 60 * 1_000
    elif unit == "h":
        return value * 60 * 60 * 1_000
    elif unit == "d":
        return value * 24 * 60 * 60 * 1_000
    else:
        raise ValueError("Unexpected unit")
