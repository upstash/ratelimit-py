# This is where the defaults and non-secret configuration values are stored.
redis_sdk_version = "0.14.2"
ratelimit_sdk_version = "0.4.0"

SDK: str = f"py-upstash-redis@v{redis_sdk_version}, py-upstash-ratelimit@v{ratelimit_sdk_version}"

PREFIX: str = "ratelimit"
