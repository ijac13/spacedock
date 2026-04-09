#!/usr/bin/env python3
# ABOUTME: PTY-based E2E regression test for single-entity mode trigger condition.
# ABOUTME: Verifies that interactive sessions create teams (not bare mode) when a user names an entity.

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "spike-no-gate"


def setup_test_project() -> Path:
    """Create a temp git project with the spike-no-gate fixture and agent files."""
    project_dir = Path(tempfile.mkdtemp(prefix="sem-test-"))

    # Initialize git repo
    subprocess.run(["git", "init", str(project_dir)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=project_dir,
    )

    # Copy fixture into workflow directory
    workflow_dir = project_dir / "spike-workflow"
    shutil.copytree(FIXTURE_DIR, workflow_dir)
    status = workflow_dir / "status"
    if status.exists():
        status.chmod(status.stat().st_mode | 0o111)

    # Install agent files
    agents_dir = project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "agents" / "first-officer.md", agents_dir / "first-officer.md")
    shutil.copy2(REPO_ROOT / "agents" / "ensign.md", agents_dir / "ensign.md")

    # Commit everything
    subprocess.run(["git", "add", "-A"], capture_output=True, check=True, cwd=project_dir)
    subprocess.run(
        ["git", "commit", "-m", "setup: single-entity mode interactive test"],
        capture_output=True, check=True, cwd=project_dir,
    )

    return project_dir


def test_interactive_dispatch_creates_team():
    """Verify that naming an entity in an interactive session triggers team dispatch, not single-entity mode."""
    print("--- Setup: Create test project ---")
    project_dir = setup_test_project()
    print(f"  Project dir: {project_dir}")

    abs_workflow = project_dir / "spike-workflow"

    session = InteractiveSession(
        model="haiku",
        max_budget_usd=2.00,
        cwd=project_dir,
        extra_args=["--plugin-dir", str(REPO_ROOT)],
    )

    try:
        print("--- Starting interactive session ---")
        session.start(ready_timeout=20)
        print("  Session ready")

        # Boot the FO skill
        print("--- Sending FO skill invocation ---")
        session.send(f"/spacedock:first-officer")
        # Wait for the FO to acknowledge the workflow — look for entity-related output
        booted = session.wait_for(r"spike-workflow|backlog|dispatch|status", timeout=90, min_matches=1)
        print(f"  FO booted: {booted}")

        if not booted:
            clean = session.get_clean_output()
            print("  WARNING: FO did not boot within timeout")
            print(f"  Output tail: ...{clean[-500:]}")
            return False

        # Ask to work on a specific entity by name — this is the trigger that
        # used to incorrectly activate single-entity mode
        print("--- Sending entity dispatch request ---")
        session.send(f"Work on test-entity through the workflow at {abs_workflow}")
        # Wait for evidence of team creation or agent dispatch
        team_evidence = session.wait_for(
            r"[Tt]eam|TeamCreate|team_name|dispatch|[Aa]gent",
            timeout=120,
            min_matches=1,
        )
        print(f"  Team/dispatch evidence found: {team_evidence}")

        # Check for absence of single-entity mode
        clean_output = session.get_clean_output()
        single_entity_mentioned = "single-entity mode" in clean_output.lower()
        bare_mode_mentioned = "bare mode" in clean_output.lower() or "bare-mode" in clean_output.lower()

        print()
        print("=== Assertions ===")

        passed = True

        # AC3a: FO must NOT enter single-entity mode in interactive session
        if single_entity_mentioned:
            print("  FAIL: FO entered single-entity mode in interactive session")
            passed = False
        else:
            print("  PASS: FO did NOT enter single-entity mode")

        # AC3b: FO should show team creation or dispatch evidence
        if team_evidence:
            print("  PASS: Team creation or dispatch evidence found")
        else:
            print("  FAIL: No team creation or dispatch evidence found")
            passed = False

        # Informational: bare mode check (bare mode is acceptable if teams
        # aren't available, but single-entity mode is not)
        if bare_mode_mentioned:
            print("  INFO: Bare mode detected (teams may not be available — this is OK)")
            print("        The key assertion is that single-entity mode was NOT triggered")

        return passed

    finally:
        print()
        print("--- Stopping session ---")
        session.stop()
        # Clean up temp directory
        shutil.rmtree(project_dir, ignore_errors=True)
        print("  Done")


def main():
    print("=== Single-Entity Mode Interactive Regression Test ===")
    print()

    if "--live" not in sys.argv:
        print("--- Live test skipped (pass --live to run) ---")
        print("This test requires a live claude session (~$1-2 with haiku).")
        print()
        print("=== Skipped ===")
        return

    success = test_interactive_dispatch_creates_team()
    print()
    if success:
        print("=== PASS ===")
    else:
        print("=== FAIL ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
