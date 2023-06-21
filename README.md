# Upstash Rate Limit - python edition

upstash-ratelimit is a connectionless rate limiting library for python, designed to be used in serverless environments such as:
- AWS Lambda
- Google Cloud Functions
- and other environments where HTTP is preferred over TCP.

The sdk is currently compatible with python 3.10 and above.

<!-- toc -->

- [Quick Start](#quick-start)
  - [Install](#install)
    - [PyPi](#pypi)
  - [Setup database client](#setup-database-client)
  - [Usage](#usage)
  - [Telemetry](#telemetry)
  - [Block until ready](#block-until-ready)
  - [Timeout](#timeout)
  - [Rate-limiting outbound requests](#rate-limiting-outbound-requests)
- [Ratelimiting algorithms](#ratelimiting-algorithms)
  - [Fixed Window](#fixed-window)
    - [Pros:](#pros)
    - [Cons:](#cons)
    - [Usage:](#usage)
  - [Sliding Window](#sliding-window)
    - [Pros:](#pros-1)
    - [Cons:](#cons-1)
    - [Usage:](#usage-1)
  - [Token Bucket](#token-bucket)
    - [Pros:](#pros-2)
    - [Cons:](#cons-2)
    - [Usage:](#usage-2)
- [Contributing](#contributing)
  - [Preparing the environment](#preparing-the-environment)
  - [Adding new algorithms](#adding-new-algorithms)
  - [Running tests](#running-tests)
  - [Releasing](#releasing)

<!-- tocstop -->

# Quick Start

## Install

### PyPi

```bash
pip install upstash-ratelimit
```

If you are using a packaging and dependency management tool like [Poetry](https://python-poetry.org), you might want to check
the respective docs in regard to adding a dependency. For example, in a Poetry-managed virtual environment, you can use:

```bash
poetry add upstash-ratelimit
```

## Setup database client
To be able to use upstash-ratelimit, you need to create a database on [Upstash](https://console.upstash.com/) and instantiate
a client with the serverless driver:

```python
from upstash_redis.client import Redis

redis = Redis(url="UPSTASH_REDIS_REST_URL", token="UPSTASH_REDIS_REST_TOKEN")
```

Or, if you want to automatically load the credentials from the environment:

```python
from upstash_redis.client import Redis

redis = Redis.from_env()
```

The constructor can take even more optional parameters, some of them being (types expanded):

```python
url: str

token: str

rest_encoding: Literal["base64"] | Literal[False] = "base64"

rest_retries: int = 1

rest_retry_interval: int = 3 # In seconds.

allow_deprecated: bool = False

format_return: bool = True

allow_telemetry: bool = True
```


## Usage

```python
from upstash_ratelimit.limiter import RateLimit
from upstash_ratelimit.schema.response import RateLimitResponse

from upstash_redis.client import Redis

# Create a ratelimit instance and load the Redis credentials from the environment.
rate_limit = RateLimit(Redis.from_env())  # Optionally, pass your own client instance.

# Chose one algorithm.
fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

"""
Use a constant to limit all the requests together.
For enforcing individual limits, use some kind of identifying variable (IP address, API key, etc.).
"""
identifier: str = "constant"


async def main() -> str:
    request_result: RateLimitResponse = await fixed_window.limit(identifier)

    if not request_result["is_allowed"]:
        return f"{identifier} is rate-limited!"
    else:
        return "Request passed!"
```

You can also pass a `prefix` to the `RateLimit` constructor to distinguish between the keys used for rate limiting and others.
It defaults to `"ratelimit"`.

The `limit` method also returns some metadata that might be useful :

```python
from typing import TypedDict


class RateLimitResponse(TypedDict):
    """
    The response given by the rate-limiting methods, with additional metadata.
    """
    is_allowed: bool

    # The maximum number of requests allowed within a window.
    limit: int

    # How many requests can still be made within the window. If negative, it means the limit has been exceeded.
    remaining: int

    # The unix time in milliseconds when the next window begins.
    reset: int
```


## Telemetry
The underlying serverless driver can collect the following anonymous telemetry:
  - the runtime (ex: `python@v.3.10.0`)
  - the sdk or sdks you're using (ex: `upstash-py@development, upstash-ratelimit@v.0.1.0`)
  - the platform you're running on (ex: `AWS-lambda`)

If you want to opt-out, simply pass `allow_telemetry=False` to the Redis client.


## Block until ready
You also have the option to try and wait for a request to pass in the given timeout.
If the first request is blocked and the timeout exceeds the time needed for the next interval to come,
we wait and retry once that happens.

```python
from upstash_ratelimit.limiter import RateLimit
from upstash_ratelimit.schema.response import RateLimitResponse

from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env())

fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

identifier: str = "constant"


async def main() -> str:
    request_result: RateLimitResponse = await fixed_window.block_until_ready(identifier, timeout=2000)

    if not request_result["is_allowed"]:
        return f"The {identifier}'s request cannot be processed, even after 2 seconds."
    else:
        return "Request passed!"
```


## Timeout
If you worry that network issues can cause your application to reject requests, you can use python's `wait_for` to 
allow the requests which exceed a given timeout to pass regardless of what the current limit is.

```python
from upstash_ratelimit.limiter import RateLimit
from upstash_ratelimit.schema.response import RateLimitResponse

from upstash_redis.client import Redis

from asyncio import wait_for

rate_limit = RateLimit(Redis.from_env())

fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

identifier: str = "constant"


async def main() -> str:
    try:
        request_result: RateLimitResponse = await wait_for(fixed_window.limit(identifier), 2.0)  # Wait for two seconds.

        if not request_result["is_allowed"]:
            return f"{identifier} is rate-limited!"

        return "Request passed!"

    except TimeoutError:
        return "Request passed"
```


## Rate-limiting outbound requests
It's also possible to limit the number of requests you're making to an external API.

```python
from upstash_ratelimit.limiter import RateLimit
from upstash_ratelimit.schema.response import RateLimitResponse

from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env())

fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

identifier: str = "constant"  # Or, use an identifier to limit your requests to a certain endpoint.


async def main() -> str:
    request_result: RateLimitResponse = await fixed_window.limit(identifier)

    if not request_result["is_allowed"]:
        return f"{identifier} is rate-limited!"
    else:
        # Call the API
        # ...
        return "Request passed!"
```


# Ratelimiting algorithms

## Fixed Window
The time is divided into windows of fixed length and each window has a maximum number of allowed requests.

### Pros
- Very cheap in terms of data size and computation
- Newer requests are not starved due to a high burst in the past

### Cons
- Can cause high bursts at the window boundaries to leak through

### Usage

```python
from upstash_ratelimit.limiter import RateLimit

from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env())

fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)
```


## Sliding Window
Combined approach of sliding window and sliding logs that calculates a weighted score between two windows
to decide if a request should pass.

### Pros
- Approaches the issue near boundaries from fixed window.

### Cons
- More expensive in terms of storage and computation
- It's only an approximation because it assumes a uniform request flow in the previous window

### Usage

```python
from upstash_ratelimit.limiter import RateLimit

from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env())

sliding_window = rate_limit.sliding_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)
```

## Token Bucket
A bucket is filled with "max_number_of_tokens" that refill at "refill_rate" per "interval".
Each request tries to consume one token and if the bucket is empty, the request is rejected.

### Pros
- Bursts of requests are smoothed out, and you can process them at a constant rate
- Allows setting a higher initial burst limit by setting maxTokens higher than refillRate

### Cons
- Expensive in terms of computation

### Usage

```python
from upstash_ratelimit.limiter import RateLimit

from upstash_redis.client import Redis

rate_limit = RateLimit(Redis.from_env())

token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=2,
    refill_rate=1,
    interval=3,
    unit="s"
)
```

# Contributing

## Preparing the environment
This project uses [Poetry](https://python-poetry.org) for packaging and dependency management. 

See [this](https://python-poetry.org/docs/basic-usage/#using-your-virtual-environment) for a detailed explanation on how
to work with the virtual environment.

You will also need a database on [Upstash](https://console.upstash.com/). If you already have one, make sure to empty it before running 
tests. You can do so by sending `FLUSHDB` from the console.


## Adding new algorithms
All the algorithms subclass and implement abstract [RateLimitAlgorithm](upstash_ratelimit/algorithm.py)'s methods.

They are also grouped in the [RateLimit](upstash_ratelimit/limiter.py) class for ease of use.


## Running tests
All tests live in the [test](./tests) folder.

Only the logic of 100%-accuracy algorithms and other utility functions are unit-tested.

To run all the tests, make sure you are in the `tests` folder and have the poetry virtual environment activated with all 
the necessary dependencies. Set the `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` environment variables and run:

```bash
poetry run pytest --import-mode importlib
```

The reason we need to use the `importlib` mode is because there are multiple test files with the same name. See the 
[pytest docs](https://docs.pytest.org/en/stable/explanation/pythonpath.html#import-modes) for more info.

**Warning**: The current evaluation speed of the tests does not take the HTTP requests duration into account. 
Because of that, if a request takes more than 2 seconds to complete, a test might fail.


## Releasing
To create a new release, first use Poetry's [version](https://python-poetry.org/docs/cli/#version) command.

You will then need to connect your PyPi API token to Poetry. 
A simple tutorial showcasing how to do it was posted by Tony Tran
[on DigitalOcean](https://www.digitalocean.com/community/tutorials/how-to-publish-python-packages-to-pypi-using-poetry-on-ubuntu-22-04)

From there, use `poetry publish --build`.