from typing import ClassVar, Literal
from upstash_ratelimit.algorithms.algorithm import RateLimitAlgorithm
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from time import time_ns
from math import floor


class SlidingWindowCore(RateLimitAlgorithm):
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

        super().__init__(prefix)

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

    def limit(self, remaining_requests) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.

        Although we return the unix time when the next window begins (via "reset"), the limit is still enforced
        between the two intervals.
        """
        return {
            "is_allowed": remaining_requests >= 0,
            "limit": self.max_number_of_requests,
            "remaining": remaining_requests,
            "reset": floor((time_ns() / 1000000) / self.window) * self.window
            + self.window,
        }

    def remaining(
        self, stored_requests_in_current_window, stored_requests_in_previous_window
    ) -> int:
        """
        Determine the number of identifier's remaining requests.
        """
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

    def reset(self, exists) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """
        # The identifier hasn't made any requests in either the previous or the current window.
        if exists == 0:
            return -1

        return floor((time_ns() / 1000000) / self.window) * self.window + self.window
