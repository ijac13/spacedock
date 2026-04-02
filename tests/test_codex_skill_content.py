#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Content-level checks for the Codex skill assets and their shared maintenance structure.

from __future__ import annotations

from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def test_first_officer_skill_bootstraps_the_packaged_agent_asset():
    text = read_text("skills/first-officer/SKILL.md")

    assert "../../agents/first-officer.md" in text


def test_claude_agent_entry_points_reference_claude_runtime():
    fo_text = read_text("agents/first-officer.md")
    assert "references/first-officer-shared-core.md" in fo_text
    assert "references/code-project-guardrails.md" in fo_text
    assert "references/claude-first-officer-runtime.md" in fo_text

    ensign_text = read_text("agents/ensign.md")
    assert "references/ensign-shared-core.md" in ensign_text
    assert "references/code-project-guardrails.md" in ensign_text
    assert "references/claude-ensign-runtime.md" in ensign_text


def test_codex_skill_references_codex_runtime():
    skill_text = read_text("skills/first-officer/SKILL.md")
    assert "../../agents/first-officer.md" in skill_text


def test_first_officer_shared_core_covers_all_behavioral_sections():
    text = read_text("references/first-officer-shared-core.md")

    for heading in [
        "## Startup",
        "## Single-Entity Mode",
        "## Working Directory",
        "## Dispatch",
        "## Completion and Gates",
        "## Feedback Rejection Flow",
        "## Merge and Cleanup",
        "## State Management",
        "## Mod Hook Convention",
        "## Clarification and Communication",
        "## Scaffolding and Issue Filing",
    ]:
        assert heading in text

    assert "Output Format" in text
    assert "feedback-to" in text


def test_ensign_shared_core_keeps_stage_report_protocol():
    text = read_text("references/ensign-shared-core.md")

    assert "## Stage Report: {stage_name}" in text
    assert "overwrite" in text.lower()
    assert "agents/" in text
    assert "Do NOT modify YAML frontmatter" in text


def test_code_project_guardrails_cover_worktrees_and_scaffolding():
    text = read_text("references/code-project-guardrails.md")

    assert ".worktrees/" in text
    assert "agents/" in text
    assert "git worktree" in text
    assert "scaffolding" in text.lower()


def test_codex_runtime_docs_cover_merge_hook_finalize_path():
    text = read_text("references/codex-first-officer-runtime.md")

    assert "codex_finalize_terminal_entity.py" in text
    assert "merge hooks" in text.lower()
    assert "archive" in text.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
