# Upstash Rate Limit - python edition

upstash-ratelimit is a connectionless rate limiting library for python, designed to be used in serverless environments such as:
- AWS Lambda
- Vercel Serverless
- Google Cloud Functions
- and other environments where HTTP is preferred over TCP.

The sdk is currently compatible with python 3.10 and above.

<!-- toc -->
- [Upstash Rate Limit - python edition](#upstash-rate-limit---python-edition)
- [Quick Start](#quick-start)
  - [Install](#install)
    - [PyPi](#pypi)
  - [Setup database client](#setup-database-client)
  - [Ratelimit](#ratelimit)
    - [Importing Options](#importing-options)
    - [Usage](#usage)
  - [Block until ready](#block-until-ready)
  - [Rate-limiting outbound requests](#rate-limiting-outbound-requests)
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

### PyPi

```bash
pip install upstash-ratelimit
```

## Setup database client
To be able to use upstash-ratelimit, you need to create a database on [Upstash](https://console.upstash.com/) and get `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` environment variables.

## Ratelimit
### Importing Options
- #### Directly from ratelimit: This method will use your `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` variables that you set as env variables. 

    ```python
    # for sync client
    from upstash_ratelimit import RateLimit
    ratelimit = RateLimit()

    # for async client
    from upstash_ratelimit.asyncio import RateLimit
    ratelimit = Ratelimit()
    ```

- #### Explicit Redis Client: This method will use the Redis client that you manually initiate.
    ```python
    # for snyc client
    from upstash_ratelimit import RateLimit
    from upstash_redis import Redis

    rate_limit = RateLimit(Redis(url="UPSTASH_REDIS_REST_URL", token="UPSTASH_REDIS_REST_TOKEN"))


    # for asnyc client
    from upstash_ratelimit.asyncio import RateLimit
    from upstash_redis.asyncio import Redis

    rate_limit = RateLimit(Redis(url="UPSTASH_REDIS_REST_URL", token="UPSTASH_REDIS_REST_TOKEN"))
    ```
    For possible Redis client configurations, have a look at the [redis sdk repository](https://github.com/upstash/redis-python/blob/main/upstash_redis/client.py).

- You can also pass a `prefix` to the `RateLimit` constructor to distinguish between the keys used for rate limiting and others.
It defaults to `"ratelimit"`
    ```python
    ratelimit = Ratelimit(prefix="app1_ratelimiter")
    ```
    
### Usage


**All of the examples below can be implemented in async context as well. Only adding the correct import with async client, and necessary `await` expressions are sufficient for async use.**


```python
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

def main():
    request_result = fixed_window.limit(identifier)

    if not request_result["is_allowed"]:
        return f"{identifier} is rate-limited!"
    else:
        return "Request passed!"
```

The `limit` method also returns the following metadata :

```python
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


## Block until ready
You also have the option to try and wait for a request to pass in the given timeout.
If the first request is blocked and the timeout exceeds the time needed for the next interval to come,
we wait and retry once that happens.

```python
fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

identifier: str = "constant"

def main() -> str:
    request_result = fixed_window.block_until_ready(identifier, timeout=2000)

    if not request_result["is_allowed"]:
        return f"The {identifier}'s request cannot be processed, even after 2 seconds."
    else:
        return "Request passed!"
```


## Rate-limiting outbound requests
It's also possible to limit the number of requests you're making to an external API.

```python
fixed_window = rate_limit.fixed_window(
    max_number_of_requests=1,
    window=3,
    unit="s"
)

identifier: str = "constant"  # Or, use an identifier to limit your requests to a certain endpoint.


def main() -> str:
    request_result = fixed_window.limit(identifier)

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
token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=2,
    refill_rate=1,
    interval=3,
    unit="s"
)
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