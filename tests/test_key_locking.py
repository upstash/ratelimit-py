import pytest

from upstash_ratelimit import FixedWindow, SlidingWindow, TokenBucket


@pytest.mark.parametrize("limiter_cls", [FixedWindow, SlidingWindow, TokenBucket])
def test_scripts_opt_into_key_locking(limiter_cls) -> None:
    # The shebang must be the very first line, otherwise Upstash
    # ignores the flag and runs the script under the global lock.
    first_line = limiter_cls.SCRIPT.split("\n", 1)[0]
    assert first_line == "#!lua flags=allow-key-locking"
