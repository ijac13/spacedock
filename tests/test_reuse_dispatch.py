#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static tests verifying the ensign reuse dispatch behavior in FO reference files.
# ABOUTME: Validates reuse conditions, SendMessage format, fresh overrides, and bare-mode guard.

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import TestRunner, assembled_agent_content


REPO_ROOT = Path(__file__).resolve().parent.parent


def read_ref(name: str) -> str:
    return (REPO_ROOT / "references" / name).read_text()


def shared_core() -> str:
    return read_ref("first-officer-shared-core.md")


def claude_runtime() -> str:
    return read_ref("claude-first-officer-runtime.md")


def assembled_fo() -> str:
    t = TestRunner("reuse dispatch", keep_test_dir=False)
    return assembled_agent_content(t, "first-officer")


# --- AC1: Reuse when consecutive non-worktree stages share context ---

def test_reuse_conditions_present():
    """The 'If the stage is not gated' path lists three reuse conditions."""
    text = shared_core()
    assert "Reuse conditions" in text
    assert "bare mode" in text.lower()
    assert "fresh: true" in text
    assert "worktree" in text.lower()


def test_reuse_sendmessage_format():
    """The reuse path uses SendMessage with stage definition and checklist."""
    text = shared_core()
    assert "SendMessage(" in text
    assert "Stage definition:" in text
    assert "Completion checklist" in text
    assert "entity_file_path" in text


# --- AC2: Fresh dispatch when fresh: true ---

def test_fresh_true_disqualifies_reuse():
    """Reuse condition 2 explicitly checks for fresh: true."""
    text = shared_core()
    assert re.search(r"NOT have.*fresh: true", text)


# --- AC3: Fresh dispatch on worktree boundary change ---

def test_worktree_mode_match_required():
    """Reuse condition 3 requires same worktree mode."""
    text = shared_core()
    assert re.search(r"same.*worktree.*mode", text, re.IGNORECASE)


# --- AC4: Bare mode always dispatches fresh ---

def test_bare_mode_guard():
    """Reuse condition 1 checks for bare mode (teams available)."""
    text = shared_core()
    assert re.search(r"Not in bare mode", text)


# --- AC5: feedback-to keep-alive preserved ---

def test_feedback_to_keepalive_in_fresh_dispatch_path():
    """The fresh dispatch path retains the feedback-to keep-alive check."""
    text = shared_core()
    assert re.search(
        r"If fresh dispatch.*feedback-to.*keep.*alive",
        text,
        re.DOTALL | re.IGNORECASE,
    )


# --- AC6: Gate approval path uses reuse logic ---

def test_gate_approval_references_reuse():
    """The gate approval path references the reuse conditions."""
    text = shared_core()
    assert re.search(
        r"captain approves.*reuse conditions",
        text,
        re.DOTALL | re.IGNORECASE,
    )


# --- AC7: Dispatch step no longer says "Always dispatch fresh" ---

def test_no_always_dispatch_fresh():
    """No reference file contains 'Always dispatch fresh'."""
    text = assembled_fo()
    assert "Always dispatch fresh" not in text


def test_dispatch_step_uses_neutral_language():
    """Dispatch step 8 uses neutral language."""
    text = shared_core()
    assert "Dispatch a worker for the stage" in text
    assert "Dispatch a fresh worker" not in text


# --- Fixture validation ---

def test_reuse_pipeline_fixture_has_consecutive_reusable_stages():
    """The reuse-pipeline fixture has consecutive non-worktree, non-fresh stages."""
    fixture = (REPO_ROOT / "tests" / "fixtures" / "reuse-pipeline" / "README.md").read_text()
    # analysis and implementation are consecutive non-worktree stages without fresh: true
    assert "analysis" in fixture
    assert "implementation" in fixture
    # validation has fresh: true
    assert "fresh: true" in fixture


def test_reuse_pipeline_fixture_has_fresh_stage():
    """The reuse-pipeline fixture has a stage with fresh: true for contrast."""
    fixture = (REPO_ROOT / "tests" / "fixtures" / "reuse-pipeline" / "README.md").read_text()
    assert re.search(r"name:\s*validation", fixture)
    assert "fresh: true" in fixture
    assert "feedback-to: implementation" in fixture


# --- Runtime adapter: SendMessage clarification ---

def test_runtime_sendmessage_clarification():
    """The Claude runtime clarifies that SendMessage is for reuse in the completion path."""
    text = claude_runtime()
    assert "NEVER use SendMessage to dispatch" not in text
    assert re.search(r"SendMessage.*completion path|completion path.*SendMessage", text, re.IGNORECASE)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
