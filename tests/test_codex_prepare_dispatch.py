#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import TestRunner, create_test_project, git_add_commit, prepare_codex_skill_home, setup_fixture


def test_prepare_dispatch_creates_validation_worktree_and_payload():
    t = TestRunner("codex prepare dispatch helper", keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, "rejection-flow-packaged-agent", "packaged-agent-pipeline")
    git_add_commit(t.test_project_dir, "setup: helper fixture")

    skill_home = prepare_codex_skill_home(t.test_dir, t.repo_root)
    helper = skill_home / ".agents" / "skills" / "spacedock" / "scripts" / "codex_prepare_dispatch.py"
    result = subprocess.run(
        [
            "python3",
            str(helper),
            "--repo-root",
            str(t.test_project_dir),
            "--workflow-dir",
            str(workflow_dir),
            "--entity-slug",
            "buggy-add-task",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["dispatch_agent_id"] == "spacedock:ensign"
    assert payload["worker_key"] == "spacedock-ensign"
    assert payload["stage_name"] == "validation"
    assert payload["role_asset_kind"] == "agent"
    assert payload["role_asset_name"] == "ensign"
    assert "spacedock-ensign-buggy-add-task-validation" in payload["worktree_path"]
    assert "fork_context=false" not in payload["spawn_message"]
    assert "~/.agents/skills/{namespace}/agents/{name}.md" in payload["spawn_message"]

    entity_text = (workflow_dir / "buggy-add-task.md").read_text()
    assert "status: validation" in entity_text
    assert "spacedock-ensign-buggy-add-task-validation" in entity_text

    branches = subprocess.run(
        ["git", "branch", "--list"],
        capture_output=True,
        text=True,
        cwd=t.test_project_dir,
        check=True,
    ).stdout
    assert "spacedock-ensign-buggy-add-task-validation" in branches

    worktree_entity = Path(payload["entity_path"])
    assert worktree_entity.is_file()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
