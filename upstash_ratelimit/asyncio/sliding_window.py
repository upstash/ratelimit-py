from typing import ClassVar, Literal
from upstash_redis.asyncio import Redis
from upstash_redis.schema.telemetry import TelemetryData
from upstash_ratelimit.algorithms.sliding_window_core import SlidingWindowCore
from upstash_ratelimit.asyncio.async_blocker import AsyncBlocker
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import PREFIX, SDK
from upstash_ratelimit.schema.response import RateLimitResponse
from time import time_ns
from math import floor


class SlidingWindow(SlidingWindowCore, AsyncBlocker):
    """
    Combined approach of sliding logs and fixed window with lower storage
    costs than sliding logs and improved boundary behavior by calculating a
    weighted score between two windows.
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

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.

        Although we return the unix time when the next window begins (via "reset"), the limit is still enforced
        between the two intervals.
        """
        async with self.redis:
            remaining_requests: int = await self.redis.eval(
                script=SlidingWindowCore.script,
                keys=[
                    self.get_current_key(identifier),
                    self.get_previous_key(identifier),
                ],
                args=[
                    self.max_number_of_requests,
                    self.current_time_in_milliseconds,
                    self.window,
                ],
            )

        return super().limit(remaining_requests)

    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """
        async with self.redis:
            stored_requests_in_current_window = await self.redis.get(
                self.get_current_key(identifier)
            )
            stored_requests_in_previous_window = await self.redis.get(
                self.get_previous_key(identifier)
            )

        return super().remaining(
            stored_requests_in_current_window, stored_requests_in_previous_window
        )

    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """
        async with self.redis:
            exists = await self.redis.exists(
                self.get_previous_key(identifier), self.get_current_key(identifier)
            )

        return super().reset(exists)

    def get_previous_key(self, identifier):
        return f"{self.prefix}:{identifier}:{self.previous_window}"

    def get_current_key(self, identifier):
        return f"{self.prefix}:{identifier}:{self.current_window}"
