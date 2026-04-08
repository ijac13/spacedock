#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import CodexLogParser, TestRunner, create_test_project, git_add_commit, run_codex_first_officer, setup_fixture


def _run_terminal_completion(t: TestRunner, run_goal: str) -> None:
    fo_exit = run_codex_first_officer(
        t,
        "merge-hook-pipeline",
        run_goal=run_goal,
        timeout_s=240,
    )
    assert fo_exit == 0

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    assert log.spawn_count() >= 1
    assert len(log.completed_agent_messages()) >= 1


def test_finalize_terminal_entity_runs_merge_hook_and_cleans_up():
    t = TestRunner("codex terminal completion direct FO with merge hook", keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, "merge-hook-pipeline", "merge-hook-pipeline")
    git_add_commit(t.test_project_dir, "setup: merge hook guardrail test fixture")

    _run_terminal_completion(
        t,
        (
            "Process only the entity `merge-hook-entity` through the workflow to terminal completion. "
            "Run any merge hooks before local merge, then archive the entity. "
            "Stop after the archive outcome is determined."
        ),
    )

    branch_name = "spacedock-ensign-merge-hook-entity-work"
    assert (workflow_dir / "_merge-hook-fired.txt").is_file()
    assert (workflow_dir / "_archive" / "merge-hook-entity.md").is_file()
    assert not (t.test_project_dir / ".spacedock" / "worktrees" / branch_name).exists()


def test_finalize_terminal_entity_without_mods_uses_local_merge_fallback():
    t = TestRunner("codex terminal completion direct FO without merge hook", keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, "merge-hook-pipeline", "merge-hook-pipeline")
    git_add_commit(t.test_project_dir, "setup: merge hook guardrail test fixture")

    mods_dir = workflow_dir / "_mods"
    if mods_dir.exists():
        for item in mods_dir.iterdir():
            if item.is_file():
                item.unlink()
        mods_dir.rmdir()

    _run_terminal_completion(
        t,
        (
            "Process only the entity `merge-hook-entity` through the workflow to terminal completion. "
            "No merge hook mod is installed in this fixture, so use the default local merge path and archive the entity. "
            "Stop after the archive outcome is determined."
        ),
    )

    branch_name = "spacedock-ensign-merge-hook-entity-work"
    assert not (workflow_dir / "_merge-hook-fired.txt").exists()
    assert (workflow_dir / "_archive" / "merge-hook-entity.md").is_file()
    assert not (t.test_project_dir / ".spacedock" / "worktrees" / branch_name).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
