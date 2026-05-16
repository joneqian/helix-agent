"""Helix sandbox runner — PID 1 inside the ``exec_python`` sandbox container.

Protocol (STREAM-F-DESIGN § 4.2): line-delimited JSON over stdin / stdout.
The Sandbox Supervisor (Stream F.1) attaches to the container's stdio,
writes one request object per line, and reads one response per line:

    → {"code": "<python source>", "timeout_s": 30}
    ← {"stdout": "...", "stderr": "...", "exit_code": 0, "timed_out": false}

The submitted code runs in a *child* ``python -c`` process rather than in
this interpreter. A child is killable on timeout and isolates a crashing
or ``sys.exit``-ing snippet from the runner loop; gVisor (Stream F.3) is
the actual security boundary, so this split is purely for timeout control
and loop survival, not isolation.

This module is image code — it ships into the sandbox via the Dockerfile
and has no dependency on the rest of the codebase, so it stays a single
self-contained stdlib-only file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TextIO

#: Applied when a request omits ``timeout_s``.
DEFAULT_TIMEOUT_S = 30
#: Hard ceiling — a request asking for more is clamped down. Matches the
#: sandbox-instance lifetime ceiling in subsystem 14.
MAX_TIMEOUT_S = 300

#: A response is always this 4-key shape, so the supervisor parses one
#: schema whether the run succeeded, failed, timed out, or the request
#: itself was malformed.
Response = dict[str, str | int | bool]


def run_once(code: str, timeout_s: int) -> Response:
    """Run ``code`` in a child Python process; capture stdout / stderr / exit.

    ``timeout_s`` is clamped to ``[1, MAX_TIMEOUT_S]``. On timeout the
    child is killed and ``timed_out`` is ``True`` with ``exit_code`` -1.
    """
    timeout_s = max(1, min(timeout_s, MAX_TIMEOUT_S))
    try:
        proc = subprocess.run(  # noqa: S603 - arbitrary code execution is the tool
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": _as_text(exc.stdout),
            "stderr": _as_text(exc.stderr),
            "exit_code": -1,
            "timed_out": True,
        }
    return {
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "timed_out": False,
    }


def handle_request(request: dict[str, object]) -> Response:
    """Validate one decoded request object and dispatch it to :func:`run_once`."""
    code = request.get("code")
    if not isinstance(code, str):
        return _error("request missing required string field 'code'")
    raw_timeout = request.get("timeout_s", DEFAULT_TIMEOUT_S)
    # JSON numbers decode to int / float; a bool is an int subclass we
    # explicitly reject. Anything else falls back to the default.
    timeout_s = raw_timeout if type(raw_timeout) is int else DEFAULT_TIMEOUT_S
    return run_once(code, timeout_s)


def handle_line(line: str) -> Response:
    """Decode one stdin line into a request and run it.

    A blank line yields ``None``-equivalent skipping at the caller; here
    any non-JSON or non-object payload becomes a structured error response
    so the supervisor never has to special-case a parse failure.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(f"invalid JSON request: {exc}")
    if not isinstance(request, dict):
        return _error("request must be a JSON object")
    return handle_request(request)


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    """Read requests line-by-line until EOF, writing one response per line."""
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        stdout.write(json.dumps(handle_line(line)) + "\n")
        stdout.flush()


def _error(message: str) -> Response:
    """A response for a request the runner could not even attempt to run."""
    return {
        "stdout": "",
        "stderr": f"[runner error] {message}",
        "exit_code": -1,
        "timed_out": False,
    }


def _as_text(value: str | bytes | None) -> str:
    """Normalise captured output to ``str`` — ``TimeoutExpired`` may carry bytes."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


if __name__ == "__main__":
    main()
