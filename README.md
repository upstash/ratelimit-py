# Upstash Ratelimit Python SDK

upstash-ratelimit is a connectionless rate limiting library for Python, designed to be used in serverless environments such as:
- AWS Lambda
- Vercel Serverless
- Google Cloud Functions
- and other environments where HTTP is preferred over TCP.

The SDK is currently compatible with Python 3.8 and above.

<!-- toc -->
- [Upstash Ratelimit Python SDK](#upstash-ratelimit-python-sdk)
- [Quick Start](#quick-start)
  - [Install](#install)
  - [Create database](#create-database)
  - [Usage](#usage)
  - [Block until ready](#block-until-ready)
  - [Using multiple limits](#using-multiple-limits)
- [Ratelimiting algorithms](#ratelimiting-algorithms)
  - [Fixed Window](#fixed-window)
    - [Pros](#pros)
    - [Cons](#cons)
    - [Usage](#usage-1)
  - [Sliding Window](#sliding-window)
    - [Pros](#pros-1)
    - [Cons](#cons-1)
    - [Usage](#usage-2)
  - [Token Bucket](#token-bucket)
    - [Pros](#pros-2)
    - [Cons](#cons-2)
    - [Usage](#usage-3)
- [Contributing](#contributing)
  - [Preparing the environment](#preparing-the-environment)
  - [Running tests](#running-tests)
<!-- tocstop -->

# Quick Start

## Install

```bash
pip install upstash-ratelimit
```

## Create database
To be able to use upstash-ratelimit, you need to create a database on [Upstash](https://console.upstash.com/).

## Usage

For possible Redis client configurations, have a look at the [Redis SDK repository](https://github.com/upstash/redis-python).

> This library supports asyncio as well. To use it, import the asyncio-based
  variant from the `upstash_ratelimit.asyncio` module.

```python
from upstash_ratelimit import Ratelimit, FixedWindow
from upstash_redis import Redis

# Create a new ratelimiter, that allows 10 requests per 10 seconds
ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=FixedWindow(max_requests=10, window=10),
    # Optional prefix for the keys used in Redis. This is useful
    # if you want to share a Redis instance with other applications
    # and want to avoid key collisions. The default prefix is
    # "@upstash/ratelimit"
    prefix="@upstash/ratelimit",
)

# Use a constant string to limit all requests with a single ratelimit
# Or use a user ID, API key or IP address for individual limits.
identifier = "api"
response = ratelimit.limit(identifier)

if not response.allowed:
    print("Unable to process at this time")
else:
    do_expensive_calculation()
    print("Here you go!")

```

The `limit` method also returns the following metadata:


```python
@dataclasses.dataclass
class Response:
    allowed: bool
    """
    Whether the request may pass(`True`) or exceeded the limit(`False`)
    """

    limit: int
    """
    Maximum number of requests allowed within a window.
    """

    remaining: int
    """
    How many requests the user has left within the current window.
    """

    reset: float
    """
    Unix timestamp in seconds when the limits are reset
    """
```

## Block until ready

You also have the option to try and wait for a request to pass in the given timeout.

It is very similar to the `limit` method and takes an identifier and returns the same 
response. However if the current limit has already been exceeded, it will automatically 
wait until the next window starts and will try again. Setting the timeout parameter (in seconds) will cause the method to block a finite amount of time.

```python
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

# Create a new ratelimiter, that allows 10 requests per 10 seconds
ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=SlidingWindow(max_requests=10, window=10),
)

response = ratelimit.block_until_ready("id", timeout=30)

if not response.allowed:
    print("Unable to process, even after 30 seconds")
else:
    do_expensive_calculation()
    print("Here you go!")
```


## Using multiple limits
Sometimes you might want to apply different limits to different users. For example you might want to allow 10 requests per 10 seconds for free users, but 60 requests per 10 seconds for paid users.

Here's how you could do that:

```python
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

class MultiRL:
    def __init__(self) -> None:
        redis = Redis.from_env()
        self.free = Ratelimit(
            redis=redis,
            limiter=SlidingWindow(max_requests=10, window=10),
            prefix="ratelimit:free",
        )

        self.paid = Ratelimit(
            redis=redis,
            limiter=SlidingWindow(max_requests=60, window=10),
            prefix="ratelimit:paid",
        )

# Create a new ratelimiter, that allows 10 requests per 10 seconds
ratelimit = MultiRL()

ratelimit.free.limit("userIP")
ratelimit.paid.limit("userIP")
```

# Ratelimiting algorithms

## Fixed Window

This algorithm divides time into fixed durations/windows. For example each window is 10 seconds long. When a new request comes in, the current time is used to determine the window and a counter is increased. If the counter is larger than the set limit, the request is rejected.

### Pros
- Very cheap in terms of data size and computation
- Newer requests are not starved due to a high burst in the past

### Cons
- Can cause high bursts at the window boundaries to leak through
- Causes request stampedes if many users are trying to access your server, whenever a new window begins

### Usage

```python
from upstash_ratelimit import Ratelimit, FixedWindow
from upstash_redis import Redis

ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=FixedWindow(max_requests=10, window=10),
)
```

## Sliding Window

Builds on top of fixed window but instead of a fixed window, we use a rolling window. Take this example: We have a rate limit of 10 requests per 1 minute. We divide time into 1 minute slices, just like in the fixed window algorithm. Window 1 will be from 00:00:00 to 00:01:00 (HH:MM:SS). Let's assume it is currently 00:01:15 and we have received 4 requests in the first window and 5 requests so far in the current window. The approximation to determine if the request should pass works like this:

```python
limit = 10

# 4 request from the old window, weighted + requests in current window
rate = 4 * ((60 - 15) / 60) + 5 = 8

return rate < limit # True means we should allow the request
```

### Pros
- Solves the issue near boundary from fixed window.

### Cons
- More expensive in terms of storage and computation
- It's only an approximation because it assumes a uniform request flow in the previous window

### Usage

```python
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=SlidingWindow(max_requests=10, window=10),
)
```

## Token Bucket

Consider a bucket filled with maximum number of tokens that refills constantly at a rate per interval. Every request will remove one token from the bucket and if there is no token to take, the request is rejected.

### Pros
- Bursts of requests are smoothed out and you can process them at a constant rate.
- Allows setting a higher initial burst limit by setting maximum number of tokens higher than the refill rate

### Cons
- Expensive in terms of computation

### Usage

```python
from upstash_ratelimit import Ratelimit, TokenBucket
from upstash_redis import Redis

ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=TokenBucket(max_tokens=10, refill_rate=5, interval=10),
)
```

# Custom Rates

When rate limiting, you may want different requests to consume different amounts of tokens.
This could be useful when processing batches of requests where you want to rate limit based
on items in the batch or when you want to rate limit based on the number of tokens.

To achieve this, you can simply pass `rate` parameter when calling the limit method:

```python

from upstash_ratelimit import Ratelimit, FixedWindow
from upstash_redis import Redis

ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=FixedWindow(max_requests=10, window=10),
)

# pass rate as 5 to subtract 5 from the number of
# allowed requests in the window:
identifier = "api"
response = ratelimit.limit(identifier, rate=5)
```

# Contributing

## Preparing the environment
This project uses [Poetry](https://python-poetry.org) for packaging and dependency management. Make sure you are able to create the poetry shell with relevant dependencies.

You will also need a database on [Upstash](https://console.upstash.com/).

## Running tests
To run all the tests, make sure the poetry virtual environment activated with all 
the necessary dependencies. Set the `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` environment variables and run:

```bash
poetry run pytest
```
