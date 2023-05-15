from abc import ABC, abstractmethod
from typing import ClassVar, Literal
from upstash_py.client import Redis
from ratelimit_python.utils.time import to_milliseconds
from time import time_ns
from math import floor


class RateLimitAlgorithm(ABC):
    @abstractmethod
    def __init__(self, redis: Redis, prefix: str):
        """
        :param redis: the Redis client that will be used to execute the algorithm's commands
        :param prefix: a prefix to distinguish between the keys used for rate limiting and others
        """

        self.redis = redis
        self.prefix = prefix

    @property
    @abstractmethod
    def script(self) -> str:
        """
        Setting this as read-only property enforces the subclasses to implement it without using a setter.
        However, replacing it with a class attribute has the same effect.
        """

    @abstractmethod
    async def is_allowed(self, identifier: str) -> bool:
        """
        Determine whether the identifier's request should pass.
        """


class FixedWindow(RateLimitAlgorithm):
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
        prefix: str,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms",
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

    async def is_allowed(self, identifier: str) -> bool:
        """
        Determine whether the identifier's request should pass.
        """

        key: str = f'{self.prefix}:{identifier}'

        async with self.redis:
            current_requests: int = await self.redis.eval(
                script=FixedWindow.script,
                keys=[key],
                arguments=[self.window]
            )

        return current_requests <= self.max_number_of_requests


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
        prefix: str,
        max_number_of_requests: int,
        window: int,
        unit: Literal["ms", "s", "m", "h", "d"] = "ms"
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

    async def is_allowed(self, identifier: str) -> bool:
        """
        Determine whether the identifier's request should pass.
        """

        now: float = time_ns() / 1000000  # Convert to milliseconds and round down.

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

        return remaining_requests >= 0
