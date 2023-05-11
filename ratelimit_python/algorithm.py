from abc import ABC, abstractmethod
from typing import ClassVar
from upstash_py.client import Redis


class RateLimitAlgorithm(ABC):
    @abstractmethod
    def __init__(self, redis: Redis, prefix: str):
        """
        :param redis: The Redis client that will be used to execute the algorithm's commands.
        :param prefix: A prefix to distinguish between the keys used for rate limiting and others.
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

    def __init__(self, max_number_of_requests: int, window: int, redis: Redis, prefix: str):
        """
        :param max_number_of_requests: The number of requests allowed within the window.
        :param window: The time unit in requests are limited, in milliseconds.
        :param redis: The Redis client that will be used to execute the algorithm's commands.
        :param prefix: A prefix to distinguish between the keys used for rate limiting and others.
        """

        super().__init__(redis, prefix)

        self.max_number_of_requests = max_number_of_requests
        self.window = window

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
