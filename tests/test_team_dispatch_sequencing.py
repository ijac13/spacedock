# ABOUTME: E2E and static tests for team lifecycle / agent dispatch sequencing in the FO.
# ABOUTME: Verifies no assistant message mixes TeamCreate/TeamDelete with Agent dispatch calls.

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    assembled_agent_content,
    git_add_commit,
    install_agents,
    run_first_officer,
    setup_fixture,
)


TEAM_LIFECYCLE = {"TeamCreate", "TeamDelete"}


@pytest.mark.live_claude
def test_team_dispatch_sequencing(test_project, model, effort):
    """No assistant message mixes TeamCreate/TeamDelete with Agent dispatch."""
    t = test_project

    print("--- Phase 1: Set up test project from fixture ---")
    setup_fixture(t, "gated-pipeline", "gated-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: team dispatch sequencing test")
    t.check_cmd("status script runs without errors",
                ["bash", "gated-pipeline/status"], cwd=t.test_project_dir)
    print()

    print("--- Phase 2: Run first officer (claude, this takes ~60-120s) ---")
    abs_workflow = t.test_project_dir / "gated-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/. "
            "Drive them from backlog through work to the gate. "
            "When you reach the gate, present the gate review and wait."
        ),
        agent_id="spacedock:first-officer",
        extra_args=[
            "--model", model,
            "--effort", effort,
            "--max-budget-usd", "2.00",
        ],
    )
    if fo_exit != 0:
        print("  (may be expected — budget cap or gate hold)")

    print("--- Phase 3: Validation ---")
    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_tool_calls(t.log_dir / "tool-calls.json")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")

    print()
    print("[Sequencing Invariant — AC5]")
    violations = []
    for msg in log.assistant_messages():
        tool_names = {
            block["name"]
            for block in msg["message"].get("content", [])
            if block.get("type") == "tool_use"
        }
        if (tool_names & TEAM_LIFECYCLE) and "Agent" in tool_names:
            violations.append(sorted(tool_names))

    if not violations:
        t.pass_("no assistant message mixes team lifecycle and Agent dispatch")
    else:
        t.fail("no assistant message mixes team lifecycle and Agent dispatch")
        for v in violations:
            print(f"    violation: {v}")

    print()
    print("[Static Template Checks — AC1-AC4]")
    assembled = assembled_agent_content(t, "first-officer")
    t.check("failure recovery documents Already-leading-team path",
            "Already leading team" in assembled)
    t.check("failure recovery documents bare mode fallback",
            bool(re.search(r"Other errors.*bare mode", assembled, re.IGNORECASE | re.DOTALL)))
    t.check("blocks agent dispatch during uncertain team state",
            bool(re.search(r"Block all Agent dispatch", assembled)))
    t.check("sequencing rule in dispatch adapter",
            bool(re.search(
                r"NEVER appear in the same tool-call message",
                assembled, re.IGNORECASE,
            )))

    t.finish()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
