#!/usr/bin/env python3
# ABOUTME: Proof-of-concept test for the InteractiveSession multi-turn harness.
# ABOUTME: Verifies PTY-driven multi-turn sessions, key sequences, and log discovery.

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession, _strip_ansi, _KEY_SEQUENCES


def test_offline():
    """Verify ANSI stripping and key sequence support without a live session."""
    print("--- Offline Tests ---")

    # ANSI stripping
    assert _strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert _strip_ansi("\x1b]0;title\x07text") == "text"
    assert "\r" not in _strip_ansi("a\r\nb")
    print("  ANSI stripping: PASS")

    # Key sequences
    assert _KEY_SEQUENCES["shift-up"] == b"\x1b[1;2A"
    assert _KEY_SEQUENCES["shift-down"] == b"\x1b[1;2B"
    print("  Key sequences defined: PASS")

    # send_key rejects unknown keys
    session = InteractiveSession()
    try:
        session.send_key("shift-up")
        assert False, "Should raise RuntimeError when not started"
    except RuntimeError:
        pass
    try:
        session._started = True
        session._fd = 999  # fake fd
        session.send_key("bogus-key")
        assert False, "Should raise ValueError for unknown key"
    except ValueError:
        pass
    finally:
        session._started = False
        session._fd = None
    print("  send_key validation: PASS")

    # Subagent log discovery with empty dir
    with tempfile.TemporaryDirectory() as td:
        logs = InteractiveSession().get_subagent_logs(td)
        assert logs == {}, f"Expected empty dict, got {logs}"
    print("  Subagent log discovery (empty): PASS")

    print("  All offline tests: PASS")
    print()


def run_multi_turn():
    """Live multi-turn test with PTY-driven claude session."""
    print("--- Live Multi-Turn Test ---")

    session = InteractiveSession(
        model="haiku",
        max_budget_usd=0.20,
    )

    try:
        print("Starting session...")
        session.start(ready_timeout=15)
        print("  Session ready")

        # Turn 1
        print("Sending turn 1: 'Say exactly ALPHA_MARKER'")
        session.send("Say exactly ALPHA_MARKER")
        found_1 = session.wait_for("ALPHA_MARKER", timeout=45)
        print(f"  ALPHA_MARKER found: {found_1}")

        # Demonstrate send_key: Shift+Down (team member switch)
        # In a non-team session this is a no-op, but proves the PTY accepts the escape code
        print("Sending Shift+Down key sequence...")
        session.send_key("shift-down")
        # Brief pause to let TUI process the key
        import time
        time.sleep(0.5)
        session._drain(timeout=0.5)
        print("  Shift+Down sent (no-op in non-team session)")

        # Turn 2
        print("Sending turn 2: 'Now say exactly BETA_MARKER'")
        session.send("Now say exactly BETA_MARKER")
        found_2 = session.wait_for("BETA_MARKER", timeout=45)
        print(f"  BETA_MARKER found: {found_2}")

        # Try subagent log discovery (won't find logs in non-team session)
        project_dir = Path(__file__).resolve().parent.parent
        logs = session.get_subagent_logs(project_dir)
        print(f"  Subagent logs found: {len(logs)}")
        for agent_id, path in logs.items():
            print(f"    {agent_id}: {path}")

        print()
        print("=== Results ===")
        print(f"  Turn 1 (ALPHA_MARKER): {'PASS' if found_1 else 'FAIL'}")
        print(f"  Shift+Down key send: PASS")
        print(f"  Turn 2 (BETA_MARKER): {'PASS' if found_2 else 'FAIL'}")
        print(f"  Multi-turn: {'PASS' if found_1 and found_2 else 'FAIL'}")

    finally:
        print()
        print("Stopping session...")
        session.stop()
        print("  Session stopped")

    return found_1 and found_2


def main():
    print("=== Interactive Session POC Test ===")
    print()

    # Always run offline tests (no claude needed)
    test_offline()

    # Run live tests if --live flag is passed (requires claude CLI)
    if "--live" in sys.argv:
        success = run_multi_turn()
        if not success:
            sys.exit(1)
    else:
        print("--- Live tests skipped (pass --live to run) ---")

    print()
    print("=== All tests passed ===")


if __name__ == "__main__":
    main()
