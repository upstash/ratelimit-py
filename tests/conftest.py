import pytest_asyncio
from pytest import fixture
from upstash_redis import Redis
from upstash_redis.asyncio import Redis as AsyncRedis


@fixture
def redis():
    with Redis.from_env() as redis:
        yield redis


@pytest_asyncio.fixture
async def async_redis():
    redis = AsyncRedis.from_env()
    async with redis:
        yield redis


@fixture(scope="session", autouse=True)
def setup_cleanup():
    with Redis.from_env() as redis:
        redis.flushdb()
        yield
        redis.flushdb()
