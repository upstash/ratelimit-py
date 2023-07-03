from typing import ClassVar, Literal
from upstash_ratelimit.algorithms.algorithm import RateLimitAlgorithm
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from time import time_ns
from math import floor


class FixedWindowCore(RateLimitAlgorithm):
    """
    The time is divided into windows of fixed length and each window has a maximum number of allowed requests.
    """

    script: ClassVar[
        str
    ] = """
    -- "key" will store the number of requests made within the window and will expire once the window elapsed.
    local key     = KEYS[1]
    local window  = ARGV[1]

    local current_requests = redis.call("INCR", key)
    if current_requests == 1 then
        -- Set the expiry time to the window duration once the first request has been made.
        redis.call("PEXPIRE", key, window)
    end

    return current_requests
    """

    def __init__(
        self,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
        prefix: str = PREFIX,
    ):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        super().__init__(prefix)

        self.max_number_of_requests = max_number_of_requests
        self.window = window if unit == "ms" else to_milliseconds(window, unit)

    @property
    def current_window(self) -> int:
        return floor(self.current_time_in_milliseconds / self.window)

    def limit(self, current_requests) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """
        return {
            "is_allowed": current_requests <= self.max_number_of_requests,
            "limit": self.max_number_of_requests,
            "remaining": self.max_number_of_requests - current_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window
            + self.window,
        }

    def remaining(self, current_requests) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

        if (
            current_requests is None
        ):  # The identifier hasn't made any request in the current window.
            return self.max_number_of_requests

        return self.max_number_of_requests - int(current_requests)

    def reset(self, exists) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

        if exists != 1:  # The identifier hasn't made any request in the current window.
            return -1

        return floor((time_ns() / 1000000) / self.window) * self.window + self.window
