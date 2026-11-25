"""Small HTTP counter backed by Redis, using only the Python standard library."""

import html
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
APP_TITLE = os.getenv("APP_TITLE", "Docker visit counter")
PORT = int(os.getenv("PORT", "8080"))


def redis_command(*parts):
    """Send one Redis RESP command and read its simple or integer reply."""
    encoded = [str(part).encode("utf-8") for part in parts]
    request = f"*{len(encoded)}\r\n".encode("ascii")
    request += b"".join(
        f"${len(part)}\r\n".encode("ascii") + part + b"\r\n"
        for part in encoded
    )
    with socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=2) as conn:
        conn.settimeout(2)
        conn.sendall(request)
        with conn.makefile("rb") as reply:
            line = reply.readline()
    if not line.endswith(b"\r\n"):
        raise OSError("Incomplete Redis response")
    if line[:1] == b"-":
        raise OSError(line[1:-2].decode("utf-8", errors="replace"))
    if line[:1] == b":":
        return int(line[1:-2])
    if line[:1] == b"+":
        return line[1:-2].decode("utf-8")
    raise OSError("Unexpected Redis response")


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="text/plain; charset=utf-8"):
        body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health/live":
            self.respond(200, "alive\n")
            return
        if self.path == "/health/ready":
            try:
                if redis_command("PING") != "PONG":
                    raise OSError("Redis is not ready")
            except OSError:
                self.respond(503, "not ready\n")
            else:
                self.respond(200, "ready\n")
            return
        if self.path != "/":
            self.respond(404, "not found\n")
            return
        try:
            visits = redis_command("INCR", "visits")
        except OSError:
            self.respond(503, "Redis is unavailable\n")
            return
        title = html.escape(APP_TITLE)
        self.respond(
            200,
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            f"<title>{title}</title>"
            "<body style='font:1.3rem system-ui;max-width:42rem;margin:5rem auto'>"
            f"<h1>{title}</h1><p>Visits: <strong>{visits}</strong></p>"
            "<p>Counter stored in Redis.</p></body></html>\n",
            "text/html; charset=utf-8",
        )


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
