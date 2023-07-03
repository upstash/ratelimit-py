from typing import ClassVar, Literal, cast
from upstash_ratelimit.algorithms.algorithm import RateLimitAlgorithm
from upstash_ratelimit.utils.time import to_milliseconds
from upstash_ratelimit.config import PREFIX
from upstash_ratelimit.schema.response import RateLimitResponse
from math import floor


class TokenBucketCore(RateLimitAlgorithm):
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

        super().__init__(prefix)

        self.max_number_of_tokens = max_number_of_tokens
        self.refill_rate = refill_rate
        self.interval = interval if unit == "ms" else to_milliseconds(interval, unit)

    def limit(self, remaining_tokens, next_refill_at) -> RateLimitResponse:
        """
        Increment identifier's request counter, determine whether it should pass
        and return additional metadata.
        """
        return {
            "is_allowed": remaining_tokens >= 0,
            "limit": self.max_number_of_tokens,
            "remaining": remaining_tokens,
            "reset": next_refill_at,
        }

    def remaining(self, bucket) -> int:
        """
        Determine the number of identifier's remaining requests.
        """
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

    def reset(self, updated_at) -> int:
        """
        Determine the unix time in milliseconds when the next window begins.

        If the identifier is not rate-limited, the returned value will be -1.
        """
        now: float = self.current_time_in_milliseconds

        if updated_at is None:  # The bucket does not exist.
            return -1

        float_updated_at = int(float(updated_at))

        if now < float_updated_at + self.interval:
            return float_updated_at + self.interval

        number_of_refills: int = floor((now - float_updated_at) / self.interval)

        last_refill: int = float_updated_at + number_of_refills * self.interval

        return last_refill + self.interval


# TODO: super()__init__(prefix) is useless.
