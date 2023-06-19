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
