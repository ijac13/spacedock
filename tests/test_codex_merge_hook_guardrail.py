#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for Codex first-officer merge hook behavior.
# ABOUTME: Verifies merge hooks fire before archive and that the no-mods fallback still merges locally.

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import TestRunner, check_merge_outcome, create_test_project, git_add_commit, run_codex_first_officer, setup_fixture


def run_with_hook_fixture(t: TestRunner) -> None:
    create_test_project(t, "with-hook-project")
    workflow_dir = setup_fixture(t, "merge-hook-pipeline", "merge-hook-pipeline")
    git_add_commit(t.test_project_dir, "setup: codex merge-hook fixture")

    t.check_cmd(
        "status script runs without errors (with hook)",
        ["bash", "merge-hook-pipeline/status"],
        cwd=t.test_project_dir,
    )

    fo_exit = run_codex_first_officer(
        t,
        "merge-hook-pipeline",
        run_goal=(
            "Process only the entity `merge-hook-entity` through the workflow to terminal completion. "
            "If it reaches the terminal stage, run any merge hooks before local merge, then archive the entity. "
            "Stop after the merge hook result and archive outcome are determined."
        ),
        timeout_s=240,
        log_name="codex-merge-hook-log.txt",
    )
    t.check("Codex launcher exited cleanly (with hook)", fo_exit == 0)

    check_merge_outcome(
        t,
        t.test_project_dir,
        "merge-hook-pipeline",
        "merge-hook-entity",
        "spacedock-ensign-merge-hook-entity-work",
        hook_expected=True,
        archive_required=True,
    )


def run_without_hook_fixture(t: TestRunner) -> None:
    fixture_dir = t.repo_root / "tests" / "fixtures" / "merge-hook-pipeline"

    project_dir = create_test_project(t, "no-hook-project")
    workflow_dir = project_dir / "merge-hook-pipeline"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    for item in fixture_dir.iterdir():
        if item.is_dir():
            continue
        shutil.copy2(item, workflow_dir / item.name)
    status_script = workflow_dir / "status"
    if status_script.exists():
        status_script.chmod(status_script.stat().st_mode | 0o111)

    git_add_commit(t.test_project_dir, "setup: codex merge-hook fixture without mods")

    t.check_cmd(
        "status script runs without errors (no hook)",
        ["bash", "merge-hook-pipeline/status"],
        cwd=t.test_project_dir,
    )

    fo_exit = run_codex_first_officer(
        t,
        "merge-hook-pipeline",
        run_goal=(
            "Process only the entity `merge-hook-entity` through the workflow to terminal completion. "
            "No merge hook mod is installed in this fixture, so use the default local merge path and archive the entity. "
            "Stop after the archive outcome is determined."
        ),
        timeout_s=240,
        log_name="codex-merge-hook-nomods-log.txt",
    )
    t.check("Codex launcher exited cleanly (no hook)", fo_exit == 0)

    check_merge_outcome(
        t,
        t.test_project_dir,
        "merge-hook-pipeline",
        "merge-hook-entity",
        "spacedock-ensign-merge-hook-entity-work",
        hook_expected=False,
        archive_required=True,
    )


def main():
    t = TestRunner("Codex Merge Hook Guardrail E2E Test")

    print("--- Phase 1: With merge hook mod ---")
    run_with_hook_fixture(t)

    print()
    print("--- Phase 2: Without merge hook mod ---")
    run_without_hook_fixture(t)

    t.results()


if __name__ == "__main__":
    main()
