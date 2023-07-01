from upstash_ratelimit.asyncio import RateLimit
from upstash_redis.asyncio import Redis
import asyncio

rate_limit = RateLimit(Redis.from_env(allow_telemetry=False))
fixed_window = rate_limit.fixed_window(max_number_of_requests=1, window=10, unit="s")

async def main():
    res = await fixed_window.block_until_ready('timeout_1', 10)
    print(f"res: {res}")



def lambda_handler(event, context):
    asyncio.run(main())

