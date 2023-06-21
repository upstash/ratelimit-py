from abc import ABC, abstractmethod
from typing import ClassVar, Literal, cast
from upstash_redis.asyncio import Redis
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import SDK, PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from asyncio import sleep
from time import time_ns
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
            self.redis.telemetry_data = {"sdk": SDK}

    @property
    @abstractmethod
    def script(self) -> str:
        """
        Setting this as read-only property enforces the subclasses to implement it without using a setter.
        However, replacing it with a class attribute has the same effect.
        """

    # Limiting methods
    @abstractmethod
    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """

    async def block_until_ready(
        self, identifier: str, timeout: int
    ) -> RateLimitResponse:
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
            await sleep(
                (min(response["reset"] * 1000000, deadline) - time_ns()) / 1000000000
            )

            response = await self.limit(identifier)

        return response

    # Metadata methods
    @abstractmethod
    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

    @abstractmethod
    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

    # Helpers & utils.
    @property
    def current_time_in_milliseconds(self) -> float:
        return time_ns() / 1000000


class FixedWindow(RateLimitAlgorithm):
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

    @property
    def current_window(self) -> int:
        return floor(self.current_time_in_milliseconds / self.window)

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """

        key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        async with self.redis:
            current_requests: int

            current_requests = await self.redis.eval(
                script=FixedWindow.script, keys=[key], args=[self.window]
            )

        return {
            "is_allowed": current_requests <= self.max_number_of_requests,
            "limit": self.max_number_of_requests,
            "remaining": self.max_number_of_requests - current_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window
            + self.window,
        }

    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

        key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        async with self.redis:
            current_requests: str | None = await self.redis.get(key)

        if (
            current_requests is None
        ):  # The identifier hasn't made any request in the current window.
            return self.max_number_of_requests

        return self.max_number_of_requests - int(current_requests)

    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

        key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        async with self.redis:
            if (
                await self.redis.exists(key) != 1
            ):  # The identifier hasn't made any request in the current window.
                return -1

        return floor((time_ns() / 1000000) / self.window) * self.window + self.window


class SlidingWindow(RateLimitAlgorithm):
    """
    Combined approach of sliding logs and fixed window with lower storage
    costs than sliding logs and improved boundary behavior by calculating a
    weighted score between two windows.
    """

    script: ClassVar[
        str
    ] = """
      local current_key             = KEYS[1]                      -- identifier including prefixes
      local previous_key            = KEYS[2]                      -- key of the previous bucket
      local max_number_of_requests  = tonumber(ARGV[1])            -- max number of requests per window
      local now                     = tonumber(ARGV[2])            -- current timestamp in milliseconds
      local window                  = tonumber(ARGV[3])            -- interval in milliseconds

      local requests_in_current_window = redis.call("GET", current_key)
      if requests_in_current_window == false then
        requests_in_current_window = -1
      else
        requests_in_current_window = tonumber(requests_in_current_window)
      end

      local requests_in_previous_window = redis.call("GET", previous_key)
      if requests_in_previous_window == false then
        requests_in_previous_window = 0
      else
        requests_in_previous_window = tonumber(requests_in_previous_window)
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

    """
    Divide the current time by the window duration and round down 
    to get possible sliding-after-window values for the intervals.
    """

    @property
    def current_window(self) -> int:
        return floor(self.current_time_in_milliseconds / self.window)

    @property
    def previous_window(self) -> int:
        return self.current_window - self.window

    async def limit(self, identifier: str) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.

        Although we return the unix time when the next window begins (via "reset"), the limit is still enforced
        between the two intervals.
        """

        current_key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        previous_key: str = f"{self.prefix}:{identifier}:{self.previous_window}"

        async with self.redis:
            remaining_requests: int = await self.redis.eval(
                script=SlidingWindow.script,
                keys=[current_key, previous_key],
                args=[
                    self.max_number_of_requests,
                    self.current_time_in_milliseconds,
                    self.window,
                ],
            )

        return {
            "is_allowed": remaining_requests >= 0,
            "limit": self.max_number_of_requests,
            "remaining": remaining_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window
            + self.window,
        }

    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

        current_key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        previous_key: str = f"{self.prefix}:{identifier}:{self.previous_window}"

        async with self.redis:
            stored_requests_in_current_window: str | None = await self.redis.get(
                current_key
            )

            stored_requests_in_previous_window: str | None = await self.redis.get(
                previous_key
            )

        requests_in_current_window: int

        # The identifier hasn't made any request in the current window.
        if stored_requests_in_current_window is None:
            requests_in_current_window = 0
        else:
            requests_in_current_window = int(stored_requests_in_current_window)

        requests_in_previous_window: int

        if stored_requests_in_previous_window is None:
            requests_in_previous_window = 0
        else:
            requests_in_previous_window = int(stored_requests_in_previous_window)

        percentage_in_current_window = (
            self.current_time_in_milliseconds % self.window
        ) / self.window

        estimated = (
            requests_in_previous_window * (1 - percentage_in_current_window)
            + requests_in_current_window
        )

        if estimated >= self.max_number_of_requests:  # The limit has been exceeded.
            return 0

        return self.max_number_of_requests - requests_in_current_window

    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

        current_key: str = f"{self.prefix}:{identifier}:{self.current_window}"

        previous_key: str = f"{self.prefix}:{identifier}:{self.previous_window}"

        async with self.redis:
            # The identifier hasn't made any requests in either the previous or the current window.
            if await self.redis.exists(previous_key, current_key) == 0:
                return -1

        return floor((time_ns() / 1000000) / self.window) * self.window + self.window


class TokenBucket(RateLimitAlgorithm):
    """
    A bucket is filled with "max_number_of_tokens" that refill at "refill_rate" per "interval".
    Each request tries to consume one token and if the bucket is empty, the request is rejected.
    """

    script: ClassVar[
        str
    ] = """
    local key                       = KEYS[1]               -- identifier including prefixes
    local max_number_of_tokens      = tonumber(ARGV[1])     -- max number of tokens
    local interval                  = tonumber(ARGV[2])     -- size of the window in milliseconds
    local refill_rate               = tonumber(ARGV[3])     -- how many tokens are refilled after each interval
    local now                       = tonumber(ARGV[4])     -- current timestamp in milliseconds
    local remaining                 = 0

    local bucket = redis.call("HMGET", key, "updated_at", "tokens")

    if bucket[1] == false then -- The bucket does not exist
      remaining = max_number_of_tokens - 1

      redis.call("HMSET", key, "updated_at", now, "tokens", remaining)

      return {remaining, now + interval}
    end

    local updated_at = tonumber(bucket[1])
    local tokens = tonumber(bucket[2])

    if now >= updated_at + interval then
      local number_of_refills = math.floor((now - updated_at)/interval)
    
      if tokens <= 0 then -- No more tokens were left before the refill.
        remaining = math.min(max_number_of_tokens, number_of_refills * refill_rate) - 1
      else
        remaining = math.min(max_number_of_tokens, tokens + number_of_refills * refill_rate) - 1
      end
      
      local last_refill = updated_at + number_of_refills * interval

      redis.call("HMSET", key, "updated_at", last_refill, "tokens", remaining)
      return {remaining, last_refill + interval}
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
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """

        key: str = f"{self.prefix}:{identifier}"

        async with self.redis:
            remaining_tokens: int
            next_refill_at: int

            remaining_tokens, next_refill_at = await self.redis.eval(
                script=TokenBucket.script,
                keys=[key],
                args=[
                    self.max_number_of_tokens,
                    self.interval,
                    self.refill_rate,
                    self.current_time_in_milliseconds,
                ],
            )

        return {
            "is_allowed": remaining_tokens >= 0,
            "limit": self.max_number_of_tokens,
            "remaining": remaining_tokens,
            "reset": next_refill_at,
        }

    async def remaining(self, identifier: str) -> int:
        """
        Determine the number of identifier's remaining requests.
        """

        key: str = f"{self.prefix}:{identifier}"

        async with self.redis:
            bucket: list[str | None] = await self.redis.hmget(
                key, "updated_at", "tokens"
            )

        if bucket[0] is None:  # The bucket does not exist yet.
            return self.max_number_of_tokens

        updated_at: float = float(bucket[0])

        tokens: int = int(cast(str, bucket[1]))  # Signal that it can't be None.

        if self.current_time_in_milliseconds < updated_at + self.interval:
            return tokens

        remaining_requests: int

        if tokens <= 0:  # No more tokens were left before the refill.
            remaining_requests = min(self.max_number_of_tokens, self.refill_rate)
        else:
            remaining_requests = min(
                self.max_number_of_tokens, tokens + self.refill_rate
            )

        return remaining_requests

    async def reset(self, identifier: str) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """

        key: str = f"{self.prefix}:{identifier}"

        now: float = self.current_time_in_milliseconds

        async with self.redis:
            updated_at: str | None = await self.redis.hget(key, "updated_at")

        if updated_at is None:  # The bucket does not exist.
            return -1

        float_updated_at = int(float(updated_at))

        if now < float_updated_at + self.interval:
            return float_updated_at + self.interval

        number_of_refills: int = floor((now - float_updated_at) / self.interval)

        last_refill: int = float_updated_at + number_of_refills * self.interval

        return last_refill + self.interval
