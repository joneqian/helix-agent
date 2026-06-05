"""Office-image smoke test — host-side driver (OFFICE-1b).

Boots the built office image and drives the runner's line-delimited JSON
protocol (one ``{"code": ...}`` request → one response), sending
``smoke_payload.py`` as the code. Passes iff the runner reports
``exit_code == 0`` and the payload printed ``OK``.

Run under runc in CI (catches missing libs/fonts/locale); the gVisor /
read-only-rootfs behaviour is verified separately on the target host.

Usage:
    python smoke_test.py <image-tag>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PAYLOAD = Path(__file__).with_name("smoke_payload.py")


def main(image: str) -> int:
    code = _PAYLOAD.read_text(encoding="utf-8")
    request = json.dumps({"code": code, "timeout_s": 180}) + "\n"
    proc = subprocess.run(  # noqa: S603
        ["docker", "run", "--rm", "-i", image],  # noqa: S607
        input=request,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        print(f"no runner output; stderr:\n{proc.stderr}", file=sys.stderr)
        return 1
    # First line is the runner's {"ready": true}; the last is the response.
    try:
        response = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        print(f"unparseable response {lines[-1]!r}: {exc}", file=sys.stderr)
        return 1
    if response.get("exit_code") != 0 or "OK" not in response.get("stdout", ""):
        print(
            "smoke FAILED\n"
            f"  exit_code={response.get('exit_code')}\n"
            f"  stdout={response.get('stdout')!r}\n"
            f"  stderr={response.get('stderr')!r}",
            file=sys.stderr,
        )
        return 1
    print(f"smoke OK\n{response['stdout']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python smoke_test.py <image-tag>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
