#!/usr/bin/env python3
# ABOUTME: Proof-of-concept test for the InteractiveSession multi-turn harness.
# ABOUTME: Verifies that PTY-driven multi-turn sessions work with claude.

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession


def main():
    print("=== Interactive Session POC Test ===")
    print()

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

        # Turn 2
        print("Sending turn 2: 'Now say exactly BETA_MARKER'")
        session.send("Now say exactly BETA_MARKER")
        found_2 = session.wait_for("BETA_MARKER", timeout=45)
        print(f"  BETA_MARKER found: {found_2}")

        print()
        print("=== Results ===")
        print(f"  Turn 1 (ALPHA_MARKER): {'PASS' if found_1 else 'FAIL'}")
        print(f"  Turn 2 (BETA_MARKER): {'PASS' if found_2 else 'FAIL'}")
        print(f"  Multi-turn: {'PASS' if found_1 and found_2 else 'FAIL'}")

    finally:
        print()
        print("Stopping session...")
        session.stop()
        print("  Session stopped")

    if not (found_1 and found_2):
        sys.exit(1)


if __name__ == "__main__":
    main()
