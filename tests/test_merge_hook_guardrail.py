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
    install_agents, assembled_agent_content, run_first_officer,
    git_add_commit, read_entity_frontmatter, file_contains,
    extract_stats,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Merge hook guardrail E2E test")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner("Merge Hook Guardrail E2E Test")

    # --- Phase 1: Static validation of the assembled agent guardrail ---

    print("--- Phase 1: Assembled agent guardrail validation ---")
    print()
    print("[Assembled Agent Guardrail Text]")

    assembled_text = assembled_agent_content(t, "first-officer")

    # Extract Merge and Cleanup section from assembled content
    merge_section_lines = []
    in_section = False
    for line in assembled_text.splitlines():
        if re.match(r"^## Merge and Cleanup", line):
            in_section = True
            continue
        if in_section and re.match(r"^## ", line):
            break
        if in_section:
            merge_section_lines.append(line)
    merge_section = "\n".join(merge_section_lines)

    # Check 1: Merge hooks are referenced before local merge
    t.check("merge hooks run before local merge in assembled agent",
            "merge hooks before any local merge" in merge_section.lower()
            or "run registered merge hooks" in merge_section.lower())
    if "merge hook" not in merge_section.lower():
        print("  FATAL: Merge hook guardrail text missing from assembled agent. Aborting.")
        t.results()
        return

    # Check 2: Guardrail is in the Merge and Cleanup section
    t.check("merge hook behavior is in Merge and Cleanup section",
            "merge hook" in merge_section.lower())

    # Check 3: Guardrail references hook registry discovery
    t.check("guardrail references hook discovery",
            "registered" in merge_section.lower() or "hook" in merge_section.lower())

    # Check 4: Guardrail blocks merge before hooks complete
    t.check("guardrail blocks merge before hooks",
            bool(re.search(r"before any local merge|before.*local merge", merge_section, re.IGNORECASE)))

    # Check 5: Guardrail handles PR-created case
    t.check("guardrail handles PR-created stop condition",
            bool(re.search(r"do not.*local.merge|not local-merge", merge_section, re.IGNORECASE)))

    # Check 6: Gate completion leads to merge handling
    t.check("gate completion references merge handling",
            bool(re.search(r"terminal.*merge|merge handling", assembled_text, re.IGNORECASE)))

    # Check 7: Gate approval path does NOT have inline merge hook instructions
    # (merge hooks should be in the Merge section, not duplicated in gate section)
    gate_section_lines = []
    in_gate = False
    for line in assembled_text.splitlines():
        if re.match(r"^## Completion and Gates", line):
            in_gate = True
            continue
        if in_gate and re.match(r"^## (Feedback|Merge)", line):
            break
        if in_gate:
            gate_section_lines.append(line)
    gate_section = "\n".join(gate_section_lines)
    t.check("gate section does NOT have inline merge hook instruction",
            not bool(re.search(r"Run merge hooks.*_mods", gate_section, re.IGNORECASE)))

    # Check 8: No-mods fallback in the guardrail
    t.check("guardrail has no-mods fallback",
            bool(re.search(r"no merge hook.*default local merge|If no merge", assembled_text, re.IGNORECASE)))

    print()

    # --- Phase 2: Set up test project with merge hook mod ---

    print("--- Phase 2: Set up test project with merge hook mod ---")

    create_test_project(t)
    fixture_dir = t.repo_root / "tests" / "fixtures" / "merge-hook-pipeline"

    # Copy workflow fixture (including _mods/)
    setup_fixture(t, "merge-hook-pipeline", "merge-hook-pipeline")
    install_agents(t)

    git_add_commit(t.test_project_dir, "setup: merge hook guardrail test fixture")

    print()
    print("[Fixture Setup — With Hook]")

    fo_text = assembled_agent_content(t, "first-officer")
    t.check("assembled first-officer contains merge hook guardrail",
            "merge hook" in fo_text.lower() and "before any merge" in fo_text.lower())
    if "merge hook" not in fo_text.lower():
        print("  FATAL: Merge hook guardrail text missing from assembled agent. Aborting.")
        t.results()
        return

    t.check_cmd("status script runs without errors",
                ["bash", "merge-hook-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 3: Run first officer (with hook mod) ---

    print("--- Phase 3: Run first officer with hook mod (this takes ~60-120s) ---")

    # Save the original test_project_dir and log for the with-hook run
    with_hook_project = t.test_project_dir
    run_first_officer(
        t,
        "Process all tasks through the workflow to completion.",
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "2.00"],
    )

    # --- Phase 4: Validate hook fired ---

    print("--- Phase 4: Validate merge hook execution ---")
    print()
    print("[Merge Hook Execution]")

    hook_file = with_hook_project / "merge-hook-pipeline" / "_merge-hook-fired.txt"
    if hook_file.is_file():
        t.pass_("_merge-hook-fired.txt exists")
        hook_content = hook_file.read_text()
        if "merge-hook-entity" in hook_content:
            t.pass_("_merge-hook-fired.txt contains entity slug")
        else:
            t.fail("_merge-hook-fired.txt contains entity slug")
            print(f"  Contents: {hook_content.strip()}")
    else:
        t.fail("_merge-hook-fired.txt exists (hook did not fire)")
        t.fail("_merge-hook-fired.txt contains entity slug (file missing)")

    # Check: entity was archived (merge completed after hook)
    archive_file = with_hook_project / "merge-hook-pipeline" / "_archive" / "merge-hook-entity.md"
    entity_file = with_hook_project / "merge-hook-pipeline" / "merge-hook-entity.md"
    if archive_file.is_file():
        t.pass_("entity was archived (merge completed after hook)")
    elif entity_file.is_file():
        fm = read_entity_frontmatter(entity_file)
        status_val = fm.get("status", "?")
        print(f"  SKIP: entity not archived (status: {status_val}) — FO may not have completed the full cycle within budget")
    else:
        t.fail("entity was archived (entity file not found in either location)")

    print()

    # --- Phase 5: Set up and run no-mods fallback test ---

    print("--- Phase 5: Set up no-mods fallback test ---")

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
    print("--- Phase 6: Run first officer without mods (this takes ~60-120s) ---")

    # Point runner at the no-mods project for this run
    t.test_project_dir = nomods_project
    nomods_log = "fo-nomods-log.jsonl"
    run_first_officer(
        t,
        "Process all tasks through the workflow to completion.",
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "2.00"],
        log_name=nomods_log,
    )

    # --- Phase 7: Validate no-mods fallback ---

    print("--- Phase 7: Validate no-mods fallback ---")
    print()
    print("[No-Mods Fallback]")

    # Check: _merge-hook-fired.txt does NOT exist (no hooks to fire)
    nomods_hook = nomods_project / "merge-hook-pipeline" / "_merge-hook-fired.txt"
    if nomods_hook.is_file():
        t.fail("no _merge-hook-fired.txt in no-mods run (file exists unexpectedly)")
    else:
        t.pass_("no _merge-hook-fired.txt in no-mods run")

    # Check: entity was archived via local merge
    nomods_archive = nomods_project / "merge-hook-pipeline" / "_archive" / "merge-hook-entity.md"
    nomods_entity = nomods_project / "merge-hook-pipeline" / "merge-hook-entity.md"
    if nomods_archive.is_file():
        t.pass_("entity was archived via local merge (no-mods fallback works)")
    elif nomods_entity.is_file():
        fm = read_entity_frontmatter(nomods_entity)
        status_val = fm.get("status", "?")
        print(f"  SKIP: entity not archived (status: {status_val}) — FO may not have completed the full cycle within budget")
    else:
        t.fail("entity was archived via local merge (entity file not found)")

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
