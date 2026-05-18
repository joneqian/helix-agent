"""Mock upstream — Stream I.1b, the #60 full-stack egress e2e.

A throwaway HTTP echo server: every request gets a 200 response whose
JSON body echoes the method, path, headers and body it received. The
#60 e2e uses it as the credential-proxy's forward target — the echoed
``authorization`` header is the proof that the proxy injected the
secret on the way through.

Pure stdlib so it runs on a bare ``python:3.12-alpine`` container with
no build step. Not on any code path outside the e2e.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_PORT = 9100


class _EchoHandler(BaseHTTPRequestHandler):
    """Echoes each request back as a JSON document."""

    def _echo(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body.decode("utf-8", "replace"),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._echo()

    def do_POST(self) -> None:
        self._echo()

    def log_message(self, *_args: object) -> None:
        """Silence per-request logging — keeps e2e output readable."""


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", _PORT), _EchoHandler).serve_forever()  # noqa: S104
