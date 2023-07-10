from http.server import BaseHTTPRequestHandler

from upstash_redis import Redis

from upstash_ratelimit import FixedWindow, Ratelimit

ratelimit = Ratelimit(
    redis=Redis.from_env(allow_telemetry=False),
    limiter=FixedWindow(max_requests=5, window=5),
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = ratelimit.limit("global")
        self.send_header("Content-type", "text/plain")
        self.send_header("X-Ratelimit-Limit", response.limit)
        self.send_header("X-Ratelimit-Remaining", response.remaining)
        self.send_header("X-Ratelimit-Reset", response.reset)

        self.end_headers()
        if not response.allowed:
            self.send_response(429)
            self.wfile.write("Come back later!".encode("utf-8"))
        else:
            self.send_response(200)
            self.wfile.write("Hello!".encode("utf-8"))

