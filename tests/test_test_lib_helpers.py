#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit tests for shared live-harness helpers in scripts/test_lib.py.
# ABOUTME: Verifies Claude runtime preflight reporting and guardrail shell-write detection heuristics.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import bash_command_targets_write, emit_skip_result, probe_claude_runtime


TARGETS = ("skills/", "agents/", "references/", "plugin.json")


def test_bash_command_targets_write_ignores_read_only_probes():
    for command in (
        "ls -la skills/",
        "cat agents/example.md",
        "head -n 5 references/core.md",
        "tail -n 5 references/core.md",
        "grep -n guardrail skills/example.md",
        "find references -name '*.md'",
        "file plugin.json",
        "stat plugin.json",
        "wc -l skills/example.md",
    ):
        assert not bash_command_targets_write(command, TARGETS)


def test_bash_command_targets_write_flags_shell_writes():
    assert bash_command_targets_write("echo '{}' > plugin.json", TARGETS)
    assert bash_command_targets_write("printf '# x' | tee skills/example.md", TARGETS)
    assert bash_command_targets_write("sed -i '' 's/old/new/' agents/example.md", TARGETS)


def test_bash_command_targets_write_requires_a_target_match():
    assert not bash_command_targets_write("echo hi > /tmp/elsewhere.txt", TARGETS)


def test_probe_claude_runtime_reports_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=17)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, reason = probe_claude_runtime("haiku", timeout_s=17)

    assert not ok
    assert "within 17s" in reason


def test_probe_claude_runtime_reports_non_zero_exit(monkeypatch):
    class Result:
        returncode = 9
        stdout = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())

    ok, reason = probe_claude_runtime("haiku", timeout_s=30)

    assert not ok
    assert "exited 9" in reason


def test_probe_claude_runtime_reports_missing_result_record(monkeypatch):
    class Result:
        returncode = 0
        stdout = '{"type":"message"}'

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())

    ok, reason = probe_claude_runtime("haiku", timeout_s=30)

    assert not ok
    assert "returned no stream-json result record" in reason


def test_probe_claude_runtime_succeeds_with_result_record_and_clean_env(monkeypatch):
    seen_env = {}

    class Result:
        returncode = 0
        stdout = '{"type":"result"}'

    def fake_run(*args, **kwargs):
        seen_env.update(kwargs["env"])
        return Result()

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, reason = probe_claude_runtime("haiku", timeout_s=30)

    assert ok
    assert reason == ""
    assert "CLAUDECODE" not in seen_env


def test_emit_skip_result_prints_standardized_skip_output(capsys):
    with pytest.raises(SystemExit) as excinfo:
        emit_skip_result("runtime unavailable")

    captured = capsys.readouterr().out
    assert "SKIP: runtime unavailable" in captured
    assert "RESULT: SKIP" in captured
    assert excinfo.value.code == 0
