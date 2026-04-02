#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the merge hook guardrail in the first-officer template.
# ABOUTME: Verifies merge hooks fire before local merge, and that no-mods fallback works.

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
    check_merge_outcome, install_agents, run_first_officer, git_add_commit,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Merge hook guardrail E2E test")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner("Merge Hook Guardrail E2E Test")

    # --- Phase 1: Set up test project with merge hook mod ---

    print("--- Phase 1: Set up test project with merge hook mod ---")

    create_test_project(t)
    fixture_dir = t.repo_root / "tests" / "fixtures" / "merge-hook-pipeline"

    # Copy workflow fixture (including _mods/)
    setup_fixture(t, "merge-hook-pipeline", "merge-hook-pipeline")
    install_agents(t)

    git_add_commit(t.test_project_dir, "setup: merge hook guardrail test fixture")

    t.check_cmd("status script runs without errors",
                ["bash", "merge-hook-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 2: Run first officer (with hook mod) ---

    print("--- Phase 2: Run first officer with hook mod (this takes ~60-120s) ---")

    # Save the original test_project_dir and log for the with-hook run
    with_hook_project = t.test_project_dir
    run_first_officer(
        t,
        "Process all tasks through the workflow to completion.",
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "2.00"],
    )

    # --- Phase 3: Validate hook fired ---

    print("--- Phase 3: Validate merge hook execution ---")
    print()
    print("[Merge Hook Execution]")

    check_merge_outcome(
        t,
        with_hook_project,
        "merge-hook-pipeline",
        "merge-hook-entity",
        "spacedock-ensign-merge-hook-entity-work",
        hook_expected=True,
        archive_required=False,
    )

    print()

    # --- Phase 4: Set up and run no-mods fallback test ---

    print("--- Phase 4: Set up no-mods fallback test ---")

    # Create a new test project for the no-mods run
    nomods_project = t.test_dir / "test-no-mods"
    subprocess.run(["git", "init", str(nomods_project)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=nomods_project,
    )

    # Copy workflow fixture WITHOUT _mods
    nomods_pipeline = nomods_project / "merge-hook-pipeline"
    nomods_pipeline.mkdir(parents=True)
    for item in fixture_dir.iterdir():
        if item.is_dir():
            continue  # Skip _mods/ and any other subdirectories
        shutil.copy2(item, nomods_pipeline / item.name)
    status_script = nomods_pipeline / "status"
    if status_script.exists():
        status_script.chmod(status_script.stat().st_mode | 0o111)

    # Install agents via shared helper (temporarily point runner at nomods project)
    orig_project = t.test_project_dir
    t.test_project_dir = nomods_project
    install_agents(t)
    t.test_project_dir = orig_project

    subprocess.run(["git", "add", "-A"], capture_output=True, check=True, cwd=nomods_project)
    subprocess.run(
        ["git", "commit", "-m", "setup: no-mods fallback test fixture"],
        capture_output=True, check=True, cwd=nomods_project,
    )

    print()
    print("[Fixture Setup — No Mods]")

    t.check_cmd("status script runs without errors (no-mods)",
                ["bash", "merge-hook-pipeline/status"], cwd=nomods_project)

    print()
    print("--- Phase 5: Run first officer without mods (this takes ~60-120s) ---")

    # Point runner at the no-mods project for this run
    t.test_project_dir = nomods_project
    nomods_log = "fo-nomods-log.jsonl"
    run_first_officer(
        t,
        "Process all tasks through the workflow to completion.",
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "2.00"],
        log_name=nomods_log,
    )

    # --- Phase 6: Validate no-mods fallback ---

    print("--- Phase 6: Validate no-mods fallback ---")
    print()
    print("[No-Mods Fallback]")

    check_merge_outcome(
        t,
        nomods_project,
        "merge-hook-pipeline",
        "merge-hook-entity",
        "spacedock-ensign-merge-hook-entity-work",
        hook_expected=False,
        archive_required=False,
    )

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
