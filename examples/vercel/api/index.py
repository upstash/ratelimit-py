from flask import Flask
from upstash_ratelimit.limiter import RateLimit
from upstash_redis.asyncio import Redis
import asyncio

rate_limit = RateLimit()
fixed_window = rate_limit.fixed_window(max_number_of_requests=2, window=4, unit="s")

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route("/request")
def request():
    asyncio.run(fixed_window.limit("timeout_1"))
    res = asyncio.run(fixed_window.block_until_ready('timeout_1', 10))
    return f"<p>{res}</p>"