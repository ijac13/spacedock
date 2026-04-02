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


def _prepare_terminal_state(test_name: str, fixture_name: str) -> tuple[TestRunner, Path, Path, dict[str, object]]:
    t = TestRunner(test_name, keep_test_dir=False)
    create_test_project(t)
    workflow_dir = setup_fixture(t, fixture_name, "merge-hook-pipeline")
    git_add_commit(t.test_project_dir, f"setup: {fixture_name}")

    skill_home = prepare_codex_skill_home(t.test_dir, t.repo_root)
    dispatch_helper = skill_home / ".agents" / "skills" / "spacedock" / "scripts" / "codex_prepare_dispatch.py"
    result = subprocess.run(
        [
            "python3",
            str(dispatch_helper),
            "--repo-root",
            str(t.test_project_dir),
            "--workflow-dir",
            str(workflow_dir),
            "--entity-slug",
            "merge-hook-entity",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    worktree_entity = Path(payload["entity_path"])
    text = worktree_entity.read_text()
    text += '\nMerge hook test complete.\n\n## Stage Report: work\n\n- [x] Produce the stage outputs for this entity\n  Added the required work summary.\n- [x] Update the stage report with evidence for each checklist item\n  Added the stage report in the entity body.\n- [x] Commit meaningful stage work before finishing\n  Committed the worktree changes for the stage.\n\n### Summary\n\nCompleted the work stage and recorded the evidence in the entity file.\n'
    worktree_entity.write_text(text)
    subprocess.run(
        ["git", "-C", str(Path(payload["worktree_path"])), "add", str(worktree_entity.relative_to(Path(payload["worktree_path"])))],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(Path(payload["worktree_path"])), "commit", "-m", "work: prepare finalize helper test"],
        capture_output=True,
        text=True,
        check=True,
    )
    return t, workflow_dir, skill_home, payload


def test_finalize_helper_runs_merge_hook_and_cleans_up():
    t, workflow_dir, skill_home, payload = _prepare_terminal_state(
        "codex finalize helper with merge hook",
        "merge-hook-pipeline",
    )
    helper = skill_home / ".agents" / "skills" / "spacedock" / "scripts" / "codex_finalize_terminal_entity.py"
    result = subprocess.run(
        [
            "python3",
            str(helper),
            "--repo-root",
            str(t.test_project_dir),
            "--workflow-dir",
            str(workflow_dir),
            "--entity-slug",
            "merge-hook-entity",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)
    assert output["handled_by_hook"] is True
    assert output["pr_pending"] is False
    assert output["worktree_removed"] is True
    assert (workflow_dir / "_merge-hook-fired.txt").is_file()
    assert (workflow_dir / "_archive" / "merge-hook-entity.md").is_file()
    assert not Path(payload["worktree_path"]).exists()


def test_finalize_helper_without_mods_uses_local_merge_fallback():
    t, workflow_dir, skill_home, payload = _prepare_terminal_state(
        "codex finalize helper without merge hook",
        "merge-hook-pipeline",
    )
    mods_dir = workflow_dir / "_mods"
    if mods_dir.exists():
        for item in mods_dir.iterdir():
            if item.is_file():
                item.unlink()
        mods_dir.rmdir()

    helper = skill_home / ".agents" / "skills" / "spacedock" / "scripts" / "codex_finalize_terminal_entity.py"
    result = subprocess.run(
        [
            "python3",
            str(helper),
            "--repo-root",
            str(t.test_project_dir),
            "--workflow-dir",
            str(workflow_dir),
            "--entity-slug",
            "merge-hook-entity",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    output = json.loads(result.stdout)
    assert output["handled_by_hook"] is False
    assert output["pr_pending"] is False
    assert output["worktree_removed"] is True
    assert not (workflow_dir / "_merge-hook-fired.txt").exists()
    assert (workflow_dir / "_archive" / "merge-hook-entity.md").is_file()
    assert not Path(payload["worktree_path"]).exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
