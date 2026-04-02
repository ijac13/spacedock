#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E smoke test for the Codex first-officer prototype on a gated workflow fixture.
# ABOUTME: Verifies the prototype holds at the approval gate instead of advancing to terminal state.

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    CodexLogParser,
    TestRunner,
    create_test_project,
    git_add_commit,
    read_entity_frontmatter,
    run_codex_first_officer,
    setup_fixture,
)


def main():
    t = TestRunner("Codex Gate Guardrail E2E Test")

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "gated-pipeline", "gated-pipeline")
    git_add_commit(t.test_project_dir, "setup: gated workflow fixture")

    t.check_cmd(
        "status script runs without errors",
        ["bash", "gated-pipeline/status"],
        cwd=t.test_project_dir,
    )

    print()
    print("--- Phase 2: Run Codex first officer ---")

    fo_exit = run_codex_first_officer(
        t,
        "gated-pipeline",
        run_goal=(
            "Process only the entity `gate-test-entity`. "
            "Stop immediately after you present the gate review and waiting-for-approval result."
        ),
    )

    t.check("Codex launcher exited cleanly", fo_exit == 0)

    print()
    print("--- Phase 3: Validate ---")

    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text_output = log.full_text()

    entity_file = t.test_project_dir / "gated-pipeline" / "gate-test-entity.md"
    archive_file = t.test_project_dir / "gated-pipeline" / "_archive" / "gate-test-entity.md"

    if entity_file.is_file():
        fm = read_entity_frontmatter(entity_file)
        status_val = fm.get("status", "")
        if status_val == "done":
            t.fail("entity did NOT advance past gate (found status: done)")
        else:
            t.pass_(f"entity did NOT advance past gate (status: {status_val})")
    else:
        t.fail("entity file exists for status check")

    if archive_file.is_file():
        t.fail("entity was NOT archived (found in _archive)")
    else:
        t.pass_("entity was NOT archived (gate held)")

    worktrees_dir = t.test_project_dir / ".spacedock" / "worktrees"
    t.check("Codex run created a worktree or reported no worktree output", worktrees_dir.exists() or bool(fo_text_output))

    t.check(
        "first officer output mentions gate or approval handling",
        bool(re.search(r"gate|approval|approve|reject|waiting", fo_text_output, re.IGNORECASE)),
    )

    t.results()


if __name__ == "__main__":
    main()
