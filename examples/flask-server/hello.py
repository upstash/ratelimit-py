from flask import Flask  # type: ignore
from upstash_redis import Redis

from upstash_ratelimit import FixedWindow, Ratelimit

ratelimit = Ratelimit(
    redis=Redis.from_env(allow_telemetry=False),
    limiter=FixedWindow(max_requests=2, window=40),
)

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/request")
def request():
    response = ratelimit.block_until_ready("timeout_1", 10)
    return f"<p>{response}</p>"
