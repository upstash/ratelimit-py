from abc import ABC, abstractmethod
from typing import ClassVar, Literal
from upstash_py.client import Redis
from ratelimit_python.utils.time import to_milliseconds


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

        if identifier == "fixed_window_4":
            print("current:", current_requests)

        print()

        return current_requests <= self.max_number_of_requests
