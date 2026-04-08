#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import CodexLogParser, TestRunner, create_test_project, git_add_commit, run_codex_first_officer, setup_fixture


def test_prepare_dispatch_creates_validation_worktree_and_payload():
    t = TestRunner("codex prepare dispatch direct FO", keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, "rejection-flow-packaged-agent", "packaged-agent-pipeline")
    git_add_commit(t.test_project_dir, "setup: helper fixture")

    fo_exit = run_codex_first_officer(
        t,
        "packaged-agent-pipeline",
        run_goal=(
            "Process only the entity `buggy-add-task`. "
            "Dispatch the validation stage, wait for the validation worker to finish, "
            "then summarize the outcome and stop. "
            "Do not begin any follow-up dispatch after the validation result."
        ),
        timeout_s=180,
    )
    assert fo_exit == 0

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text = log.full_text()
    invocation_text = (t.log_dir / "codex-fo-invocation.txt").read_text()
    assert "codex_prepare_dispatch.py" not in invocation_text
    assert "spacedock:first-officer" in invocation_text
    assert log.spawn_count() >= 1
    assert len(log.completed_agent_messages()) >= 1
    assert "spacedock:ensign" in fo_text

    branches = subprocess.run(
        ["git", "branch", "--list"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    ).stdout
    assert "spacedock-ensign/buggy-add-task" in branches
    assert "validation" in fo_text


def test_prepare_dispatch_refuses_to_auto_advance_gated_entities_to_done():
    t = TestRunner("codex prepare dispatch gate hold", keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, "gated-pipeline", "gated-pipeline")
    git_add_commit(t.test_project_dir, "setup: helper fixture for gated entity")

    fo_exit = run_codex_first_officer(
        t,
        "gated-pipeline",
        run_goal=(
            "Process only the entity `gate-test-entity`. "
            "Stop at the gate and report the approval status instead of advancing into completion."
        ),
        timeout_s=120,
    )

    assert fo_exit == 0

    entity_text = (workflow_dir / "gate-test-entity.md").read_text()
    assert "status: work" in entity_text
    assert "status: done" not in entity_text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
