# ABOUTME: Live E2E test for per-stage model propagation (#157).
# ABOUTME: Verifies stages.defaults.model: haiku reaches the dispatched ensign's runtime model.

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    git_add_commit,
    install_agents,
    run_first_officer,
    setup_fixture,
)


def _latest_ensign_jsonl(project_dir: Path) -> Path | None:
    """Find the most recent ensign jsonl under ~/.claude/projects/ for this project."""
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.is_dir():
        return None
    project_slug = str(project_dir.resolve()).replace("/", "-")
    if not project_slug.startswith("-"):
        project_slug = "-" + project_slug

    best: Path | None = None
    best_mtime = 0.0
    for session_dir in claude_dir.glob(f"{project_slug}*"):
        if not session_dir.is_dir():
            continue
        for subagents_dir in session_dir.rglob("subagents"):
            if not subagents_dir.is_dir():
                continue
            for meta_path in subagents_dir.glob("agent-*.meta.json"):
                try:
                    meta = json.loads(meta_path.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                agent_type = meta.get("agentType", "")
                if "ensign" not in agent_type and "general-purpose" not in agent_type:
                    continue
                jsonl_path = meta_path.with_suffix("").with_suffix(".jsonl")
                if not jsonl_path.is_file():
                    continue
                mtime = jsonl_path.stat().st_mtime
                if mtime > best_mtime:
                    best_mtime = mtime
                    best = jsonl_path
    return best


def _first_assistant_model(jsonl_path: Path) -> str | None:
    """Return the first non-empty assistant message.model string in the jsonl."""
    with jsonl_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            msg = entry.get("message", {})
            if not isinstance(msg, dict):
                continue
            model = msg.get("model")
            if model:
                return model
    return None


@pytest.mark.live_claude
def test_per_stage_model_haiku_propagates(test_project, effort):
    """stages.defaults.model: haiku must stamp the dispatched ensign with claude-haiku-*."""
    t = test_project

    print("--- Phase 1: Set up test project (workflow nested in subdir) ---")
    # Workflow lives at a subdirectory of project_root for cleanest isolation.
    setup_fixture(t, "per-stage-model", "per-stage-model")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: per-stage-model fixture")
    print()

    print("--- Phase 2: Run first officer ---")
    abs_workflow = t.test_project_dir / "per-stage-model"
    # Pin captain to opus so any opus-inheritance bug would be observable.
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/ to terminal "
            "completion. Drive every dispatchable task through its stages until the "
            "entity reaches the done stage. Stop once the entity is archived."
        ),
        agent_id="spacedock:first-officer",
        extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"],
    )
    if fo_exit != 0:
        print(f"  (first officer exit code {fo_exit})")

    print()
    print("--- Phase 3: Validation ---")

    # Confirm the FO dispatched at least one ensign.
    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_agent_calls(t.log_dir / "agent-calls.txt")
    agent_calls = log.agent_calls()
    ensign_calls = [
        c for c in agent_calls
        if "ensign" in c.get("subagent_type", "")
        or "ensign" in c.get("name", "")
    ]
    assert len(ensign_calls) > 0, (
        "FO dispatched no ensigns; cannot verify per-stage model propagation."
    )

    # AC-live-propagation: parse the ensign jsonl and assert message.model starts
    # with claude-haiku-.
    ensign_jsonl = _latest_ensign_jsonl(t.test_project_dir)
    assert ensign_jsonl is not None, (
        "No ensign jsonl found under ~/.claude/projects/*/subagents/."
    )

    model = _first_assistant_model(ensign_jsonl)
    assert model is not None, (
        f"No assistant message.model found in {ensign_jsonl}."
    )
    assert model.startswith("claude-haiku-"), (
        f"Ensign ran on model {model!r}; expected a claude-haiku-* model per "
        f"stages.defaults.model: haiku. Jsonl: {ensign_jsonl}"
    )

    print(f"[OK] ensign runtime model: {model}")
