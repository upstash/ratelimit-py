from abc import ABC, abstractmethod
from upstash_redis.asyncio import Redis
from upstash_redis.schema.telemetry import TelemetryData
from upstash_ratelimit.config import SDK, PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from asyncio import sleep
from time import time_ns


# TODO might delete this
class RateLimitAlgorithm(ABC):
    @abstractmethod
    def __init__(self, prefix: str = PREFIX):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands. If not given, will read from env variables `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others
        """

        self.prefix = prefix

    @property
    @abstractmethod
    def script(self) -> str:
        """
        Setting this as read-only property enforces the subclasses to implement it without using a setter.
        However, replacing it with a class attribute has the same effect.
        """

    # Limiting methods
    @abstractmethod
    def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """

    # Metadata methods
    @abstractmethod
    def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

    @abstractmethod
    def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

    # Helpers & utils.
    @property
    def current_time_in_milliseconds(self) -> float:
        return time_ns() / 1000000
