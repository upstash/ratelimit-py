from upstash_ratelimit.limiter import RateLimit
from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env(allow_telemetry=False))
