#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the checklist protocol in the first-officer template.
# ABOUTME: Commissions a workflow, runs the first officer, validates ensign checklist compliance.

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lib import (
    TestRunner, LogParser, create_test_project, run_commission,
    run_first_officer, git_add_commit, extract_stats,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Checklist protocol E2E test")
    parser.add_argument("--from-snapshot", default=None, help="Use a snapshot dir instead of commissioning")
    parser.add_argument("--model", default="opus", help="Model to use (default: opus)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner("Checklist Protocol E2E Test")

    if args.from_snapshot:
        # --- Snapshot mode: copy snapshot into test dir ---
        print("--- Phase 1: Loading from snapshot (skipping commission) ---")
        snapshot = Path(args.from_snapshot)
        # Copy snapshot contents into test dir
        shutil.copytree(snapshot, t.test_dir, dirs_exist_ok=True)
        t.test_project_dir = t.test_dir / "test-project"

        # Verify snapshot has the expected structure
        workflow_dir = None
        for d in t.test_project_dir.iterdir():
            if d.is_dir() and (d / "README.md").is_file() and d.name != ".claude" and d.name != ".git":
                workflow_dir = d
                break

        if workflow_dir is None:
            t.fail("snapshot contains a workflow directory")
            t.results()
            return

        # Add acceptance criteria to first entity (matching non-snapshot behavior)
        for entity_file in sorted(workflow_dir.glob("*.md")):
            if entity_file.name == "README.md":
                continue
            with open(entity_file, "a") as f:
                f.write("""

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
""")
            git_add_commit(t.test_project_dir, "setup: add acceptance criteria to entity")
            break

        t.pass_("loaded snapshot")
        print()
    else:
        # --- Phase 1: Commission a test workflow ---
        print("--- Phase 1: Commission test workflow (this takes ~30-60s) ---")

        create_test_project(t)

        prompt = """/spacedock:commission

All inputs for this workflow:
- Mission: Track tasks through stages
- Entity: A task
- Stages: backlog → work → done
- Approval gates: none
- Seed entities:
  1. test-checklist — Verify checklist protocol works (score: 25/25)
- Location: ./checklist-test/

Skip interactive questions and confirmation — use these inputs directly. Make reasonable assumptions for anything not specified. Do NOT run the pilot phase — just generate the files and stop."""

        extra = list(extra_args)
        extra.extend(["--model", args.model, "--effort", args.effort])
        run_commission(t, prompt, extra_args=extra)

        print("[Commission Output]")
        entity_file = t.test_project_dir / "checklist-test" / "test-checklist.md"
        if not entity_file.is_file():
            t.fail("commission produced test-checklist.md")
            print("  FATAL: Cannot proceed without commissioned workflow. Aborting.")
            t.results()
            return
        else:
            t.pass_("commission produced test-checklist.md")

        fo_file = t.test_project_dir / ".claude" / "agents" / "first-officer.md"
        if not fo_file.is_file():
            t.fail("commission produced first-officer.md")
            print("  FATAL: Cannot proceed without first-officer agent. Aborting.")
            t.results()
            return
        else:
            t.pass_("commission produced first-officer.md")

        # Add acceptance criteria to the test entity
        with open(entity_file, "a") as f:
            f.write("""

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
""")

        # Commit so the first officer has a clean working tree
        git_add_commit(t.test_project_dir, "commission: initial workflow with acceptance criteria")
        print()

    # --- Phase 2: Run the first officer ---

    print("--- Phase 2: Run first officer (this takes ~60-120s) ---")

    extra_fo = ["--max-budget-usd", "2.00"]
    extra_fo.extend(["--model", args.model, "--effort", args.effort])
    extra_fo.extend(extra_args)

    run_first_officer(
        t,
        "Process all entities through the workflow. Process one entity through one stage, then stop.",
        extra_args=extra_fo,
    )

    # --- Phase 3: Validate from the stream-json log ---

    print("--- Phase 3: Validation ---")

    log = LogParser(t.log_dir / "fo-log.jsonl")

    # Write extracted data for debug inspection
    log.write_agent_prompt(t.log_dir / "agent-prompt.txt")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")

    agent_prompt = log.agent_prompt()
    fo_text = "\n".join(log.fo_texts())

    print()
    print("[Ensign Dispatch Prompt]")

    # Check 1: Dispatch prompt contains Completion checklist section
    t.check("dispatch prompt contains Completion checklist section",
            bool(re.search(r"Completion checklist|completion checklist", agent_prompt, re.IGNORECASE)))

    # Check 2: Dispatch prompt contains DONE/SKIPPED/FAILED instructions
    t.check("dispatch prompt has DONE/SKIPPED/FAILED instructions",
            bool(re.search(r"DONE.*SKIPPED.*FAILED|Mark each.*DONE", agent_prompt, re.IGNORECASE)))

    # Check 3: Dispatch prompt includes entity acceptance criteria items
    t.check("dispatch prompt includes entity acceptance criteria",
            bool(re.search(r"hello|UTF-8", agent_prompt, re.IGNORECASE)))

    # Check 4: Dispatch prompt includes stage requirement items
    t.check("dispatch prompt includes stage requirement items",
            bool(re.search(r"deliverable|summary", agent_prompt, re.IGNORECASE)))

    print()
    print("[First Officer Checklist Review]")

    # Check 5: First officer performed checklist review
    t.check("first officer performed checklist review",
            bool(re.search(r"checklist review|checklist.*complete|all.*items.*DONE|items reported",
                           fo_text, re.IGNORECASE)))

    # Check 6: First officer mentions DONE/SKIPPED/FAILED
    t.check("first officer review references item statuses",
            bool(re.search(r"DONE|SKIPPED|FAILED", fo_text, re.IGNORECASE)))

    # Check 7: Dispatch prompt has structured completion message template
    t.check("dispatch prompt has structured completion message template",
            bool(re.search(r"### Checklist|### Summary", agent_prompt, re.IGNORECASE)))

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
