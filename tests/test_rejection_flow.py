#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the validation rejection flow in the first-officer template.
# ABOUTME: Verifies that a REJECTED validation triggers implementer dispatch via the relay protocol.

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit,
    file_contains,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Rejection flow E2E test")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner("Rejection Flow E2E Test")

    # --- Phase 1: Set up test project from static fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    fixture_dir = t.repo_root / "tests" / "fixtures" / "rejection-flow"
    setup_fixture(t, "rejection-flow", "rejection-pipeline")
    install_agents(t, include_ensign=True)

    # Copy the buggy implementation and tests into the repo root
    shutil.copy2(fixture_dir / "math_ops.py", t.test_project_dir)
    tests_dir = t.test_project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    shutil.copy2(fixture_dir / "tests" / "test_add.py", tests_dir)

    git_add_commit(t.test_project_dir, "setup: rejection flow fixture with buggy implementation")

    print()
    print("[Fixture Setup]")

    fo_path = t.test_project_dir / ".claude" / "agents" / "first-officer.md"

    t.check("generated first-officer contains feedback rejection flow",
            file_contains(fo_path, r"Feedback Rejection Flow"))
    if not file_contains(fo_path, r"Feedback Rejection Flow"):
        print("  FATAL: Rejection flow section missing from generated agent. Aborting.")
        t.results()
        return

    t.check("generated first-officer has feedback-to dispatch logic",
            file_contains(fo_path, r"feedback-to"))

    t.check_cmd("status script runs without errors",
                ["python3", "rejection-pipeline/status"], cwd=t.test_project_dir)

    status_result = subprocess.run(
        ["python3", "rejection-pipeline/status", "--next"],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "buggy-add-task" in status_result.stdout)

    print()

    # --- Phase 2: Run the first officer ---

    print("--- Phase 2: Run first officer (this takes ~120-300s) ---")

    fo_exit = run_first_officer(
        t,
        "Process all tasks through the workflow. When you encounter a gate review where the reviewer recommends REJECTED, approve the REJECTED verdict so the rejection flow proceeds.",
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "5.00"],
    )

    if fo_exit != 0:
        print("  (may be expected — budget cap or gate hold)")

    # --- Phase 3: Validate ---

    print("--- Phase 3: Validation ---")

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_agent_calls(t.log_dir / "agent-calls.txt")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")

    agent_calls = log.agent_calls()
    fo_text = "\n".join(log.fo_texts())

    print()
    print("[Rejection Flow Behavior]")

    # Check 1: FO dispatched an ensign for the validation stage
    ensign_calls = [c for c in agent_calls if c["subagent_type"] == "spacedock:ensign"]
    t.check("FO dispatched an ensign for validation stage", len(ensign_calls) > 0)

    # Check 2: The reviewer's stage report contains a REJECTED recommendation
    found_rejected = False

    # Check entity file on main
    entity_main = t.test_project_dir / "rejection-pipeline" / "buggy-add-task.md"
    if entity_main.is_file() and re.search(r"REJECTED", entity_main.read_text(), re.IGNORECASE):
        found_rejected = True

    # Check entity files in any worktree
    worktrees_dir = t.test_project_dir / ".worktrees"
    if worktrees_dir.is_dir():
        for wt in worktrees_dir.iterdir():
            wt_entity = wt / "rejection-pipeline" / "buggy-add-task.md"
            if wt_entity.is_file() and re.search(r"REJECTED", wt_entity.read_text(), re.IGNORECASE):
                found_rejected = True

    # Check FO text output
    if re.search(r"REJECTED", fo_text, re.IGNORECASE):
        found_rejected = True

    t.check("reviewer stage report contains REJECTED recommendation", found_rejected)

    # Check 3: FO dispatched multiple ensigns (implementation + validation + fix after rejection)
    ensign_count = len(ensign_calls)
    if ensign_count >= 3:
        t.pass_(f"FO dispatched ensign for fix after rejection ({ensign_count} total ensign dispatches)")
    elif ensign_count >= 2:
        t.fail(f"FO dispatched ensign for fix after rejection (only {ensign_count} ensign dispatches — missing fix dispatch)")
    else:
        t.fail(f"FO dispatched ensign for fix after rejection (only {ensign_count} ensign dispatches)")

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
