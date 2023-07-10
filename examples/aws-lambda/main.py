from upstash_redis import Redis

from upstash_ratelimit import FixedWindow, Ratelimit

ratelimit = Ratelimit(
    redis=Redis.from_env(allow_telemetry=False),
    limiter=FixedWindow(max_requests=1, window=10),
)


def lambda_handler(event, context):
    response = ratelimit.limit("id")
    print(response)
