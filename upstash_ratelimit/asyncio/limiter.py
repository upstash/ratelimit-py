from upstash_ratelimit.config import PREFIX
from upstash_redis.asyncio import Redis
from upstash_redis.schema.telemetry import TelemetryData
from upstash_ratelimit.config import SDK, PREFIX
from typing import Literal, Optional
from upstash_ratelimit.asyncio.fixed_window import FixedWindow
from upstash_ratelimit.asyncio.sliding_window import SlidingWindow
from upstash_ratelimit.asyncio.token_bucket import TokenBucket


class RateLimit:
    """
    A class that incorporates all the algorithms to provide a smoother initialisation experience.
    """

    def __init__(self, redis: Optional[Redis] = None, prefix: str = PREFIX):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands. If not given, will read from env variables `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others
        """

        if redis is None:
            redis = Redis.from_env()

        self.redis = redis
        self.prefix = prefix

        if redis.allow_telemetry:
            self.redis.telemetry_data = TelemetryData(sdk=SDK)

    def fixed_window(
        self,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
    ) -> FixedWindow:
        """
        The time is divided into windows of fixed length and each window has a maximum number of allowed requests.

        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        return FixedWindow(
            self.redis, max_number_of_requests, window, unit, self.prefix
        )

    def sliding_window(
        self,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
    ) -> SlidingWindow:
        """
        Combined approach of sliding logs and fixed window with lower storage
        costs than sliding logs and improved boundary behavior by calculating a
        weighted score between two windows.

        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        return SlidingWindow(
            self.redis, max_number_of_requests, window, unit, self.prefix
        )

    def token_bucket(
        self,
        max_number_of_tokens: int,
        refill_rate: int,
        interval: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
    ) -> TokenBucket:
        """
        A bucket is filled with "max_number_of_tokens" that refill at "refill_rate" per "interval".
        Each request tries to consume one token and if the bucket is empty, the request is rejected.

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
            self.prefix,
        )
