# ABOUTME: Proof-of-concept tests for the InteractiveSession multi-turn harness.
# ABOUTME: Splits pure-Python offline asserts from the live PTY smoke that actually spawns claude.

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession, _strip_ansi, _KEY_SEQUENCES  # noqa: E402


def test_interactive_poc_offline():
    """Verify ANSI stripping and key sequence support without a live session."""
    assert _strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert _strip_ansi("\x1b]0;title\x07text") == "text"
    assert "\r" not in _strip_ansi("a\r\nb")

    assert _KEY_SEQUENCES["shift-up"] == b"\x1b[1;2A"
    assert _KEY_SEQUENCES["shift-down"] == b"\x1b[1;2B"

    session = InteractiveSession()
    with pytest.raises(RuntimeError):
        session.send_key("shift-up")

    session._started = True
    session._fd = 999
    try:
        with pytest.raises(ValueError):
            session.send_key("bogus-key")
    finally:
        session._started = False
        session._fd = None

    with tempfile.TemporaryDirectory() as td:
        assert InteractiveSession().get_subagent_logs(td) == {}


@pytest.mark.skip(reason="requires real TTY; CI runners are headless — see #155")
@pytest.mark.live_claude
@pytest.mark.serial
def test_interactive_poc_live(model):
    """Live multi-turn PTY smoke with two marker prompts and a Shift+Down key send."""
    session = InteractiveSession(model=model, max_budget_usd=0.20)

    try:
        print("Starting session...")
        session.start(ready_timeout=15)
        print("  Session ready")

        print("Sending turn 1: 'Say exactly ALPHA_MARKER'")
        session.send("Say exactly ALPHA_MARKER")
        found_1 = session.wait_for("ALPHA_MARKER", timeout=45)
        print(f"  ALPHA_MARKER found: {found_1}")

        print("Sending Shift+Down key sequence...")
        session.send_key("shift-down")
        time.sleep(0.5)
        session._drain(timeout=0.5)
        print("  Shift+Down sent (no-op in non-team session)")

        print("Sending turn 2: 'Now say exactly BETA_MARKER'")
        session.send("Now say exactly BETA_MARKER")
        found_2 = session.wait_for("BETA_MARKER", timeout=45)
        print(f"  BETA_MARKER found: {found_2}")

        project_dir = Path(__file__).resolve().parent.parent
        logs = session.get_subagent_logs(project_dir)
        print(f"  Subagent logs found: {len(logs)}")
        for agent_id, path in logs.items():
            print(f"    {agent_id}: {path}")

        assert found_1, "turn 1 did not echo ALPHA_MARKER"
        assert found_2, "turn 2 did not echo BETA_MARKER"

    finally:
        print("Stopping session...")
        session.stop()

