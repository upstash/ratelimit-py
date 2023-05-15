from ratelimit_python.algorithm import FixedWindow, SlidingWindow
from upstash_py.client import Redis
from typing import Literal


class RateLimit:
    """
    A class that incorporates all the algorithms to provide a smoother initialisation experience.
    """

    def __init__(self, redis: Redis, prefix: str):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others
        """

        self.redis = redis
        self.prefix = prefix

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

        return FixedWindow(self.redis, self.prefix, max_number_of_requests, window, unit)

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

        return SlidingWindow(self.redis, self.prefix, max_number_of_requests, window, unit)
