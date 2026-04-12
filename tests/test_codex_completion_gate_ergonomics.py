#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static regression tests for the Codex interactive completion and gate ergonomics rules.
# ABOUTME: Verifies prompt guidance and runtime docs keep gated completions foregrounded and dispatch metadata-driven.

from __future__ import annotations

from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import build_codex_first_officer_invocation_prompt


REPO_ROOT = Path(__file__).resolve().parent.parent


def read_text(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


def test_codex_prompt_foregrounds_gated_completion_and_gate_handling():
    """Purpose: pin the interactive Codex completion interrupt rule.

    Coverage intention: the first-officer prompt must tell Codex to foreground a
    gated stage report before unrelated conversation can continue.
    """
    prompt = build_codex_first_officer_invocation_prompt("/tmp/example-workflow")

    assert "completed gated stage is the next required action" in prompt
    assert "foreground the stage report and gate handling" in prompt


def test_codex_prompt_uses_stage_metadata_for_worktree_dispatch():
    """Purpose: pin metadata-driven dispatch mode selection.

    Coverage intention: stages without `worktree: true` must stay on main rather
    than defaulting into worktree dispatch just because Codex is active.
    """
    prompt = build_codex_first_officer_invocation_prompt("/tmp/example-workflow")

    assert "Stage metadata is authoritative for dispatch mode" in prompt
    assert "only create a worktree when the stage definition says `worktree: true`" in prompt
    assert "if it is absent or false, dispatch on main" in prompt


def test_codex_prompt_auto_routes_rejected_feedback_without_drift():
    """Purpose: pin immediate rejection routing for feedback stages.

    Coverage intention: a REJECTED validation with `feedback-to` must route
    immediately through the existing worker handle instead of lingering behind
    unrelated conversation.
    """
    prompt = build_codex_first_officer_invocation_prompt("/tmp/example-workflow")

    assert "If validation returns `REJECTED`" in prompt
    assert "route the rejection immediately" in prompt
    assert "existing worker handle" in prompt


def test_codex_ensign_runtime_requires_explicit_worktree_path():
    """Purpose: keep the packaged worker contract from inferring a worktree.

    Coverage intention: the Codex ensign runtime should stay on the main branch
    unless the first officer explicitly provides a worktree path.
    """
    text = read_text("skills/ensign/references/codex-ensign-runtime.md")

    assert "If no worktree path is provided, stay on the main branch" in text
    assert "gated completion as the next required action" in text
    assert "surface the stage report before anything unrelated" in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
