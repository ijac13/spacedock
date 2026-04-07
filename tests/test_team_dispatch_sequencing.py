#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E and static tests for team lifecycle / agent dispatch sequencing in the FO.
# ABOUTME: Verifies no assistant message mixes TeamCreate/TeamDelete with Agent dispatch calls.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser, TestRunner, assembled_agent_content, create_test_project,
    git_add_commit, install_agents, run_first_officer, setup_fixture,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
TEAM_LIFECYCLE = {"TeamCreate", "TeamDelete"}


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Team dispatch sequencing E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Team Dispatch Sequencing E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "gated-pipeline", "gated-pipeline")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: team dispatch sequencing test")

    t.check_cmd("status script runs without errors",
                ["bash", "gated-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}, this takes ~60-120s) ---")

    abs_workflow = t.test_project_dir / "gated-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/. "
            "Drive them from backlog through work to the gate. "
            "When you reach the gate, present the gate review and wait."
        ),
        agent_id=args.agent,
        extra_args=[
            "--model", args.model,
            "--effort", args.effort,
            "--max-budget-usd", "2.00",
            *extra_args,
        ],
    )

    if fo_exit != 0:
        print("  (may be expected — budget cap or gate hold)")

    # --- Phase 3: Validate sequencing invariant ---

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
        has_team = bool(tool_names & TEAM_LIFECYCLE)
        has_agent = "Agent" in tool_names
        if has_team and has_agent:
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

    # AC1: "Already leading team" recovery path documented
    t.check("failure recovery documents Already-leading-team path",
            "Already leading team" in assembled)

    # AC2: Bare mode fallback for other errors
    t.check("failure recovery documents bare mode fallback",
            bool(re.search(r"Other errors.*bare mode", assembled, re.IGNORECASE | re.DOTALL)))

    # AC3: Block agent dispatch during uncertain team state
    t.check("blocks agent dispatch during uncertain team state",
            bool(re.search(r"Block all Agent dispatch", assembled)))

    # AC4: Sequencing rule in Dispatch Adapter
    t.check("sequencing rule in dispatch adapter",
            bool(re.search(
                r"NEVER appear in the same tool-call message",
                assembled, re.IGNORECASE,
            )))

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
