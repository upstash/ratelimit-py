from ratelimit_python.limiter import RateLimit
from upstash_py.client import Redis

rate_limit = RateLimit(Redis.from_env(allow_telemetry=False))
