from distutils.sysconfig import PREFIX
from typing import Literal
from upstash_redis import Redis
from upstash_redis.schema.telemetry import TelemetryData
from upstash_ratelimit.algorithms.fixed_window_core import FixedWindowCore
from upstash_ratelimit.config import SDK
from upstash_ratelimit.sync.sync_blocker import SyncBlocker
from upstash_ratelimit.schema.response import RateLimitResponse


class FixedWindow(FixedWindowCore, SyncBlocker):
    """
    The time is divided into windows of fixed length and each window has a maximum number of allowed requests.
    """

    def __init__(
        self,
        redis: Redis,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
        prefix: str = PREFIX,
    ):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands. If not given, will read from env variables `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        if redis is None:
            redis = Redis.from_env()

        self.redis = redis

        if redis.allow_telemetry:
            self.redis.telemetry_data = TelemetryData(sdk=SDK)

        super().__init__(
            max_number_of_requests=max_number_of_requests,
            window=window,
            unit=unit,
            prefix=prefix,
        )

    def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """
        current_requests = self.redis.eval(
            script=FixedWindowCore.script,
            keys=[self.find_key(identifier)],
            args=[self.window],
        )

        return super().limit(current_requests)

    def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """
        current_requests = self.redis.get(self.find_key(identifier))

        return super().remaining(current_requests)

    def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """
        exists = (
            self.redis.exists(self.find_key(identifier)) == 1
        )  # The identifier hasn't made any request in the current window.

        return super().reset(exists)

    def find_key(self, identifier: str) -> str:
        return f"{self.prefix}:{identifier}:{self.current_window}"
