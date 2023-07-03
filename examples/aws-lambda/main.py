from upstash_ratelimit.asyncio import RateLimit as ARateLimit
from upstash_redis.asyncio import Redis as ARedis
import asyncio

from upstash_ratelimit import RateLimit
from upstash_redis import Redis

arate_limit = ARateLimit(ARedis.from_env(allow_telemetry=False))
afixed_window = arate_limit.fixed_window(max_number_of_requests=1, window=10, unit="s")


async def main():
    res = await afixed_window.block_until_ready("timeout_1", 10)
    print(f"res: {res}")


def lambda_handler(event, context):
    asyncio.run(main())

    rate_limit = RateLimit(prefix="test")

    fixed_window = rate_limit.fixed_window(max_number_of_requests=2, window=5, unit="s")

    res = fixed_window.block_until_ready("timeout_sync", 10)
    print(f"sync res: {res}")
