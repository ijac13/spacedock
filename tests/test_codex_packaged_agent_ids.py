#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit-style coverage for Codex packaged logical worker ids in the Spacedock prototype.

from __future__ import annotations

import pytest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    build_codex_first_officer_invocation_prompt,
    build_codex_worker_bootstrap_prompt,
    resolve_codex_worker,
)


def test_packaged_agent_id_resolves_to_agent_asset_with_safe_worker_key():
    resolved = resolve_codex_worker("spacedock:ensign")

    assert resolved["dispatch_agent_id"] == "spacedock:ensign"
    assert resolved["worker_key"] == "spacedock-ensign"
    assert resolved["asset_kind"] == "agent"
    assert resolved["asset_path"].name == "ensign.md"
    assert resolved["asset_path"].parent.name == "agents"


def test_unknown_packaged_agent_id_is_rejected():
    with pytest.raises(ValueError):
        resolve_codex_worker("spacedock:unknown")


def test_custom_non_spacedock_agent_id_falls_back_to_generic_worker():
    resolved = resolve_codex_worker("acme:reviewer")

    assert resolved["dispatch_agent_id"] == "acme:reviewer"
    assert resolved["worker_key"] == "acme-reviewer"
    assert resolved["asset_kind"] == "prompt"
    assert resolved["asset_name"] == "generic-worker"


def test_exec_harness_invokes_first_officer_skill_by_name():
    prompt = build_codex_first_officer_invocation_prompt("/tmp/example-workflow")

    assert "spacedock:first-officer" in prompt
    assert "workflow" in prompt
    assert "codex-first-officer-prompt.md" not in prompt


def test_packaged_worker_bootstrap_tells_worker_to_read_agent_first():
    resolved = resolve_codex_worker("spacedock:ensign")

    prompt = build_codex_worker_bootstrap_prompt(
        resolved,
        workflow_dir=Path("/tmp/project/workflow"),
        entity_path=Path("/tmp/project/workflow/entity.md"),
        stage_name="implementation",
        stage_definition_text="Do the implementation work.",
        worktree_path=Path("/tmp/project/.spacedock/worktrees/spacedock-ensign-entity"),
        checklist=["Write the stage report", "Commit code changes"],
    )

    assert "Resolve your role definition" in prompt
    assert "~/.agents/skills/{namespace}/agents/{name}.md" in prompt
    assert "role_asset_name: ensign" in prompt
    assert "first" in prompt.lower()
    assert "spacedock:ensign" in prompt
    assert "worker_key: spacedock-ensign" in prompt


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
