#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test verifying that single-entity mode skips team creation entirely.
# ABOUTME: Asserts TeamCreate is absent from tool calls and Agent dispatch has no team_name.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser, TestRunner, create_test_project,
    git_add_commit, install_agents, run_first_officer, setup_fixture,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Single-entity team skip E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Single-Entity Team Skip E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "spike-no-gate", "spike-workflow")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: single-entity team skip test")

    t.check_cmd("status script runs without errors",
                ["bash", "spike-workflow/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 2: Run the first officer in single-entity mode ---

    print(f"--- Phase 2: Run first officer in single-entity mode ({args.runtime}, ~60-120s) ---")

    abs_workflow = t.test_project_dir / "spike-workflow"
    fo_exit = run_first_officer(
        t,
        (
            f"Process test-entity through the workflow at {abs_workflow}/. "
            "Drive it from backlog through work to done, then stop."
        ),
        agent_id=args.agent,
        extra_args=[
            "--model", args.model,
            "--effort", args.effort,
            "--max-budget-usd", "3.00",
            *extra_args,
        ],
    )

    if fo_exit != 0:
        print("  (may be expected — budget cap)")

    # --- Phase 3: Validate single-entity mode skips team creation ---

    print("--- Phase 3: Validation ---")

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_tool_calls(t.log_dir / "tool-calls.json")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")

    all_tool_calls = log.tool_calls()
    tool_names = [tc["name"] for tc in all_tool_calls]

    print()
    print("[Single-Entity Mode — TeamCreate must be absent]")

    team_create_calls = [tc for tc in all_tool_calls if tc["name"] == "TeamCreate"]
    if not team_create_calls:
        t.pass_("TeamCreate does NOT appear in tool calls")
    else:
        t.fail("TeamCreate does NOT appear in tool calls")
        for tc in team_create_calls:
            print(f"    found TeamCreate: {tc['input']}")

    print()
    print("[Single-Entity Mode — Agent calls must NOT have team_name]")

    agent_calls_with_team = [
        tc for tc in all_tool_calls
        if tc["name"] == "Agent" and tc["input"].get("team_name")
    ]
    if not agent_calls_with_team:
        t.pass_("Agent calls do NOT have team_name parameter")
    else:
        t.fail("Agent calls do NOT have team_name parameter")
        for tc in agent_calls_with_team:
            print(f"    found Agent with team_name={tc['input'].get('team_name')}")

    print()
    print("[Sanity — at least one Agent dispatch occurred]")

    agent_calls = [tc for tc in all_tool_calls if tc["name"] == "Agent"]
    if agent_calls:
        t.pass_(f"at least one Agent dispatch occurred ({len(agent_calls)} total)")
    else:
        t.fail("at least one Agent dispatch occurred (0 found — test inconclusive)")

    # Also check no TeamDelete appeared
    print()
    print("[Single-Entity Mode — TeamDelete must be absent]")

    team_delete_calls = [tc for tc in all_tool_calls if tc["name"] == "TeamDelete"]
    if not team_delete_calls:
        t.pass_("TeamDelete does NOT appear in tool calls")
    else:
        t.fail("TeamDelete does NOT appear in tool calls")

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
