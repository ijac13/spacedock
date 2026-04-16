# ABOUTME: Offline unit tests for FOStreamWatcher + run_first_officer_streaming (#173).
# ABOUTME: Covers ACs 1-8, 11, 12 — no claude subprocess, only sh and synthetic logs.

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    FOStreamWatcher,
    StepFailure,
    StepTimeout,
    assistant_model_equals,
    entry_contains_text,
    run_first_officer_streaming,
    tool_use_matches,
)


class _FakeProc:
    """Minimal stand-in for subprocess.Popen implementing the subset the watcher reads."""

    def __init__(self, returncode: int | None = None):
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def set_exited(self, returncode: int) -> None:
        self.returncode = returncode


def _write_line(path: Path, obj: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(obj) + "\n")


def _assistant_tool_use(tool_name: str, **inp) -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-4-6",
            "content": [{"type": "tool_use", "name": tool_name, "input": inp}],
        },
    }


def _assistant_text(text: str, model: str = "claude-sonnet-4-6") -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "content": [{"type": "text", "text": text}],
        },
    }


def _user_tool_result(text: str) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "content": [{"type": "text", "text": text}]}
            ]
        },
    }


def test_expect_returns_matched_entry(tmp_path):
    """AC-1: expect() returns the matched entry dict on success."""
    log = tmp_path / "fo.jsonl"
    log.touch()
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    _write_line(log, _assistant_tool_use("Bash", command="echo one"))
    target = _assistant_tool_use("Bash", command="spawn-standing now")
    _write_line(log, target)

    result = watcher.expect(
        lambda e: tool_use_matches(e, "Bash", command="spawn-standing"),
        timeout_s=2.0,
        label="spawn-standing",
    )
    assert result["message"]["content"][0]["input"]["command"] == "spawn-standing now"


def test_expect_raises_step_timeout_with_label(tmp_path):
    """AC-2: expect() raises StepTimeout carrying the label when predicate never matches."""
    log = tmp_path / "fo.jsonl"
    log.touch()
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    _write_line(log, _assistant_tool_use("Bash", command="noise"))

    with pytest.raises(StepTimeout) as excinfo:
        watcher.expect(
            lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
            timeout_s=0.6,
            label="echo-agent dispatched",
        )
    assert excinfo.value.label == "echo-agent dispatched"
    assert "echo-agent dispatched" in str(excinfo.value)


def test_expect_raises_step_failure_when_proc_exits(tmp_path):
    """AC-3: expect() raises StepFailure when the subprocess exits before a match."""
    log = tmp_path / "fo.jsonl"
    log.touch()
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    _write_line(log, _assistant_tool_use("Bash", command="noise"))

    def exit_soon():
        time.sleep(0.3)
        proc.set_exited(1)

    threading.Thread(target=exit_soon, daemon=True).start()

    with pytest.raises(StepFailure) as excinfo:
        watcher.expect(
            lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
            timeout_s=5.0,
            label="echo-agent dispatched",
        )
    assert excinfo.value.exit_code == 1
    assert excinfo.value.label == "echo-agent dispatched"
    assert "code=1" in str(excinfo.value)


def test_expect_matches_final_flush_before_exit(tmp_path):
    """AC-3 ordering: expect() must drain the log before checking proc.poll()."""
    log = tmp_path / "fo.jsonl"
    log.touch()
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    _write_line(log, _assistant_tool_use("Agent", name="echo-agent"))
    proc.set_exited(0)

    matched = watcher.expect(
        lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
        timeout_s=1.0,
        label="echo-agent dispatched",
    )
    assert matched["message"]["content"][0]["name"] == "Agent"


def test_partial_line_then_newline(tmp_path):
    """AC-4: watcher holds a partial trailing line until its newline arrives."""
    log = tmp_path / "fo.jsonl"
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    entry = _assistant_tool_use("Bash", command="spawn-standing")
    serialized = json.dumps(entry)
    mid = len(serialized) // 2

    with log.open("w") as f:
        f.write(serialized[:mid])
        f.flush()

    with pytest.raises(StepTimeout):
        watcher.expect(
            lambda e: tool_use_matches(e, "Bash", command="spawn-standing"),
            timeout_s=0.4,
            label="spawn half-written",
        )

    with log.open("a") as f:
        f.write(serialized[mid:] + "\n")
        f.flush()

    matched = watcher.expect(
        lambda e: tool_use_matches(e, "Bash", command="spawn-standing"),
        timeout_s=1.0,
        label="spawn fully-written",
    )
    assert matched["message"]["content"][0]["input"]["command"] == "spawn-standing"


def _fake_runner(tmp_path: Path):
    """Build a minimal runner-shaped object the context manager expects."""

    class Runner:
        pass

    r = Runner()
    r.repo_root = tmp_path
    r.log_dir = tmp_path
    r.test_project_dir = tmp_path
    return r


_REAL_POPEN = subprocess.Popen


def test_context_manager_extracts_stats_on_normal_exit(tmp_path, monkeypatch):
    """AC-5: context manager drains the log and runs extract_stats on exit."""
    calls: dict = {}

    hello = json.dumps(_assistant_text("hello"))

    def fake_popen(cmd, **kwargs):
        # Swap in a trivial shell command that prints one stream-json entry;
        # the log_file that test_lib opened remains the stdout target.
        kwargs.pop("env", None)
        return _REAL_POPEN(
            ["sh", "-c", f"printf '%s\\n' {shlex.quote(hello)}"],
            **kwargs,
        )

    def fake_extract_stats(log_path, phase_name, output_dir):
        calls["args"] = (Path(log_path), phase_name, Path(output_dir))
        return {}

    import test_lib

    monkeypatch.setattr(test_lib.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(test_lib, "extract_stats", fake_extract_stats)

    runner = _fake_runner(tmp_path)
    with run_first_officer_streaming(runner, prompt="noop", hard_cap_s=5) as w:
        matched = w.expect(
            lambda e: entry_contains_text(e, "hello"),
            timeout_s=2.0,
            label="hello text",
        )
        assert matched["type"] == "assistant"
        w.expect_exit(timeout_s=2.0)

    assert calls["args"][1] == "fo"
    assert calls["args"][0].name == "fo-log.jsonl"


def test_context_manager_terminates_lingering_proc(tmp_path, monkeypatch):
    """AC-6: context manager terminates the subprocess when caller skips expect_exit."""
    holder: dict = {}

    def fake_popen(cmd, **kwargs):
        kwargs.pop("env", None)
        proc = _REAL_POPEN(["sh", "-c", "sleep 30"], **kwargs)
        holder["proc"] = proc
        return proc

    import test_lib

    monkeypatch.setattr(test_lib.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(test_lib, "extract_stats", lambda *a, **k: {})

    runner = _fake_runner(tmp_path)
    start = time.monotonic()
    with run_first_officer_streaming(runner, prompt="noop", hard_cap_s=1):
        time.sleep(0.2)

    elapsed = time.monotonic() - start
    proc = holder["proc"]
    assert proc.poll() is not None, "subprocess must be dead on context exit"
    assert elapsed < 4.0, f"context manager should finish within ~1-2s, took {elapsed:.2f}s"


def test_context_manager_enforces_hard_cap(tmp_path, monkeypatch):
    """AC-7: context manager enforces the hard_cap_s budget on a runaway proc."""
    holder: dict = {}

    def fake_popen(cmd, **kwargs):
        kwargs.pop("env", None)
        proc = _REAL_POPEN(["sh", "-c", "sleep 10"], **kwargs)
        holder["proc"] = proc
        return proc

    import test_lib

    monkeypatch.setattr(test_lib.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(test_lib, "extract_stats", lambda *a, **k: {})

    runner = _fake_runner(tmp_path)
    start = time.monotonic()
    with run_first_officer_streaming(runner, prompt="noop", hard_cap_s=1):
        # Simulate a test body that keeps the with-block open past hard_cap_s.
        # The context manager must kill the subprocess once the budget trips.
        time.sleep(3)

    elapsed = time.monotonic() - start
    proc = holder["proc"]
    assert proc.poll() is not None
    assert elapsed < 6.0, f"hard cap should fire inside ~3s, took {elapsed:.2f}s"


def test_context_manager_terminates_fast_on_exception_exit(tmp_path, monkeypatch):
    """AC-13: context manager terminates within ~10s when an exception propagates.

    Regression guard for cycle-1 feedback: on exception-driven exit the
    finally must use a short grace period (5s) instead of waiting out
    ``hard_cap_s - elapsed`` for a hung subprocess to exit on its own.
    """
    holder: dict = {}

    def fake_popen(cmd, **kwargs):
        kwargs.pop("env", None)
        proc = _REAL_POPEN(["sh", "-c", "sleep 60"], **kwargs)
        holder["proc"] = proc
        return proc

    import test_lib

    monkeypatch.setattr(test_lib.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(test_lib, "extract_stats", lambda *a, **k: {})

    runner = _fake_runner(tmp_path)
    start = time.monotonic()

    class _Boom(RuntimeError):
        pass

    with pytest.raises(_Boom):
        with run_first_officer_streaming(runner, prompt="noop", hard_cap_s=600):
            raise _Boom("assertion failed deep in the test body")

    elapsed = time.monotonic() - start
    proc = holder["proc"]
    assert proc.poll() is not None, "subprocess must be dead after exception exit"
    assert elapsed < 15.0, (
        f"exception exit must fast-terminate in <15s regardless of hard_cap_s; "
        f"took {elapsed:.2f}s"
    )


def test_tool_use_matches_covers_all_tool_shapes():
    """AC-8: tool_use_matches identifies Bash/Agent/SendMessage entries with substring input."""
    bash_entry = _assistant_tool_use("Bash", command="claude-team spawn-standing --all")
    agent_entry = _assistant_tool_use("Agent", name="echo-agent", subagent_type="echo")
    send_entry = _assistant_tool_use("SendMessage", to="echo-agent", message="ping")

    assert tool_use_matches(bash_entry, "Bash", command="spawn-standing")
    assert not tool_use_matches(bash_entry, "Bash", command="not-there")
    assert not tool_use_matches(bash_entry, "Agent")

    assert tool_use_matches(agent_entry, "Agent", name="echo-agent")
    assert tool_use_matches(agent_entry, "Agent", name="echo", subagent_type="echo")
    assert not tool_use_matches(agent_entry, "Agent", name="other")

    assert tool_use_matches(send_entry, "SendMessage", to="echo-agent")
    assert not tool_use_matches(send_entry, "SendMessage", to="elsewhere")

    # Non-tool_use entries return False cleanly.
    assert not tool_use_matches(_assistant_text("just text"), "Bash")
    assert not tool_use_matches(_user_tool_result("tool output"), "Bash")


def test_entry_contains_text_and_assistant_model_equals():
    """Sanity: predicate helpers for text + model. Part of the AC-8 coverage surface."""
    assert entry_contains_text(_assistant_text("hello world"), r"hello")
    assert entry_contains_text(_user_tool_result("ECHO: ping"), r"ECHO:\s*ping")
    assert not entry_contains_text(_assistant_text("unrelated"), r"ECHO:\s*ping")

    assert assistant_model_equals(_assistant_text("x", model="claude-haiku-4-5"), "claude-haiku-")
    assert not assistant_model_equals(_assistant_text("x", model="claude-opus-4-7"), "claude-haiku-")
    assert not assistant_model_equals(_user_tool_result("x"), "claude-haiku-")


def test_non_migrated_public_surface_intact():
    """AC-11: non-migrated tests still import the old public surface unchanged."""
    from test_lib import (  # noqa: F401
        FOStreamWatcher,
        LogParser,
        run_first_officer,
        run_first_officer_streaming,
    )


def test_failure_messages_include_log_tail_and_label(tmp_path):
    """AC-12: watcher failure messages include a log tail and the step label."""
    log = tmp_path / "fo.jsonl"
    log.touch()
    proc = _FakeProc()
    watcher = FOStreamWatcher(log, proc)

    for i in range(5):
        _write_line(log, _assistant_text(f"noise line {i}"))

    with pytest.raises(StepTimeout) as excinfo:
        watcher.expect(
            lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
            timeout_s=0.4,
            label="echo-agent dispatched",
        )
    message = str(excinfo.value)
    assert "echo-agent dispatched" in message
    assert "Log tail:" in message
    assert "noise line 4" in message

    # StepFailure case also carries the tail + label.
    proc.set_exited(2)
    with pytest.raises(StepFailure) as exc2:
        watcher.expect(
            lambda e: tool_use_matches(e, "Agent", name="echo-agent"),
            timeout_s=1.0,
            label="after-exit step",
        )
    message2 = str(exc2.value)
    assert "after-exit step" in message2
    assert "Log tail:" in message2
    assert "noise line 4" in message2
