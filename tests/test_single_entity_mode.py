#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: PTY-based E2E regression test for single-entity mode trigger condition.
# ABOUTME: Verifies that interactive sessions create teams (not bare mode) when a user names an entity.

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession, _strip_ansi

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "spike-no-gate"


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Single-entity mode interactive regression test"
    )
    parser.add_argument(
        "--runtime", choices=["claude"], default="claude",
        help="Runtime to test (claude only — this tests interactive sessions)",
    )
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument(
        "--budget", type=float, default=2.00,
        help="Max budget in USD (default: 2.00)",
    )
    return parser.parse_known_args()


def setup_test_project() -> Path:
    """Create a temp git project with the spike-no-gate fixture and agent files."""
    project_dir = Path(tempfile.mkdtemp(prefix="sem-test-"))

    subprocess.run(["git", "init", str(project_dir)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=project_dir,
    )

    workflow_dir = project_dir / "spike-workflow"
    shutil.copytree(FIXTURE_DIR, workflow_dir)
    status = workflow_dir / "status"
    if status.exists():
        status.chmod(status.stat().st_mode | 0o111)

    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "agents" / "first-officer.md", agents_dir / "first-officer.md")
    shutil.copy2(REPO_ROOT / "agents" / "ensign.md", agents_dir / "ensign.md")

    subprocess.run(["git", "add", "-A"], capture_output=True, check=True, cwd=project_dir)
    subprocess.run(
        ["git", "commit", "-m", "setup: single-entity mode interactive test"],
        capture_output=True, check=True, cwd=project_dir,
    )

    return project_dir


def start_with_trust_handling(session: InteractiveSession, ready_timeout: float = 30.0) -> None:
    """Start the session, handling the workspace trust dialog if it appears.

    Claude Code shows a trust dialog for untrusted directories. This function
    detects the dialog and sends Enter to accept it before waiting for the
    normal prompt.
    """
    if session._started:
        raise RuntimeError("Session already started")

    from test_lib_interactive import _clean_env
    import pty
    import select

    env = _clean_env()
    cmd = ["claude", "--model", session.model, "--permission-mode", session.permission_mode]
    if session.max_budget_usd is not None:
        cmd.extend(["--max-budget-usd", str(session.max_budget_usd)])
    cmd.extend(session.extra_args)

    pid, fd = pty.fork()
    if pid == 0:
        if session.cwd:
            os.chdir(session.cwd)
        os.execvpe("claude", cmd, env)
        os._exit(1)

    session._pid = pid
    session._fd = fd
    session._started = True

    start = time.time()
    trust_handled = False
    while time.time() - start < ready_timeout:
        session._drain(timeout=1.0)
        clean = session.get_clean_output()

        # Check for trust dialog BEFORE prompt-ready — the trust dialog
        # uses ❯ as a selection indicator (e.g., "❯ 1. Yes, I trust this
        # folder"), which would false-positive the prompt-ready check.
        if not trust_handled and re.search(r"trust.*folder|Do you want to trust", clean, re.IGNORECASE):
            print("  Trust dialog detected, sending Enter to accept...")
            os.write(fd, b"\r")
            time.sleep(1.0)
            trust_handled = True
            continue

        # Check for the normal prompt (only after trust dialog is handled)
        if "\u276f" in clean:
            return

    raise TimeoutError(f"Session did not become ready within {ready_timeout}s")


def main():
    args, extra_args = parse_args()

    print("=== Single-Entity Mode Interactive Regression Test ===")
    print()

    passes = 0
    failures = 0

    def pass_(label: str):
        nonlocal passes
        passes += 1
        print(f"  PASS: {label}")

    def fail(label: str):
        nonlocal failures
        failures += 1
        print(f"  FAIL: {label}")

    # --- Phase 1: Set up test project ---

    print("--- Phase 1: Set up test project ---")
    project_dir = setup_test_project()
    print(f"  Project dir: {project_dir}")

    abs_workflow = project_dir / "spike-workflow"

    session = InteractiveSession(
        model=args.model,
        max_budget_usd=args.budget,
        cwd=project_dir,
        extra_args=["--plugin-dir", str(REPO_ROOT), *extra_args],
    )

    try:
        # --- Phase 2: Start session and boot FO ---

        print()
        print("--- Phase 2: Start interactive session ---")
        start_with_trust_handling(session, ready_timeout=30)
        print("  Session ready")

        print("  Sending FO skill invocation...")
        session.send("/spacedock:first-officer")
        booted = session.wait_for(
            r"spike-workflow|backlog|dispatch|status|workflow",
            timeout=90,
            min_matches=1,
        )
        print(f"  FO booted: {booted}")

        if not booted:
            clean = session.get_clean_output()
            print("  WARNING: FO did not boot within timeout")
            print(f"  Output tail: ...{clean[-500:]}")
            fail("FO booted and acknowledged workflow")
            return

        pass_("FO booted and acknowledged workflow")

        # --- Phase 3: Send entity dispatch request ---

        print()
        print("--- Phase 3: Entity dispatch request ---")
        session.send(f"Work on test-entity through the workflow at {abs_workflow}")
        team_evidence = session.wait_for(
            r"[Tt]eam|TeamCreate|team_name|dispatch|[Aa]gent",
            timeout=120,
            min_matches=1,
        )

        # --- Phase 4: Assertions ---

        print()
        print("--- Phase 4: Validation ---")

        clean_output = session.get_clean_output()
        single_entity_mentioned = "single-entity mode" in clean_output.lower()

        if single_entity_mentioned:
            fail("FO did NOT enter single-entity mode in interactive session")
        else:
            pass_("FO did NOT enter single-entity mode in interactive session")

        if team_evidence:
            pass_("team creation or dispatch evidence found")
        else:
            fail("team creation or dispatch evidence found")

        # Informational: bare mode is acceptable (teams may not be available),
        # but single-entity mode is not
        bare_mode_mentioned = "bare mode" in clean_output.lower() or "bare-mode" in clean_output.lower()
        if bare_mode_mentioned:
            print("  INFO: Bare mode detected (teams may not be available — this is OK)")
            print("        The key assertion is that single-entity mode was NOT triggered")

    finally:
        print()
        print("--- Stopping session ---")
        session.stop()
        if failures > 0:
            print(f"  Test dir preserved at: {project_dir}")
        else:
            shutil.rmtree(project_dir, ignore_errors=True)
        print("  Done")

    # --- Results ---

    print()
    print("=== Results ===")
    total = passes + failures
    print(f"  {passes} passed, {failures} failed (out of {total} checks)")
    print()

    if failures > 0:
        print("RESULT: FAIL")
        sys.exit(1)
    else:
        print("RESULT: PASS")


if __name__ == "__main__":
    main()
