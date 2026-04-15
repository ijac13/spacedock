#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static checks for the GitHub Actions workflow that runs offline CI on pull requests.
# ABOUTME: Verifies the workflow uses the stable repo-level pytest entrypoint with no skip-list policy.

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci-static.yml"


def read_workflow() -> str:
    return WORKFLOW_PATH.read_text()


def test_ci_static_workflow_targets_pull_requests_to_main():
    text = read_workflow()

    assert "pull_request:" in text
    assert "branches:" in text
    assert "- main" in text


def test_ci_static_workflow_uses_stable_offline_suite_entrypoint():
    text = read_workflow()

    assert "run: make test-static" in text
    assert "pytest tests/ --ignore=tests/fixtures" not in text
    assert "run_codex_first_officer" not in text
    assert "run_first_officer" not in text
    assert "InteractiveSession" not in text


def test_ci_static_workflow_has_no_allowlist_or_known_failure_suppression():
    text = read_workflow()

    assert "continue-on-error" not in text
    assert "known failure" not in text.lower()
    assert "allowlist" not in text.lower()
    assert "skip list" not in text.lower()
