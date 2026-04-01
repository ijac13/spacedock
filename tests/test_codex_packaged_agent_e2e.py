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

    fo_exit = run_codex_first_officer(t, "packaged-agent-pipeline")
    t.check("Codex launcher returned an exit code", fo_exit is not None)

    print()
    print("--- Phase 3: Validate explicit packaged-agent path ---")

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text = log.full_text()
    invocation_text = (t.log_dir / "codex-fo-invocation.txt").read_text()
    t.check("harness invoked the spacedock first officer skill", "spacedock:first-officer" in invocation_text)
    t.check("FO or worker output mentions spacedock packaged id", bool(re.search(r"spacedock:ensign", fo_text)))
    t.check("FO or worker output mentions the ensign skill asset", "ensign/SKILL.md" in fo_text)
    t.check("FO spawned a worker for the packaged agent path", log.spawn_count() >= 1)

    worktrees_dir = t.test_project_dir / ".worktrees"
    worktree_names = [wt.name for wt in worktrees_dir.iterdir()] if worktrees_dir.is_dir() else []
    t.check("safe packaged worker key appears in worktree names", any("spacedock-ensign" in name for name in worktree_names))
    t.check("raw packaged worker id does not leak into worktree names", not any("spacedock:ensign" in name for name in worktree_names))

    branches = subprocess.run(
        ["git", "branch", "--list"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    ).stdout
    t.check("safe packaged worker key appears in branch names", "spacedock-ensign/" in branches)
    t.check("raw packaged worker id does not leak into branch names", "spacedock:ensign/" not in branches)

    t.results()


if __name__ == "__main__":
    main()
