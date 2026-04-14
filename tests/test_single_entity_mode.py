# ABOUTME: PTY-based E2E regression test for single-entity mode trigger condition.
# ABOUTME: Verifies that interactive sessions create teams (not bare mode) when a user names an entity.

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib_interactive import InteractiveSession, _strip_ansi  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "spike-no-gate"


def _setup_test_project() -> Path:
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


def _start_with_trust_handling(session: InteractiveSession, ready_timeout: float = 30.0) -> None:
    if session._started:
        raise RuntimeError("Session already started")

    from test_lib_interactive import _clean_env
    import pty

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
    post_trust_pos = 0
    while time.time() - start < ready_timeout:
        session._drain(timeout=1.0)

        if not trust_handled:
            clean = session.get_clean_output()
            if re.search(r"trust.*folder|Do you want to trust", clean, re.IGNORECASE):
                print("  Trust dialog detected, sending Enter to accept...")
                os.write(fd, b"\r")
                time.sleep(1.0)
                trust_handled = True
                post_trust_pos = len(session._raw_output)
                continue

        new_output = session._raw_output[post_trust_pos:]
        clean_new = _strip_ansi(new_output.decode("utf-8", errors="replace"))
        if "\u276f" in clean_new:
            return

    raise TimeoutError(f"Session did not become ready within {ready_timeout}s")


@pytest.mark.live_claude
@pytest.mark.serial
def test_single_entity_mode(model, budget):
    """Interactive FO in single-entity mode does NOT create a team."""
    print("=== Single-Entity Mode Interactive Regression Test ===")
    print()

    passes = 0
    failures = 0

    def pass_(label):
        nonlocal passes
        passes += 1
        print(f"  PASS: {label}")

    def fail_(label):
        nonlocal failures
        failures += 1
        print(f"  FAIL: {label}")

    print("--- Phase 1: Set up test project ---")
    project_dir = _setup_test_project()
    print(f"  Project dir: {project_dir}")

    abs_workflow = project_dir / "spike-workflow"
    session = InteractiveSession(
        model=model,
        max_budget_usd=budget if budget is not None else 2.00,
        cwd=project_dir,
        extra_args=["--plugin-dir", str(REPO_ROOT)],
    )

    try:
        print()
        print("--- Phase 2: Start interactive session ---")
        _start_with_trust_handling(session, ready_timeout=30)
        print("  Session ready")

        print("  Sending FO skill invocation...")
        session.send("/spacedock:first-officer")
        booted = session.wait_for(
            r"spike-workflow|backlog|dispatch|status|workflow",
            timeout=90, min_matches=1,
        )
        print(f"  FO booted: {booted}")

        if not booted:
            clean = session.get_clean_output()
            print("  WARNING: FO did not boot within timeout")
            print(f"  Output tail: ...{clean[-500:]}")
            fail_("FO booted and acknowledged workflow")
        else:
            pass_("FO booted and acknowledged workflow")

            print()
            print("--- Phase 3: Entity dispatch request ---")
            session.send(f"Work on test-entity through the workflow at {abs_workflow}")
            team_evidence = session.wait_for(
                r"[Tt]eam|TeamCreate|team_name|dispatch|[Aa]gent",
                timeout=120, min_matches=1,
            )

            print()
            print("--- Phase 4: Validation ---")
            clean_output = session.get_clean_output()
            single_entity_activated = bool(re.search(
                r"(entering|switching to|activating|in) single-entity mode",
                clean_output, re.IGNORECASE,
            ))

            if team_evidence and not single_entity_activated:
                pass_("FO used team dispatch (not single-entity mode)")
            elif single_entity_activated:
                fail_("FO did NOT activate single-entity mode in interactive session")
            elif not team_evidence:
                fail_("team creation or dispatch evidence found")

            bare_mode_mentioned = "bare mode" in clean_output.lower() or "bare-mode" in clean_output.lower()
            if bare_mode_mentioned:
                print("  INFO: Bare mode detected (teams may not be available — this is OK)")

    finally:
        print()
        print("--- Stopping session ---")
        session.stop()
        if failures > 0:
            print(f"  Test dir preserved at: {project_dir}")
        else:
            shutil.rmtree(project_dir, ignore_errors=True)
        print("  Done")

    print()
    print("=== Results ===")
    total = passes + failures
    print(f"  {passes} passed, {failures} failed (out of {total} checks)")
    print()
    assert failures == 0, f"{failures} checks failed"

