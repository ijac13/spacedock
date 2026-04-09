#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static content checks for shared Claude/Codex agent contracts and guardrails.

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import TestRunner, assembled_agent_content


REPO_ROOT = Path(__file__).resolve().parent.parent


def read_text(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def section_text(text: str, heading: str, stop_patterns: tuple[str, ...]) -> str:
    lines: list[str] = []
    in_section = False
    for line in text.splitlines():
        if re.match(rf"^{re.escape(heading)}$", line):
            in_section = True
            continue
        if in_section and any(re.match(pattern, line) for pattern in stop_patterns):
            break
        if in_section:
            lines.append(line)
    return "\n".join(lines)


def test_first_officer_skill_reads_references_directly():
    text = read_text("skills/first-officer/SKILL.md")
    assert "first-officer-shared-core.md" in text
    assert "code-project-guardrails.md" in text
    assert "claude-first-officer-runtime.md" in text
    assert "${CLAUDE_SKILL_DIR}" in text


def test_agent_entry_points_use_skill_preloading():
    fo_text = read_text("agents/first-officer.md")
    assert 'skills:' in fo_text
    assert 'spacedock:first-officer' in fo_text
    assert 'DISPATCHER' in fo_text

    ensign_text = read_text("agents/ensign.md")
    assert 'skills:' in ensign_text
    assert 'spacedock:ensign' in ensign_text


def test_first_officer_shared_core_covers_all_behavioral_sections():
    text = read_text("references/first-officer-shared-core.md")

    for heading in [
        "## Startup",
        "## Status Viewer",
        "## Single-Entity Mode",
        "## Working Directory",
        "## Dispatch",
        "## Completion and Gates",
        "## Feedback Rejection Flow",
        "## Merge and Cleanup",
        "## State Management",
        "## Mod Hook Convention",
        "## Clarification and Communication",
        "## Issue Filing",
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
    assert "codex_finalize_terminal_entity.py" not in text
    assert "merge hooks" in text.lower()
    assert "archive" in text.lower()
    assert "fork_context=false" in text


def test_assembled_claude_first_officer_has_gate_guardrails():
    t = TestRunner("agent content", keep_test_dir=False)
    text = assembled_agent_content(t, "first-officer")
    assert "self-approve" in text.lower()
    assert re.search(r"only the captain can approve|never self-approve", text, re.IGNORECASE)
    assert "Gate review:" in text or "gate review" in text.lower()


def test_assembled_claude_first_officer_has_rejection_flow_guardrails():
    t = TestRunner("agent content", keep_test_dir=False)
    text = assembled_agent_content(t, "first-officer")
    assert "Feedback Rejection Flow" in text
    assert "feedback-to" in text


def test_assembled_claude_first_officer_has_merge_hook_guardrails():
    t = TestRunner("agent content", keep_test_dir=False)
    text = assembled_agent_content(t, "first-officer")

    merge_section = section_text(text, "## Merge and Cleanup", (r"^## ",))
    gate_section = section_text(text, "## Completion and Gates", (r"^## Feedback", r"^## Merge"))

    assert (
        "merge hooks before any local merge" in merge_section.lower()
        or "run registered merge hooks" in merge_section.lower()
    )
    assert "merge hook" in merge_section.lower()
    assert "registered" in merge_section.lower() or "hook" in merge_section.lower()
    assert re.search(r"before any local merge|before.*local merge", merge_section, re.IGNORECASE)
    assert re.search(r"do not.*local.merge|not local-merge", merge_section, re.IGNORECASE)
    assert re.search(r"terminal.*merge|merge handling", text, re.IGNORECASE)
    assert not re.search(r"Run merge hooks.*_mods", gate_section, re.IGNORECASE)
    assert re.search(r"no merge hook.*default local merge|If no merge", text, re.IGNORECASE)


def test_assembled_claude_first_officer_has_teamcreate_failure_recovery():
    t = TestRunner("agent content", keep_test_dir=False)
    assembled = assembled_agent_content(t, "first-officer")

    # AC1: "Already leading team" recovery path
    assert "Already leading team" in assembled
    assert re.search(r"TeamDelete.*its own message", assembled)
    assert re.search(r"TeamCreate.*subsequent message", assembled)

    # AC2: Bare mode fallback for non-"Already leading" errors
    assert re.search(r"Other errors.*bare mode", assembled, re.IGNORECASE | re.DOTALL)

    # AC3: Block agent dispatch while team state is uncertain
    assert re.search(r"Block all Agent dispatch", assembled)
    assert re.search(r"never dispatch.*while team", assembled, re.IGNORECASE)

    # AC4: Sequencing rule in Dispatch Adapter
    assert re.search(
        r"Sequencing rule.*Team lifecycle.*Agent.*NEVER.*same tool-call message",
        assembled, re.IGNORECASE | re.DOTALL,
    )


def test_assembled_claude_first_officer_has_team_health_check():
    t = TestRunner("agent content", keep_test_dir=False)
    assembled = assembled_agent_content(t, "first-officer")

    # AC1: Health check paragraph with test -f verification
    assert "Team health check" in assembled
    assert "test -f ~/.claude/teams/" in assembled

    # AC2: Recovery sequence — TeamDelete alone, then TeamCreate alone, then dispatch
    assert re.search(
        r"TeamDelete.*its own message.*TeamCreate.*subsequent message",
        assembled, re.DOTALL,
    )

    # AC3: Bare mode fallback if TeamCreate fails during recovery
    assert "fall back to bare mode" in assembled

    # AC4: Health check skipped in bare mode and single-entity mode
    assert re.search(r"not in bare mode or single-entity mode", assembled)


def test_assembled_claude_first_officer_has_dispatch_idle_guardrail():
    t = TestRunner("agent content", keep_test_dir=False)
    text = assembled_agent_content(t, "first-officer")

    # The guardrail heading must be present
    assert "DISPATCH IDLE GUARDRAIL" in text

    # Idle is normal between-turn state
    assert "idle" in text.lower() and "between-turn state" in text.lower()

    # Three explicit shutdown conditions
    assert "completion message" in text.lower()
    assert "captain explicitly requests shutdown" in text.lower()
    assert "transitioning the entity to a new stage" in text.lower()

    # Never interpret idle as stuck
    assert re.search(r"never interpret idle.*stuck.*unresponsive", text, re.IGNORECASE)


def test_assembled_claude_ensign_has_captain_communication():
    t = TestRunner("agent content", keep_test_dir=False)
    text = assembled_agent_content(t, "ensign")

    # Captain Communication section exists
    assert "## Captain Communication" in text

    # Direct text output for captain interaction
    assert "direct text output" in text.lower()

    # SendMessage scoped to agent-to-agent use
    assert re.search(
        r"SendMessage.*only.*agent-to-agent", text, re.IGNORECASE | re.DOTALL
    )

    # Captain switches to ensign via Shift+Up/Down
    assert "Shift+Up/Down" in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
