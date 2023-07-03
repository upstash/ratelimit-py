from typing import Literal
from upstash_redis.asyncio import Redis
from upstash_redis.schema.telemetry import TelemetryData
from upstash_ratelimit.algorithms.token_bucket_core import TokenBucketCore
from upstash_ratelimit.asyncio.async_blocker import AsyncBlocker
from upstash_ratelimit.config import PREFIX, SDK
from upstash_ratelimit.schema.response import RateLimitResponse
from math import floor


class TokenBucket(TokenBucketCore, AsyncBlocker):
    """
    A bucket is filled with "max_number_of_tokens" that refill at "refill_rate" per "interval".
    Each request tries to consume one token and if the bucket is empty, the request is rejected.
    """

    def __init__(
        self,
        redis: Redis,
        max_number_of_tokens: int,
        refill_rate: int,
        interval: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
        prefix: str = PREFIX,
    ):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands. If not given, will read from env variables `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param max_number_of_tokens: the maximum number of tokens that can be stored in the bucket
        :param refill_rate: the number of tokens that are refilled per interval
        :param interval: the number of time units between each refill
        :param unit: the shorthand version of the time measuring unit
        """

        if redis is None:
            redis = Redis.from_env()

        self.redis = redis

        if redis.allow_telemetry:
            self.redis.telemetry_data = TelemetryData(sdk=SDK)

        super().__init__(
            max_number_of_tokens=max_number_of_tokens,
            refill_rate=refill_rate,
            interval=interval,
            unit=unit,
            prefix=prefix,
        )

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """
        async with self.redis:
            remaining_tokens, next_refill_at = await self.redis.eval(
                script=TokenBucketCore.script,
                keys=[self.get_key(identifier)],
                args=[
                    self.max_number_of_tokens,
                    self.interval,
                    self.refill_rate,
                    self.current_time_in_milliseconds,
                ],
            )

        return super().limit(
            remaining_tokens=remaining_tokens, next_refill_at=next_refill_at
        )

    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """
        async with self.redis:
            bucket = await self.redis.hmget(
                self.get_key(identifier), "updated_at", "tokens"
            )

        return super().remaining(bucket=bucket)

    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """
        async with self.redis:
            updated_at = await self.redis.hget(self.get_key(identifier), "updated_at")

        return super().reset(updated_at=updated_at)

    def get_key(self, identifier):
        return f"{self.prefix}:{identifier}"
