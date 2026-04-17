# ABOUTME: Live E2E test for per-stage model propagation (#157).
# ABOUTME: Verifies stages.defaults.model: haiku reaches the dispatched ensign's runtime model.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    assistant_model_equals,
    git_add_commit,
    install_agents,
    run_first_officer_streaming,
    setup_fixture,
    tool_use_matches,
)


def _agent_name(entry: dict) -> str:
    message = entry.get("message", {})
    for block in message.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Agent":
            return (block.get("input", {}) or {}).get("name", "")
    return ""


@pytest.mark.live_claude
@pytest.mark.xfail(
    reason="Agent(model='haiku') in teams mode does not propagate to the subagent — "
    "Claude Code platform bug. PR #100 saw 3/30 haiku messages (opus-4-6); "
    "PR #105 saw 0/34 (opus-4-7). See #171.",
    strict=False,
)
def test_per_stage_model_haiku_propagates(test_project, model, effort):
    """stages.defaults.model: haiku must stamp the dispatched ensign with claude-haiku-*.

    Streaming-watcher variant: fail-fast within 240s after the ensign dispatches
    if no haiku message arrives. xfail stays until #171 is fixed.
    """
    t = test_project

    print("--- Phase 1: Set up test project (workflow nested in subdir) ---")
    setup_fixture(t, "per-stage-model", "per-stage-model")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: per-stage-model fixture")
    print()

    print("--- Phase 2: Run first officer with streaming watcher ---")
    abs_workflow = t.test_project_dir / "per-stage-model"
    prompt = (
        f"Process all tasks through the workflow at {abs_workflow}/ to terminal "
        "completion. Drive every dispatchable task through its stages until the "
        "entity reaches the done stage. Stop once the entity is archived."
    )

    with run_first_officer_streaming(
        t,
        prompt,
        agent_id="spacedock:first-officer",
        extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
    ) as w:
        w.expect(
            lambda e: tool_use_matches(e, "Agent") and "ensign" in _agent_name(e).lower(),
            timeout_s=180,
            label="ensign Agent() dispatched",
        )
        print("[OK] ensign Agent() dispatched")

        # The hypothesis under test: the dispatched ensign stamps haiku on its
        # assistant messages. If no haiku message arrives within 240s after
        # dispatch the xfail surfaces fast instead of at the 600s cap.
        haiku_entry = w.expect(
            lambda e: assistant_model_equals(e, "claude-haiku-"),
            timeout_s=240,
            label="haiku assistant message observed",
        )
        print(f"[OK] haiku assistant message: {haiku_entry['message'].get('model')}")

        w.expect_exit(timeout_s=300)
