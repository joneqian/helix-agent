"""Unit tests for the sandbox runner — Stream F.2 (test matrix #44).

``infra/sandbox-image/runner.py`` is image code, not an installed package,
so it is loaded by path. The tests exercise the stdin / stdout JSON
protocol (STREAM-F-DESIGN § 4.2): happy path, non-zero exit, timeout, and
the malformed-request paths the supervisor must never have to special-case.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType


def _load_runner() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "infra" / "sandbox-image" / "runner.py"
    spec = importlib.util.spec_from_file_location("helix_sandbox_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


# ---------- run_once ----------


def test_run_once_captures_stdout() -> None:
    result = runner.run_once("print(2 + 2)", 30)
    assert result["stdout"].strip() == "4"
    assert result["exit_code"] == 0
    assert result["timed_out"] is False


def test_run_once_nonzero_exit_on_exception() -> None:
    result = runner.run_once("raise ValueError('boom')", 30)
    assert result["exit_code"] != 0
    assert "ValueError" in result["stderr"]
    assert "boom" in result["stderr"]
    assert result["timed_out"] is False


def test_run_once_propagates_sys_exit_code() -> None:
    result = runner.run_once("import sys\nsys.exit(7)", 30)
    assert result["exit_code"] == 7
    assert result["timed_out"] is False


def test_run_once_timeout_sets_timed_out() -> None:
    result = runner.run_once("import time\ntime.sleep(30)", 1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_run_once_clamps_timeout_below_one() -> None:
    # timeout_s=0 would make subprocess.run raise immediately; the runner
    # clamps it up to 1 so a fast snippet still completes.
    result = runner.run_once("print('ok')", 0)
    assert result["stdout"].strip() == "ok"
    assert result["timed_out"] is False


# ---------- handle_request ----------


def test_handle_request_missing_code_is_error() -> None:
    result = runner.handle_request({"timeout_s": 5})
    assert result["exit_code"] == -1
    assert "code" in result["stderr"]
    assert result["timed_out"] is False


def test_handle_request_non_int_timeout_falls_back_to_default() -> None:
    # A bool is an int subclass but must not be accepted as a timeout;
    # falling back to the default still runs the code successfully.
    result = runner.handle_request({"code": "print('hi')", "timeout_s": True})
    assert result["stdout"].strip() == "hi"
    assert result["exit_code"] == 0


# ---------- handle_line ----------


def test_handle_line_runs_valid_request() -> None:
    result = runner.handle_line('{"code": "print(1 + 1)", "timeout_s": 10}')
    assert result["stdout"].strip() == "2"
    assert result["exit_code"] == 0


def test_handle_line_invalid_json_is_error() -> None:
    result = runner.handle_line("not json at all")
    assert result["exit_code"] == -1
    assert "invalid JSON" in result["stderr"]


def test_handle_line_non_object_is_error() -> None:
    result = runner.handle_line("42")
    assert result["exit_code"] == -1
    assert "JSON object" in result["stderr"]


# ---------- main loop ----------


def test_main_processes_multiple_lines_and_skips_blanks() -> None:
    stdin = io.StringIO(
        '{"code": "print(10)"}\n'
        "\n"  # blank line — skipped, no response emitted
        '{"code": "print(20)"}\n'
    )
    stdout = io.StringIO()
    runner.main(stdin=stdin, stdout=stdout)

    responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert len(responses) == 2
    assert responses[0]["stdout"].strip() == "10"
    assert responses[1]["stdout"].strip() == "20"


def test_main_emits_error_response_for_bad_line() -> None:
    stdout = io.StringIO()
    runner.main(stdin=io.StringIO("{bad}\n"), stdout=stdout)

    response = json.loads(stdout.getvalue())
    assert response["exit_code"] == -1
    assert "invalid JSON" in response["stderr"]
