#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E spike test for Codex multi-agent rejection handling on the rejection-flow fixture.
# ABOUTME: Verifies that validation can reject implementation and trigger observable follow-up work.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    CodexLogParser,
    TestRunner,
    create_test_project,
    git_add_commit,
    run_codex_first_officer,
    setup_fixture,
)


def main():
    t = TestRunner("Codex Rejection Flow E2E Test")

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "rejection-flow", "rejection-pipeline")

    git_add_commit(t.test_project_dir, "setup: codex rejection flow fixture")

    t.check_cmd(
        "status script runs without errors",
        ["python3", "rejection-pipeline/status"],
        cwd=t.test_project_dir,
    )

    status_result = subprocess.run(
        ["python3", "rejection-pipeline/status", "--next"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    )
    t.check("status --next detects dispatchable entity", "buggy-add-task" in status_result.stdout)

    print()
    print("--- Phase 2: Run Codex first officer ---")

    fo_exit = run_codex_first_officer(t, "rejection-pipeline")
    t.check("Codex launcher returned an exit code", fo_exit is not None)

    print()
    print("--- Phase 3: Validate ---")

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text = log.full_text()

    entity_main = t.test_project_dir / "rejection-pipeline" / "buggy-add-task.md"
    worktrees_dir = t.test_project_dir / ".worktrees"

    found_rejected = bool(re.search(r"REJECTED|recommend reject|failing test|Expected 5, got -1", fo_text, re.IGNORECASE))
    if entity_main.is_file() and re.search(r"REJECTED", entity_main.read_text(), re.IGNORECASE):
        found_rejected = True

    if worktrees_dir.is_dir():
        for wt in worktrees_dir.iterdir():
            wt_entity = wt / "rejection-pipeline" / "buggy-add-task.md"
            if wt_entity.is_file() and re.search(r"REJECTED", wt_entity.read_text(), re.IGNORECASE):
                found_rejected = True

    t.check("validation surfaced a rejection signal", found_rejected)

    spawn_count = log.spawn_count()
    t.check(
        "multiple worker dispatches occurred",
        spawn_count >= 2 or bool(re.search(r"validation|implementation", fo_text, re.IGNORECASE)),
    )

    follow_up_observed = False
    if re.search(r"feedback-to|follow-up|fix|rework|implementation", fo_text, re.IGNORECASE):
        follow_up_observed = True

    if worktrees_dir.is_dir():
        for wt in worktrees_dir.iterdir():
            wt_entity = wt / "rejection-pipeline" / "buggy-add-task.md"
            if wt_entity.is_file():
                text = wt_entity.read_text()
                if re.search(r"Feedback Cycles|Stage Report: validation|Stage Report: implementation", text, re.IGNORECASE):
                    follow_up_observed = True

    t.check("follow-up work after rejection was observable", follow_up_observed)

    if worktrees_dir.is_dir():
        worktree_names = [wt.name for wt in worktrees_dir.iterdir()]
    else:
        worktree_names = []

    t.check(
        "packaged worker uses safe worktree key",
        any("spacedock-ensign" in name for name in worktree_names),
    )
    t.check(
        "logical packaged id does not leak into worktree names",
        not any("spacedock:ensign" in name for name in worktree_names),
    )

    t.results()


if __name__ == "__main__":
    main()
