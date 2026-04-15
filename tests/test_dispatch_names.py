# ABOUTME: E2E test for dispatch name collision fix across consecutive stages.
# ABOUTME: Verifies an entity completes the full pipeline without agents getting killed by stale shutdowns.

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    assembled_agent_content,
    git_add_commit,
    install_agents,
    read_entity_frontmatter,
    run_first_officer,
    setup_fixture,
)


@pytest.mark.live_claude
def test_dispatch_names(test_project):
    """Entity completes the full pipeline without agents getting killed by stale shutdowns."""
    t = test_project

    print("--- Phase 1: Set up test project from fixture ---")
    setup_fixture(t, "multi-stage-pipeline", "dispatch-pipeline")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: no-gate pipeline fixture")

    print()
    print("[Fixture Setup]")
    fo_text = assembled_agent_content(t, "first-officer")
    assert re.search(r'name=.*\{.*stage', fo_text), \
        "assembled first-officer must have stage in dispatch name"
    t.pass_("assembled first-officer has stage in dispatch name")

    t.check_cmd("status script runs without errors",
                ["bash", "dispatch-pipeline/status"], cwd=t.test_project_dir)
    status_result = subprocess.run(
        ["bash", "dispatch-pipeline/status", "--next"],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "dispatch-name-test" in status_result.stdout)
    print()

    print("--- Phase 2: Run first officer (this takes ~60-180s) ---")
    run_first_officer(
        t,
        "Process all tasks through the pipeline to completion.",
        extra_args=["--max-budget-usd", "2.00"],
    )

    print("--- Phase 3: Validation ---")
    print()
    print("[Pipeline Completion]")
    entity_file = t.test_project_dir / "dispatch-pipeline" / "dispatch-name-test.md"
    archive_file = t.test_project_dir / "dispatch-pipeline" / "_archive" / "dispatch-name-test.md"

    final_file = None
    if archive_file.is_file():
        final_file = archive_file
        t.pass_("entity was archived (reached terminal stage)")
    elif entity_file.is_file():
        final_file = entity_file
        print("  INFO: entity still in main directory (not archived)")
    else:
        t.fail("entity file exists")

    if final_file:
        fm = read_entity_frontmatter(final_file)
        status_val = fm.get("status", "")
        t.check("entity reached done status", status_val == "done")
        if status_val != "done":
            print(f"  (stuck at: {status_val})")
        t.check(f"entity advanced past backlog (status: {status_val})",
                status_val != "backlog")

    log = LogParser(t.log_dir / "fo-log.jsonl")
    dispatch_count = len(log.agent_calls())
    t.check(
        f"multiple dispatches occurred ({dispatch_count} Agent() calls)"
        if dispatch_count >= 2
        else f"multiple dispatches occurred (got {dispatch_count} — expected >=2 for work + review)",
        dispatch_count >= 2,
    )

    if final_file:
        completed_val = fm.get("completed", "")
        t.check("entity has completed timestamp", bool(completed_val))

    t.finish()

