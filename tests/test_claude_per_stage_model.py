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


def _assistant_models(jsonl_path: Path) -> dict[str, int]:
    """Count distinct assistant message.model values in a stream-json log."""
    counts: dict[str, int] = {}
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
                counts[model] = counts.get(model, 0) + 1
    return counts


@pytest.mark.live_claude
@pytest.mark.xfail(
    reason="Agent(model='haiku') in teams mode does not propagate to the subagent — "
    "Claude Code platform bug. PR #100 saw 3/30 haiku messages (opus-4-6); "
    "PR #105 saw 0/34 (opus-4-7). See #171.",
    strict=False,
)
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

    # AC-live-propagation: the FO stream-json log folds in every subagent's
    # assistant messages with their stamped runtime model. Under the target
    # precedence (stages.defaults.model: haiku) the dispatched ensign MUST
    # run on a claude-haiku-* model even though the captain is pinned to opus.
    fo_log = t.log_dir / "fo-log.jsonl"
    assert fo_log.is_file(), f"FO log not found at {fo_log}"
    models = _assistant_models(fo_log)
    haiku_models = [m for m in models if m.startswith("claude-haiku-")]
    assert haiku_models, (
        f"No claude-haiku-* assistant messages found in {fo_log}. "
        f"Models seen: {sorted(models.keys())}. "
        "This means the per-stage model did not propagate to the ensign; "
        "the ensign inherited the captain's opus model instead."
    )
    print(f"[OK] haiku assistant messages in FO log: {haiku_models}")
