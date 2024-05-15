import abc
import dataclasses
from collections.abc import Generator
from typing import Any, Callable

from upstash_redis import Redis
from upstash_redis.asyncio import Redis as AsyncRedis

from upstash_ratelimit.typing import UnitT
from upstash_ratelimit.utils import ms_to_s, now_ms, to_ms


@dataclasses.dataclass
class Response:
    allowed: bool
    """
    Whether the request may pass(`True`) or exceeded the limit(`False`)
    """

    limit: int
    """
    Maximum number of requests allowed within a window.
    """

    remaining: int
    """
    How many requests the user has left within the current window.
    """

    reset: float
    """
    Unix timestamp in seconds when the limits are reset
    """


class Limiter(abc.ABC):
    @abc.abstractmethod
    def limit(self, redis: Redis, identifier: str, rate: int = 1) -> Response:
        pass

    @abc.abstractmethod
    async def limit_async(self, redis: AsyncRedis, identifier: str, rate: int = 1) -> Response:
        pass

    @abc.abstractmethod
    def get_remaining(self, redis: Redis, identifier: str) -> int:
        pass

    @abc.abstractmethod
    async def get_remaining_async(self, redis: AsyncRedis, identifier: str) -> int:
        pass

    @abc.abstractmethod
    def get_reset(self, redis: Redis, identifier: str) -> float:
        pass

    @abc.abstractmethod
    async def get_reset_async(self, redis: AsyncRedis, identifier: str) -> float:
        pass


def _with_at_most_one_request(redis: Redis, generator: Generator) -> Any:
    """
    A function that makes at most one HTTP request over the
    given Redis instance.

    If the generator needs to execute a command, this function
    takes the command name and args from the generator,
    executes the given command, and passes the result
    of the command back to the generator. Then, it
    takes the final response from the generator and
    returns it.

    If the generator does not need to execute a command,
    it returns the result directly.
    """

    command_name, command_args = next(generator)
    if not command_name:
        # No need to execute a command
        response = next(generator)
        return response

    command: Callable = getattr(redis, command_name)
    command_response = command(*command_args)
    response = generator.send(command_response)
    return response


async def _with_at_most_one_request_async(
    redis: AsyncRedis, generator: Generator
) -> Any:
    """
    Async variant of the `_with_one_request_fn` defined above.
    """

    command_name, command_args = next(generator)
    if not command_name:
        # No need to execute a command
        response = next(generator)
        return response

    command: Callable = getattr(redis, command_name)
    command_response = await command(*command_args)
    response = generator.send(command_response)
    return response


class AbstractLimiter(Limiter):
    @abc.abstractmethod
    def _limit(self, identifier: str, rate: int = 1) -> Generator:
        pass

    def limit(self, redis: Redis, identifier: str, rate: int = 1) -> Response:
        response: Response = _with_at_most_one_request(redis, self._limit(identifier, rate))
        return response

    async def limit_async(self, redis: AsyncRedis, identifier: str, rate: int = 1) -> Response:
        response: Response = await _with_at_most_one_request_async(
            redis, self._limit(identifier, rate)
        )
        return response

    @abc.abstractmethod
    def _get_remaining(self, identifier: str) -> Generator:
        pass

    def get_remaining(self, redis: Redis, identifier: str) -> int:
        remaining: int = _with_at_most_one_request(
            redis, self._get_remaining(identifier)
        )
        return remaining

    async def get_remaining_async(self, redis: AsyncRedis, identifier: str) -> int:
        remaining: int = await _with_at_most_one_request_async(
            redis, self._get_remaining(identifier)
        )
        return remaining

    @abc.abstractmethod
    def _get_reset(self, identifier: str) -> Generator:
        pass

    def get_reset(self, redis: Redis, identifier: str) -> float:
        reset: float = _with_at_most_one_request(redis, self._get_reset(identifier))
        return reset

    async def get_reset_async(self, redis: AsyncRedis, identifier: str) -> float:
        reset: float = await _with_at_most_one_request_async(
            redis, self._get_reset(identifier)
        )
        return reset


class FixedWindow(AbstractLimiter):
    """
    The time is divided into windows of fixed length, and each request inside
    a window increases a counter.

    Once the counter reaches the maximum allowed number, all further requests
    are rejected.

    Pros:
    - Newer requests are not starved by old ones.
    - Low storage cost.

    Cons:
    - A burst of requests near the boundary of a window can result in twice the
      rate of requests being processed because two windows will be filled with
      requests quickly.
    """

    SCRIPT = """
    local key           = KEYS[1]
    local window        = ARGV[1]
    local increment_by  = ARGV[2] -- increment rate per request at a given value, default is 1

    local r = redis.call("INCRBY", key, increment_by)
    if r == tonumber(increment_by) then
    -- The first time this key is set, the value will be equal to increment_by.
    -- So we only need the expire command once
    redis.call("PEXPIRE", key, window)
    end

    return r
    """

    def __init__(self, max_requests: int, window: int, unit: UnitT = "s") -> None:
        """
        :param max_requests: Maximum number of requests allowed within a window
        :param window: The number of time units in a window
        :param unit: The unit of time
        """

        assert max_requests > 0
        assert window > 0

        self._max_requests = max_requests
        self._window = to_ms(window, unit)

    def _limit(self, identifier: str, rate: int = 1) -> Generator:
        curr_window = now_ms() // self._window
        key = f"{identifier}:{curr_window}"

        num_requests = yield (
            "eval",
            (FixedWindow.SCRIPT, [key], [self._window, rate]),
        )

        yield Response(
            allowed=num_requests <= self._max_requests,
            limit=self._max_requests,
            remaining=max(0, self._max_requests - num_requests),
            reset=ms_to_s((curr_window + 1) * self._window),
        )

    def _get_remaining(self, identifier: str) -> Generator:
        curr_window = now_ms() // self._window
        key = f"{identifier}:{curr_window}"

        num_requests = yield (
            "get",
            (key,),
        )

        if num_requests is None:
            yield self._max_requests

        yield max(0, self._max_requests - int(num_requests))  # type: ignore[arg-type]

    def _get_reset(self, _: str) -> Generator:
        yield (None, None)  # Signal that we don't need to make a remote call

        curr_window = now_ms() // self._window
        yield ms_to_s((curr_window + 1) * self._window)


class SlidingWindow(AbstractLimiter):
    """
    Combined approach of sliding logs and fixed window with lower storage
    costs than sliding logs and improved boundary behavior by calculating a
    weighted score between two windows.

    Pros:
    - Good performance allows this to scale to very high loads.
    """

    SCRIPT = """
    local current_key  = KEYS[1]           -- identifier including prefixes
    local previous_key = KEYS[2]           -- key of the previous bucket
    local tokens       = tonumber(ARGV[1]) -- tokens per window
    local now          = ARGV[2]           -- current timestamp in milliseconds
    local window       = ARGV[3]           -- interval in milliseconds
    local increment_by = ARGV[4]           -- increment rate per request at a given value, default is 1

    local requests_in_current_window = redis.call("GET", current_key)
    if requests_in_current_window == false then
        requests_in_current_window = 0
    end

    local requests_in_previous_window = redis.call("GET", previous_key)
    if requests_in_previous_window == false then
        requests_in_previous_window = 0
    end
    local percentage_in_current = ( now % window ) / window
    -- weighted requests to consider from the previous window
    requests_in_previous_window = math.floor(( 1 - percentage_in_current ) * requests_in_previous_window)
    if requests_in_previous_window + requests_in_current_window >= tokens then
        return -1
    end

    local new_value = redis.call("INCRBY", current_key, increment_by)
    if new_value == tonumber(increment_by) then
        -- The first time this key is set, the value will be equal to increment_by.
        -- So we only need the expire command once
        redis.call("PEXPIRE", current_key, window * 2 + 1000) -- Enough time to overlap with a new window + 1 second
    end
    return tokens - ( new_value + requests_in_previous_window )
    """

    def __init__(self, max_requests: int, window: int, unit: UnitT = "s") -> None:
        """
        :param max_requests: Maximum number of requests allowed within a window
        :param window: The number of time units in a window
        :param unit: The unit of time
        """

        assert max_requests > 0
        assert window > 0

        self._max_requests = max_requests
        self._window = to_ms(window, unit)

    def _limit(self, identifier: str, rate: int = 1) -> Generator:
        now = now_ms()

        curr_window = now // self._window
        key = f"{identifier}:{curr_window}"

        prev_window = curr_window - 1
        prev_key = f"{identifier}:{prev_window}"

        remaining = yield (
            "eval",
            (
                SlidingWindow.SCRIPT,
                [key, prev_key],
                [self._max_requests, now, self._window, rate],
            ),
        )

        yield Response(
            allowed=remaining >= 0,
            limit=self._max_requests,
            remaining=max(0, remaining),
            reset=ms_to_s((curr_window + 1) * self._window),
        )

    def _get_remaining(self, identifier: str) -> Generator:
        now = now_ms()

        window = now // self._window
        key = f"{identifier}:{window}"

        prev_window = window - 1
        prev_key = f"{identifier}:{prev_window}"

        num_requests_, prev_num_requests_ = yield (
            "mget",
            (key, prev_key),
        )
        num_requests = int(num_requests_ or 0)
        prev_num_requests = int(prev_num_requests_ or 0)

        prev_window_weight = 1 - ((now % self._window) / self._window)
        prev_num_requests = int(prev_num_requests * prev_window_weight)

        remaining = self._max_requests - (prev_num_requests + num_requests)
        yield max(0, remaining)

    def _get_reset(self, _: str) -> Generator:
        yield (None, None)  # Signal that we don't need to make a remote call

        curr_window = now_ms() // self._window
        yield ms_to_s((curr_window + 1) * self._window)


class TokenBucket(AbstractLimiter):
    """
    A bucket is filled with maximum number of tokens that refill at a given
    rate per interval.

    Each request tries to consume one token and if the bucket is empty,
    the request is rejected.

    Pros:
    - Bursts of requests are smoothed out so that they can be processed at
      a constant rate.
    - Allows to set a higher initial burst limit by setting maximum number
      of tokens higher than the refill rate.
    """

    SCRIPT = """
    local key          = KEYS[1]           -- identifier including prefixes
    local max_tokens   = tonumber(ARGV[1]) -- maximum number of tokens
    local interval     = tonumber(ARGV[2]) -- size of the window in milliseconds
    local refill_rate  = tonumber(ARGV[3]) -- how many tokens are refilled after each interval
    local now          = tonumber(ARGV[4]) -- current timestamp in milliseconds
    local increment_by = tonumber(ARGV[5]) -- how many tokens to consume, default is 1
            
    local bucket = redis.call("HMGET", key, "refilled_at", "tokens")
            
    local refilled_at
    local tokens

    if bucket[1] == false then
        refilled_at = now
        tokens = max_tokens
    else
        refilled_at = tonumber(bucket[1])
        tokens = tonumber(bucket[2])
    end
            
    if now >= refilled_at + interval then
        local num_refills = math.floor((now - refilled_at) / interval)
        tokens = math.min(max_tokens, tokens + num_refills * refill_rate)

        refilled_at = refilled_at + num_refills * interval
    end

    if tokens == 0 then
        return {-1, refilled_at + interval}
    end

    local remaining = tokens - increment_by
    local expire_at = math.ceil(((max_tokens - remaining) / refill_rate)) * interval
            
    redis.call("HSET", key, "refilled_at", refilled_at, "tokens", remaining)
    redis.call("PEXPIRE", key, expire_at)
    return {remaining, refilled_at + interval}
    """

    def __init__(
        self, max_tokens: int, refill_rate: int, interval: int, unit: UnitT = "s"
    ) -> None:
        """
        :param max_tokens: Maximum number of tokens in a bucket. Since a newly
            created bucket starts with this many tokens, it can be used to
            allow higher burst limits.
        :param refill_rate: The number of tokens that are refilled per interval
        :param interval: The number of time units between each refill
        :param unit: The unit of time
        """
        assert max_tokens > 0
        assert refill_rate > 0
        assert interval > 0

        self._max_tokens = max_tokens
        self._refill_rate = refill_rate
        self._interval = to_ms(interval, unit)

    def _limit(self, identifier: str, rate: int = 1) -> Generator:
        remaining, refill_at = yield (
            "eval",
            (
                TokenBucket.SCRIPT,
                [identifier],
                [self._max_tokens, self._interval, self._refill_rate, now_ms(), rate],
            ),
        )

        yield Response(
            allowed=remaining >= 0,
            limit=self._max_tokens,
            remaining=max(0, remaining),
            reset=ms_to_s(refill_at),
        )

    def _get_remaining(self, identifier: str) -> Generator:
        now = now_ms()

        refilled_at_, tokens_ = yield (
            "hmget",
            (identifier, "refilled_at", "tokens"),
        )

        if refilled_at_ is None:
            yield self._max_tokens

        refilled_at = int(refilled_at_)  # type: ignore[arg-type]
        tokens = int(tokens_)  # type: ignore[arg-type]

        if now >= refilled_at + self._interval:
            num_refills = (now - refilled_at) // self._interval
            tokens = min(self._max_tokens, tokens + num_refills * self._refill_rate)

        yield tokens

    def _get_reset(self, identifier: str) -> Generator:
        now = now_ms()

        refilled_at_ = yield (
            "hget",
            (identifier, "refilled_at"),
        )

        if refilled_at_ is None:
            yield ms_to_s(now)

        refilled_at = int(refilled_at_)  # type: ignore[arg-type]
        if now >= refilled_at + self._interval:
            num_refills = (now - refilled_at) // self._interval
            refilled_at = refilled_at + num_refills * self._interval

        yield ms_to_s(refilled_at + self._interval)
