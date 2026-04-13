#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static checks for the manual runtime live E2E workflow and its operator docs.
# ABOUTME: Verifies the workflow stays manual, split into exactly two runtime jobs, and documents provenance/secrets.

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "runtime-live-e2e.yml"
README_PATH = REPO_ROOT / "tests" / "README.md"


def read_workflow() -> str:
    return WORKFLOW_PATH.read_text()


def read_readme() -> str:
    return README_PATH.read_text()


def section(text: str, heading: str) -> str:
    marker = f"{heading}:"
    start = text.index(marker)
    lines = []
    for line in text[start:].splitlines()[1:]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        lines.append(line)
    return "\n".join(lines)


def test_runtime_live_e2e_workflow_exists_and_is_manual_only():
    text = read_workflow()

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "pr_number:" in text
    assert "required: true" in text


def test_runtime_live_e2e_workflow_has_exactly_two_runtime_jobs():
    text = read_workflow()

    assert "\n  claude-live:\n" in text
    assert "\n  codex-live:\n" in text
    assert "path classifier" not in text.lower()
    assert "shard" not in text.lower()
    assert "matrix:" not in text


def test_runtime_live_e2e_workflow_scopes_secrets_to_the_matching_job():
    text = read_workflow()
    claude_section = section(text, "  claude-live")
    codex_section = section(text, "  codex-live")

    assert "ANTHROPIC_API_KEY" in claude_section
    assert "OPENAI_API_KEY" not in claude_section
    assert "OPENAI_API_KEY" in codex_section
    assert "ANTHROPIC_API_KEY" not in codex_section
    assert "is required for claude-live" in claude_section
    assert "is required for codex-live" in codex_section


def test_runtime_live_e2e_workflow_lists_the_expected_commands_and_provenance_fields():
    text = read_workflow()

    for command in (
        "unset CLAUDECODE && uv run tests/test_gate_guardrail.py --runtime claude",
        "unset CLAUDECODE && uv run tests/test_rejection_flow.py --runtime claude",
        "unset CLAUDECODE && uv run tests/test_scaffolding_guardrail.py",
        "unset CLAUDECODE && uv run tests/test_feedback_keepalive.py",
        "unset CLAUDECODE && uv run tests/test_dispatch_completion_signal.py",
        "unset CLAUDECODE && uv run tests/test_merge_hook_guardrail.py --runtime claude",
        "unset CLAUDECODE && uv run tests/test_push_main_before_pr.py",
        "unset CLAUDECODE && uv run tests/test_rebase_branch_before_push.py",
        "uv run tests/test_gate_guardrail.py --runtime codex",
        "uv run tests/test_rejection_flow.py --runtime codex",
        "uv run tests/test_merge_hook_guardrail.py --runtime codex",
    ):
        assert command in text

    for field in (
        "PR number",
        "Tested workflow SHA",
        "Current PR head SHA",
        "same-repo",
        "fork",
        "Approval context",
    ):
        assert field in text

    assert "set -euo pipefail" in text
    assert "continue-on-error" not in text
    assert "|| true" not in text


def test_tests_readme_documents_runtime_live_e2e_workflow():
    text = read_readme()

    assert "runtime-live-e2e.yml" in text
    assert "workflow_dispatch" in text
    assert "after the PR has been approved" in text
    assert "claude-live" in text
    assert "codex-live" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "OPENAI_API_KEY" in text
    assert "PR number" in text
    assert "Tested workflow SHA" in text
    assert "Current PR head SHA" in text
    assert "same-repo vs fork" in text
    assert "approval/reviewer context" in text
    assert "job stays red" in text
