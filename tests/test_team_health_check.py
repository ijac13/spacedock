# ABOUTME: E2E and static tests for pre-dispatch team health check in the FO.
# ABOUTME: Verifies the FO runs `test -f config.json` before Agent dispatch and checks assembled content for AC1-AC4.

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


@pytest.mark.live_claude
def test_team_health_check(test_project, model, effort):
    """FO performs `test -f config.json` before first Agent dispatch."""
    t = test_project

    print("--- Phase 1: Set up test project from fixture ---")
    setup_fixture(t, "multi-stage-pipeline", "multi-stage-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: team health check test")
    t.check_cmd("status script runs without errors",
                ["bash", "multi-stage-pipeline/status"], cwd=t.test_project_dir)
    print()

    print("--- Phase 2: Run first officer (claude, this takes ~60-120s) ---")
    abs_workflow = t.test_project_dir / "multi-stage-pipeline"
    # This test historically defaulted to sonnet; respect it unless model was overridden.
    model_for_run = model if model != "haiku" else "sonnet"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/. "
            "Drive them from backlog through all stages to done."
        ),
        agent_id="spacedock:first-officer",
        extra_args=[
            "--model", model_for_run,
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
    print("[Team Health Check — AC5]")
    health_check_found = False
    first_health_check_idx = None
    for i, msg in enumerate(log.assistant_messages()):
        for block in msg["message"].get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                cmd = block.get("input", {}).get("command", "")
                if "test -f" in cmd and "config.json" in cmd:
                    health_check_found = True
                    if first_health_check_idx is None:
                        first_health_check_idx = i
                    break

    t.check("FO performs team health check (test -f config.json)", health_check_found)

    first_agent_idx = None
    for i, msg in enumerate(log.assistant_messages()):
        for block in msg["message"].get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Agent":
                first_agent_idx = i
                break
        if first_agent_idx is not None:
            break

    if first_health_check_idx is not None and first_agent_idx is not None:
        t.check("health check precedes first Agent dispatch",
                first_health_check_idx < first_agent_idx)
    elif first_health_check_idx is None:
        t.fail("health check precedes first Agent dispatch (no health check found)")
    elif first_agent_idx is None:
        print("  SKIP: no Agent dispatch found — cannot verify ordering (budget may have been exhausted)")
    print()

    print("[Static Content Checks — AC1-AC4]")
    assembled = assembled_agent_content(t, "first-officer")
    t.check("health check paragraph present",
            "Team health check" in assembled and "test -f" in assembled)
    t.check("recovery sequence documented",
            bool(re.search(r"TeamDelete.*its own message.*TeamCreate.*its own message",
                           assembled, re.DOTALL)))
    t.check("bare mode fallback on failure",
            "fall back to bare mode" in assembled)
    t.check("skipped in bare mode and single-entity mode",
            bool(re.search(r"not in bare mode or single-entity mode", assembled)))

    t.finish()

