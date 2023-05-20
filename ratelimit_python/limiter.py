from ratelimit_python.algorithm import FixedWindow, SlidingWindow, TokenBucket
from ratelimit_python.config import ALLOW_TELEMETRY, PREFIX
from upstash_py.client import Redis
from typing import Literal


class RateLimit:
    """
    A class that incorporates all the algorithms to provide a smoother initialisation experience.
    """

    def __init__(self, redis: Redis, prefix: str = PREFIX, allow_telemetry: bool = ALLOW_TELEMETRY):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param allow_telemetry: whether collecting non-identifiable telemetry data is allowed
        """

        self.redis = redis
        self.prefix = prefix
        self.allow_telemetry = allow_telemetry

    def fixed_window(
        self,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
    ) -> FixedWindow:
        """
        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        return FixedWindow(self.redis, max_number_of_requests, window, unit, self.allow_telemetry, self.prefix)

    def sliding_window(
        self,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms"
    ) -> SlidingWindow:
        """
        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        return SlidingWindow(self.redis, max_number_of_requests, window, unit, self.allow_telemetry, self.prefix)

    def token_bucket(
        self,
        max_number_of_tokens: int,
        refill_rate: int,
        interval: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms"
    ) -> TokenBucket:
        """
        :param max_number_of_tokens: the maximum number of tokens that the bucket can hold
        :param refill_rate: the number of tokens that are refilled per interval
        :param interval: the number of time units between each refill
        :param unit: the shorthand version of the time measuring unit
        """

        return TokenBucket(
            self.redis,
            max_number_of_tokens,
            refill_rate,
            interval,
            unit,
            self.allow_telemetry,
            self.prefix,
        )
