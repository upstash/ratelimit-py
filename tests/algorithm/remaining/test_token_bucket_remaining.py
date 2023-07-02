from tests.client import rate_limit
from pytest import mark
from time import sleep

token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=1, refill_rate=1, interval=3000, unit="ms"
)

def test_before_the_first_request() -> None:
    assert token_bucket.remaining("token_bucket_remaining_1") == 1

def test_after_the_first_request() -> None:
    token_bucket.limit("token_bucket_remaining_2")

    assert token_bucket.remaining("token_bucket_remaining_2") == 0


# Use a client that has different maximum number of tokens and refill rate.
burst_token_bucket = rate_limit.token_bucket(
    max_number_of_tokens=2, refill_rate=1, interval=2000, unit="ms"
)

def test_after_burst() -> None:
    # Exhaust the request limit.
    burst_token_bucket.limit("burst_token_bucket_remaining_1")
    burst_token_bucket.limit("burst_token_bucket_remaining_1")

    # Wait for the refill.
    sleep(2)

    assert burst_token_bucket.remaining("burst_token_bucket_remaining_1") == 1

def test_after_burst_with_positive_number_of_tokens_before_the_refill() -> None:
    burst_token_bucket.limit("burst_token_bucket_remaining_2")

    """
    At this point the bucket should've had 1 token. 
    Since the refill adds another one, the identifier should have 2 requests left.
    """
    sleep(2)

    assert burst_token_bucket.remaining("burst_token_bucket_remaining_2") == 2
