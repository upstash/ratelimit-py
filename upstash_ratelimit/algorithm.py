from abc import ABC, abstractmethod
from typing import ClassVar, Literal
from upstash_redis.client import Redis
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import SDK, PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from time import time_ns, sleep
from math import floor


class RateLimitAlgorithm(ABC):
    @abstractmethod
    def __init__(self, redis: Redis, prefix: str = PREFIX):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others
        """

        self.redis = redis
        self.prefix = prefix

        if redis.allow_telemetry:
            self.redis.telemetry_data = {
                "sdk": SDK
            }

    @property
    @abstractmethod
    def script(self) -> str:
        """
        Setting this as read-only property enforces the subclasses to implement it without using a setter.
        However, replacing it with a class attribute has the same effect.
        """

    @abstractmethod
    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Determine whether the identifier's request should pass and return additional metadata.
        """

    async def block_until_ready(self, identifier: str, timeout: int) -> RateLimitResponse:
        """
        If a request is denied, wait for it to pass in the given timeout in milliseconds
        and if it doesn't, return the last response.
        """

        if timeout <= 0:
            raise Exception("Timeout must be greater than 0.")

        response: RateLimitResponse = await self.limit(identifier)

        if response["is_allowed"]:
            return response

        deadline: int = time_ns() + timeout * 1000000  # Transform in nanoseconds.

        while response["is_allowed"] is False and time_ns() < deadline:
            # Transform the reset time from milliseconds to seconds and the sleep time in seconds.
            sleep((min(response["reset"] * 1000000, deadline) - time_ns()) / 1000000000)

            response = await self.limit(identifier)

        return response


class FixedWindow(RateLimitAlgorithm):
    """
    The first request after a window has elapsed triggers the creation of a new one with the specified duration.
    For each subsequent request, the algorithm checks whether the number of requests has exceeded the limit.
    """

    script: ClassVar[str] = """
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
        redis: Redis,
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

        super().__init__(redis, prefix)

        self.max_number_of_requests = max_number_of_requests
        self.window = window if unit == "ms" else to_milliseconds(window, unit)

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Determine whether the identifier's request should pass and return additional metadata.
        """

        key: str = f'{self.prefix}:{identifier}'

        async with self.redis:
            current_requests: int = await self.redis.eval(
                script=FixedWindow.script,
                keys=[key],
                arguments=[self.window]
            )

        return {
            "is_allowed": current_requests <= self.max_number_of_requests,
            "limit": self.max_number_of_requests,
            "remaining": self.max_number_of_requests - current_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window + self.window,
        }


class SlidingWindow(RateLimitAlgorithm):
    """
    Combined approach of sliding logs and fixed window with lower storage
    costs than sliding logs and improved boundary behavior by calculating a
    weighted score between two windows.
    """

    script: ClassVar[str] = """
      local current_key             = KEYS[1]                      -- identifier including prefixes
      local previous_key            = KEYS[2]                      -- key of the previous bucket
      local max_number_of_requests  = tonumber(ARGV[1])            -- max number of requests per window
      local now                     = ARGV[2]                      -- current timestamp in milliseconds
      local window                  = ARGV[3]                      -- interval in milliseconds

      local requests_in_current_window = redis.call("GET", current_key)
      if requests_in_current_window == false then
        requests_in_current_window = -1
      end

      local requests_in_previous_window = redis.call("GET", previous_key)
      if requests_in_previous_window == false then
        requests_in_previous_window = 0
      end
      
      local percentage_in_current_window = ( now % window) / window
      
      local estimated = requests_in_previous_window * ( 1 - percentage_in_current_window ) + requests_in_current_window
      if estimated >= max_number_of_requests then
        return -1
      end

      local new_current_requests = redis.call("INCR", current_key)
      if new_current_requests == 1 then 
        -- Set the expiry time of the current window once the first request has been made.
        redis.call("PEXPIRE", current_key, window * 2 + 1000) -- Enough time to overlap with a new window + 1 second
      end
      return max_number_of_requests - new_current_requests
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
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param max_number_of_requests: the number of requests allowed within the window
        :param window: the number of time units in which requests are limited
        :param unit: the shorthand version of the time measuring unit
        """

        super().__init__(redis, prefix)

        self.max_number_of_requests = max_number_of_requests
        self.window = window if unit == "ms" else to_milliseconds(window, unit)

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Determine whether the identifier's request should pass and return additional metadata.

        Although we return the unix time when the next window begins (via "reset"), the limit is still enforced
        between the two intervals.
        """

        now: float = time_ns() / 1000000  # Convert to milliseconds.

        """
        Divide the current time by the window duration and round down 
        to get possible sliding-after-window values for the intervals.
        """
        current_window: int = floor(now / self.window)

        previous_window: int = current_window - self.window

        current_key: str = f'{self.prefix}:{identifier}:{current_window}'

        previous_key: str = f'{self.prefix}:{identifier}:{previous_window}'

        async with self.redis:
            remaining_requests: int = await self.redis.eval(
                script=SlidingWindow.script,
                keys=[current_key, previous_key],
                arguments=[self.max_number_of_requests, now, self.window]
            )

        return {
            "is_allowed": remaining_requests >= 0,
            "limit": self.max_number_of_requests,
            "remaining": remaining_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window + self.window,
        }


class TokenBucket(RateLimitAlgorithm):
    """
    A bucket is filled with "max_number_of_tokens" that refill at "refill_rate" per "interval".
    Each request tries to consume one token and if the bucket is empty, the request is rejected.
    """

    script: ClassVar[str] = """
    local key                       = KEYS[1]               -- identifier including prefixes
    local max_number_of_tokens      = tonumber(ARGV[1])     -- max number of tokens
    local interval                  = tonumber(ARGV[2])     -- size of the window in milliseconds
    local refill_rate               = tonumber(ARGV[3])     -- how many tokens are refilled after each interval
    local now                       = tonumber(ARGV[4])     -- current timestamp in milliseconds
    local remaining                 = 0

    local bucket = redis.call("HMGET", key, "updated_at", "tokens")

    if bucket[1] == false then
      -- The bucket does not exist yet, create it and set its ttl to "interval".
      remaining = max_number_of_tokens - 1

      redis.call("HMSET", key, "updated_at", now, "tokens", remaining)

      return {remaining, now + interval}
    end

    local updated_at = tonumber(bucket[1])
    local tokens = tonumber(bucket[2])

    if now >= updated_at + interval then
      if tokens <= 0 then -- No more tokens were left before the refill.
        remaining = math.min(max_number_of_tokens, refill_rate) - 1
      else
        remaining = math.min(max_number_of_tokens, tokens + refill_rate) - 1
      end

      redis.call("HMSET", key, "updated_at", now, "tokens", remaining)
      return {remaining, now + interval}
    end
    
    remaining = tokens - 1
    redis.call("HSET", key, "tokens", remaining)

    return {remaining, updated_at + interval}
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
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others

        :param max_number_of_tokens: the maximum number of tokens that can be stored in the bucket
        :param refill_rate: the number of tokens that are refilled per interval
        :param interval: the number of time units between each refill
        :param unit: the shorthand version of the time measuring unit
        """

        super().__init__(redis, prefix)

        self.max_number_of_tokens = max_number_of_tokens
        self.refill_rate = refill_rate
        self.interval = interval if unit == "ms" else to_milliseconds(interval, unit)

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Determine whether the identifier's request should pass and return additional metadata.
        """

        now: float = time_ns() / 1000000

        key: str = f'{self.prefix}:{identifier}'

        async with self.redis:
            remaining_tokens, next_refill_at = await self.redis.eval(
                script=TokenBucket.script,
                keys=[key],
                arguments=[self.max_number_of_tokens, self.interval, self.refill_rate, now]
            )

        return {
            "is_allowed": remaining_tokens >= 0,
            "limit": self.max_number_of_tokens,
            "remaining": remaining_tokens,
            "reset": next_refill_at
        }
