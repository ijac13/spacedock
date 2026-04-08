#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Direct E2E proof for explicit packaged stage agent ids in the Codex Spacedock prototype.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import CodexLogParser, TestRunner, create_test_project, git_add_commit, run_codex_first_officer, setup_fixture


def main():
    t = TestRunner("Codex Packaged Agent E2E Test")

    print("--- Phase 1: Set up explicit packaged-agent fixture ---")

    create_test_project(t)
    workflow_dir = setup_fixture(t, "rejection-flow-packaged-agent", "packaged-agent-pipeline")
    git_add_commit(t.test_project_dir, "setup: codex packaged agent fixture")

    readme_text = (workflow_dir / "README.md").read_text()
    t.check("fixture explicitly declares spacedock packaged agent", "agent: spacedock:ensign" in readme_text)
    t.check_cmd(
        "status script runs without errors",
        ["python3", "packaged-agent-pipeline/status"],
        cwd=t.test_project_dir,
    )

    status_result = subprocess.run(
        ["python3", "packaged-agent-pipeline/status", "--next"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    )
    t.check("status --next detects dispatchable entity", "buggy-add-task" in status_result.stdout)

    print()
    print("--- Phase 2: Run Codex first officer ---")

    fo_exit = run_codex_first_officer(
        t,
        "packaged-agent-pipeline",
        run_goal=(
            "Process only the entity `buggy-add-task`. "
            "Dispatch the validation stage, wait for the validation worker to finish, "
            "then summarize the outcome and stop. "
            "Do not begin any follow-up dispatch after the validation result. "
            "When you dispatch the worker, use the exact Codex pattern "
            "`spawn_agent(agent_type=\"worker\", fork_context=false, message=<fully self-contained prompt>)` "
            "followed by `wait_agent(...)`."
        ),
        timeout_s=180,
    )
    t.check("Codex launcher exited cleanly", fo_exit == 0)

    print()
    print("--- Phase 3: Validate explicit packaged-agent path ---")

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text = log.full_text()
    worker_messages = log.completed_agent_messages()
    invocation_text = (t.log_dir / "codex-fo-invocation.txt").read_text()
    t.check("harness invoked the spacedock first officer skill", "spacedock:first-officer" in invocation_text)
    t.check("FO or worker output mentions spacedock packaged id", bool(re.search(r"spacedock:ensign", fo_text)))
    t.check(
        "FO or worker output mentions packaged skill resolution",
        "spacedock:ensign" in fo_text and (
            "invoke the `spacedock:ensign` skill" in fo_text
            or "role_asset_kind: skill" in fo_text
            or "role_asset_name: ensign" in fo_text
        ),
    )
    t.check("FO spawned a worker for the packaged agent path", log.spawn_count() >= 1)
    t.check("worker completed and returned a result", len(worker_messages) >= 1)

    entity_text = (workflow_dir / "buggy-add-task.md").read_text()
    worktree_match = re.search(r"^worktree:\s*(.+)$", entity_text, re.MULTILINE)
    worktree_value = worktree_match.group(1).strip() if worktree_match else ""
    t.check("safe packaged worker key appears in worktree path", "spacedock-ensign" in worktree_value)
    t.check("raw packaged worker id does not leak into worktree path", "spacedock:ensign" not in worktree_value)

    branches = subprocess.run(
        ["git", "branch", "--list"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    ).stdout
    t.check("safe packaged worker key appears in branch names", "spacedock-ensign-" in branches)
    t.check("raw packaged worker id does not leak into branch names", "spacedock:ensign" not in branches)

    t.results()


if __name__ == "__main__":
    main()
