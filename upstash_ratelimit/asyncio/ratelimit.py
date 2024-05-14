import asyncio
from typing import Optional

from upstash_redis.asyncio import Redis

from upstash_ratelimit.limiter import Limiter, Response
from upstash_ratelimit.utils import merge_telemetry, now_s


class Ratelimit:
    """
    Provides means of ratelimitting over the HTTP-based
    Upstash Redis client.
    """

    def __init__(
        self, redis: Redis, limiter: Limiter, prefix: str = "@upstash/ratelimit"
    ) -> None:
        """
        :param redis: Upstash Redis instance to use.
        :param limiter: Ratelimiter to use. Available limiters are \
            `FixedWindow`, `SlidingWindow`, and `TokenBucket` which are provided \
            in the `limiter` module. 
        :param prefix: Prefix to distinguish the keys used in the ratelimit \
            logic from others, in case the same Redis instance is reused between \
            different applications. 
        """

        self._redis = redis
        merge_telemetry(redis)

        self._limiter = limiter
        self._prefix = prefix

    async def limit(self, identifier: str, rate: int = 1) -> Response:
        """
        Determines if a request should pass or be rejected based on the identifier 
        and previously chosen ratelimit.

        Use this if you want to reject all requests that you can not handle 
        right now.

        .. code-block:: python

            from upstash_ratelimit.asyncio import Ratelimit, SlidingWindow
            from upstash_redis.asyncio import Redis

            ratelimit = Ratelimit(
                redis=Redis.from_env(),
                limiter=SlidingWindow(max_requests=10, window=10, unit="s"),
            )

            async def main() -> None:
                response = await ratelimit.limit("some-id")
                if not response.allowed:
                    print("Ratelimitted!")

                print("Good to go!")
        
        :param identifier: Identifier to ratelimit. Use a constant string to \
            limit all requests, or user ids, API keys, or IP addresses for \
            individual limits.
        :param rate: Rate with which to subtract from the limit of the \
            identifier.
        """

        key = f"{self._prefix}:{identifier}"
        return await self._limiter.limit_async(self._redis, key, rate)

    async def block_until_ready(self, identifier: str, timeout: float, rate: int = 1) -> Response:
        """
        Blocks until the request may pass or timeout is reached.
        
        This method blocks until the request may be processed or the timeout 
        has been reached.

        Use this if you want to delay the request until it is ready to get 
        processed.

        .. code-block:: python

            from upstash_ratelimit.asyncio import Ratelimit, SlidingWindow
            from upstash_redis.asyncio import Redis

            ratelimit = Ratelimit(
                redis=Redis.from_env(),
                lmiter=SlidingWindow(max_requests=10, window=10, unit="s"),
            )

            async def main() -> None:
                response = await ratelimit.block_until_ready("some-id", 60)
                if not response.allowed:
                    print("Ratelimitted!")

                print("Good to go!")
        
        :param identifier: Identifier to ratelimit. Use a constant string to \
            limit all requests, or user ids, API keys, or IP addresses for \
            individual limits.
        :param timeout: Maximum time in seconds to wait until the request \
            may pass.
        :param rate: Rate with which to subtract from the limit of the \
            identifier.
        """

        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        response: Optional[Response] = None
        deadline = now_s() + timeout

        while True:
            response = await self.limit(identifier, rate)
            if response.allowed:
                break

            wait = max(0, min(response.reset, deadline) - now_s())
            await asyncio.sleep(wait)

            if now_s() > deadline:
                break

        return response

    async def get_remaining(self, identifier: str) -> int:
        """
        Returns the number of requests left for the given identifier.
        """

        key = f"{self._prefix}:{identifier}"
        return await self._limiter.get_remaining_async(self._redis, key)

    async def get_reset(self, identifier: str) -> float:
        """
        Returns the UNIX timestamp in seconds when the remaining
        requests will be reset or replenished.
        """

        key = f"{self._prefix}:{identifier}"
        return await self._limiter.get_reset_async(self._redis, key)
