#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E and static tests for pre-dispatch team health check in the FO.
# ABOUTME: Verifies the FO runs `test -f config.json` before Agent dispatch and checks assembled content for AC1-AC4.

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


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Team health check E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Team Health Check E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "multi-stage-pipeline", "multi-stage-pipeline")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: team health check test")

    t.check_cmd("status script runs without errors",
                ["bash", "multi-stage-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}, this takes ~60-120s) ---")

    abs_workflow = t.test_project_dir / "multi-stage-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/. "
            "Drive them from backlog through all stages to done."
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

    # --- Phase 3: Log analysis — AC5 ---

    print("--- Phase 3: Validation ---")

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_tool_calls(t.log_dir / "tool-calls.json")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")

    print()
    print("[Team Health Check — AC5]")

    # Find Bash tool calls containing 'test -f' and 'config.json'
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

    # Verify health check precedes first Agent dispatch
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
        # No Agent dispatch found — can't verify ordering, but health check was present
        print("  SKIP: no Agent dispatch found — cannot verify ordering (budget may have been exhausted)")

    print()

    # --- Phase 4: Static checks — AC1-AC4 ---

    print("[Static Content Checks — AC1-AC4]")

    assembled = assembled_agent_content(t, "first-officer")

    # AC1: Health check paragraph with test -f verification
    t.check("health check paragraph present",
            "Team health check" in assembled and "test -f" in assembled)

    # AC2: Recovery sequence documented
    t.check("recovery sequence documented",
            bool(re.search(r"TeamDelete.*its own message.*TeamCreate.*its own message",
                           assembled, re.DOTALL)))

    # AC3: Bare mode fallback on failure
    t.check("bare mode fallback on failure",
            "fall back to bare mode" in assembled)

    # AC4: Skipped in bare mode and single-entity mode
    t.check("skipped in bare mode and single-entity mode",
            bool(re.search(r"not in bare mode or single-entity mode", assembled)))

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
