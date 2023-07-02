
from asyncio import sleep
from time import time_ns
from upstash_ratelimit.schema.response import RateLimitResponse


class AsyncBlocker:
    async def limit(self, identifier) -> RateLimitResponse:
        ...

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