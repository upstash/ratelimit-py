# Upstash Rate Limit - python edition

upstash-ratelimit is a connectionless rate limiting library for python, designed to be used in serverless environments such as:
- AWS Lambda
- Google Cloud Functions
- and other environments where HTTP is preferred over TCP.

The sdk is currently compatible with python 3.10 and above.

<!-- toc -->

- [Quick Start](#quick-start)
  - [Install](#install)
    - [pypi](#pypi)
  - [Setup database client](#setup-database-client)
  - [Usage](#usage)
  - [Telemetry](#telemetry)
  - [Block until ready](#block-until-ready)
  - [Timeout](#timeout)
  - [Use with mypy](#use-with-mypy)
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
  - [Running tests](#running-tests)
  - [Adding new algorithms](#adding-new-algorithms)
  - [Releasing](#releasing)

<!-- tocstop -->

# Quick Start

## Install

### pypi

```bash
pip install upstash-ratelimit
```

## Setup database client
To be able to use upstash-ratelimit, you need to create a database on [Upstash](https://console.upstash.com/) and instantiate
a client with the serverless driver (which will be released separately in the following months).

```python
from upstash_py.client import Redis

redis = Redis(url="UPSTASH_REDIS_REST_URL", token="UPSTASH_REDIS_REST_TOKEN")
```

Or, if you want to automatically load the credentials from the environment

```python
from upstash_py.client import Redis

redis = Redis.from_env()
```

The constructor can take even more optional parameters, which are (types expanded):
```python
from typing import Literal
from typing import TypedDict


class TelemetryData(TypedDict, total=False):
    runtime: str
    sdk: str
    platform: str


url: str

token: str

rest_encoding: str | Literal[False] = "base64"

rest_retries: int = 1

rest_retry_interval: int = 3 # In seconds.

allow_deprecated: bool = False

format_return: bool = True

allow_telemetry: bool = True

telemetry_data: TelemetryData | None = None
```

## Usage
```python
from ratelimit_python.limiter import RateLimit
from ratelimit_python.schema.response import RateLimitResponse

from upstash_py.client import Redis

# Create a ratelimit instance and load the Redis credentials from environment.
rate_limit = RateLimit(Redis.from_env()) # Optionally, pass your own client instance.

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

request_result: RateLimitResponse = await fixed_window.limit(identifier)

if not request_result["is_allowed"]:
    print(f"{identifier} is rate-limited!")
else:
    print("Request passed!")
```

You can also pass a `prefix` to the `RateLimit` constructor to distinguish between the keys used for rate limiting and others.
It defaults to `"ratelimit"`.

The `limit` method also returns some metadata that might be useful 

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

If you want to opt out, simply pass `allow_telemetry=False` to the Redis client.

## Block until ready
You also have the option to try and wait for a request to pass in the given timeout.
If the first request is blocked and the timeout exceeds the time needed for the next interval to come,
we wait and retry once that happens.

```python
from ratelimit_python.limiter import RateLimit
from ratelimit_python.schema.response import RateLimitResponse

from upstash_py.client import Redis

rate_limit = RateLimit(Redis.from_env())

fixed_window = rate_limit.fixed_window(
  max_number_of_requests=1,
  window=3,
  unit="s"
)

identifier: str = "constant"

request_result: RateLimitResponse = await fixed_window.block_until_ready(identifier, timeout=2000)

if not request_result["is_allowed"]:
    print(f"The {identifier}'s request cannot be processed, even after 2 seconds.")
else:
    print("Request passed!")
```

## Timeout
If you worry that network issues can cause your application to reject requests, you can use python's `wait_for` to 
allow the requests which exceed a given timeout to pass regardless of what the current limit is.

```python
from ratelimit_python.limiter import RateLimit
from ratelimit_python.schema.response import RateLimitResponse

from upstash_py.client import Redis

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
    request_result: RateLimitResponse = await wait_for(fixed_window.limit(identifier), 2.0) # Wait for two seconds.
    
    if not request_result["is_allowed"]:
        return f"{identifier} is rate-limited!"
    
    return "Request passed!"
  
  except TimeoutError:
    return "Request passed"
```

## Use with mypy
TBA after release.