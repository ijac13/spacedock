#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static checks for the runtime live E2E workflow and its operator docs.
# ABOUTME: Verifies PR/manual triggers, CI-E2E approval gating, and the two runtime jobs.

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


def test_runtime_live_e2e_workflow_supports_pr_and_manual_triggers():
    text = read_workflow()

    assert "workflow_dispatch:" in text
    assert "pull_request:" in text
    assert "pr_number:" in text
    assert "required: true" in text


def test_runtime_live_e2e_workflow_has_exactly_two_runtime_jobs():
    text = read_workflow()
    claude_section = section(text, "  claude-live")
    codex_section = section(text, "  codex-live")

    assert "\n  claude-live:\n" in text
    assert "\n  codex-live:\n" in text
    assert "environment:" in claude_section
    assert "name: CI-E2E" in claude_section
    assert "deployment: false" in claude_section
    assert "environment:" in codex_section
    assert "name: CI-E2E-CODEX" in codex_section
    assert "deployment: false" in codex_section
    assert "path classifier" not in text.lower()
    assert "shard" not in text.lower()
    assert "matrix:" not in text


def test_runtime_live_e2e_workflow_preserves_and_uploads_live_test_dirs():
    text = read_workflow()
    claude_section = section(text, "  claude-live")
    codex_section = section(text, "  codex-live")

    for job_section, artifact_name in (
        (claude_section, "runtime-live-e2e-claude-live"),
        (codex_section, "runtime-live-e2e-codex-live"),
    ):
        assert 'KEEP_TEST_DIR: "1"' in job_section
        assert "SPACEDOCK_TEST_TMP_ROOT:" not in job_section
        assert 'echo "SPACEDOCK_TEST_TMP_ROOT=$RUNNER_TEMP/spacedock-live/$GITHUB_JOB" >> "$GITHUB_ENV"' in job_section
        assert 'mkdir -p "$RUNNER_TEMP/spacedock-live/$GITHUB_JOB"' in job_section
        assert "uses: actions/upload-artifact@v4" in job_section
        assert "if: always()" in job_section
        assert f"name: {artifact_name}" in job_section
        assert "path: ${{ runner.temp }}/spacedock-live/${{ github.job }}" in job_section

    assert "Login Codex with API key" in codex_section
    assert "printenv OPENAI_API_KEY | codex login --with-api-key" in codex_section


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
        "unset CLAUDECODE && uv run tests/test_feedback_keepalive.py",
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
        "Trigger source",
    ):
        assert field in text

    assert "github.event.pull_request.number" in text
    assert "inputs.pr_number" in text
    assert "TRIGGER_SOURCE" in text
    assert "DISPATCH_PR_NUMBER" in text
    assert "set -euo pipefail" in text
    assert "continue-on-error" not in text
    assert "|| true" not in text


def test_tests_readme_documents_runtime_live_e2e_workflow():
    text = read_readme()

    assert "runtime-live-e2e.yml" in text
    assert "workflow_dispatch" in text
    assert "pull_request" in text
    assert "CI-E2E" in text
    assert "claude-live" in text
    assert "codex-live" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "OPENAI_API_KEY" in text
    assert "PR number" in text
    assert "Tested workflow SHA" in text
    assert "Current PR head SHA" in text
    assert "same-repo vs fork" in text
    assert "approval/reviewer context" in text
    assert "Trigger source" in text
    assert "job stays red" in text
    assert "pending environment review" in text
