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

    assert "agents/first-officer.md" in text


def test_first_officer_agent_references_shared_core_and_codex_runtime_docs():
    text = read_text("agents/first-officer.md")

    assert "references/first-officer-shared-core.md" in text
    assert "references/code-project-guardrails.md" in text
    assert "references/codex-first-officer-runtime.md" in text


def test_ensign_agent_references_shared_core_and_codex_runtime_docs():
    text = read_text("agents/ensign.md")

    assert "references/ensign-shared-core.md" in text
    assert "references/code-project-guardrails.md" in text
    assert "references/codex-ensign-runtime.md" in text


def test_first_officer_shared_core_covers_latest_template_sections():
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

    assert "## Output Format" in read_text("templates/first-officer.md")
    assert "Output Format" in text
    assert "feedback-to" in text


def test_ensign_shared_core_keeps_stage_report_protocol():
    text = read_text("references/ensign-shared-core.md")

    assert "## Stage Report: {stage_name}" in text
    assert "overwrite" in text.lower()
    assert ".claude/agents/" in text
    assert "Do NOT modify YAML frontmatter" in text


def test_code_project_guardrails_cover_worktrees_and_scaffolding():
    text = read_text("references/code-project-guardrails.md")

    assert ".worktrees/" in text
    assert ".claude/agents/" in text
    assert "git worktree" in text
    assert "scaffolding" in text.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
