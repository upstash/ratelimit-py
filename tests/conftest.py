from upstash_redis import Redis

redis = Redis.from_env()

def pytest_configure():
    redis.flushall()


