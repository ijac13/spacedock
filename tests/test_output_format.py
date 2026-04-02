#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for configurable output format in single-entity mode.
# ABOUTME: Verifies the FO follows README Output Format instructions or falls back to default.

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, assembled_agent_content, run_first_officer,
    git_add_commit, file_contains, read_entity_frontmatter,
)


def main():
    t = TestRunner("Output Format E2E Test")

    # --- Phase 1: Static checks on assembled FO content ---

    print("--- Phase 1: Static checks on assembled FO content ---")

    fo_text = assembled_agent_content(t, "first-officer")

    t.check("assembled FO references Output Format section from README",
            "Output Format" in fo_text and "fall back" in fo_text)

    t.check("assembled FO covers single-entity output format rules",
            "Output Format" in fo_text and "terminal" in fo_text.lower())

    t.check("custom format fixture has ## Output Format section",
            file_contains(t.repo_root / "tests" / "fixtures" / "output-format-custom" / "README.md",
                          r"## Output Format"))

    t.check("default format fixture has no ## Output Format section",
            not file_contains(t.repo_root / "tests" / "fixtures" / "output-format-default" / "README.md",
                              r"## Output Format"))

    print()

    # --- Phase 2: E2E — custom output format ---

    print("--- Phase 2: Run FO with custom output format (already-terminal entity) ---")

    create_test_project(t, "project-custom")
    setup_fixture(t, "output-format-custom", "output-format-custom")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: output-format-custom fixture")

    fo_exit_custom = run_first_officer(
        t,
        "Process format-test-entity through all stages.",
        extra_args=["--max-budget-usd", "1.00"],
        log_name="fo-log-custom.jsonl",
    )

    log_custom = LogParser(t.log_dir / "fo-log-custom.jsonl")
    log_custom.write_fo_texts(t.log_dir / "fo-texts-custom.txt")
    custom_output = "\n".join(log_custom.fo_texts())

    print()
    print("[Custom Output Format Checks]")

    # The custom README specifies: RESULT: {verdict}, ENTITY: {entity_id}, TITLE: {entity_title}
    t.check("custom output contains RESULT: line",
            bool(re.search(r"RESULT:\s*PASSED", custom_output, re.IGNORECASE)))

    t.check("custom output contains ENTITY: line",
            bool(re.search(r"ENTITY:\s*001", custom_output, re.IGNORECASE)))

    t.check("custom output contains TITLE: line",
            bool(re.search(r"TITLE:\s*Custom format test entity", custom_output, re.IGNORECASE)))

    print()

    # --- Phase 3: E2E — default output format (real dispatch) ---

    print("--- Phase 3: Run FO with default output format (entity starts at backlog) ---")

    # Create a separate test project for the default fixture.
    # The entity starts at backlog so the FO must dispatch an ensign to process it
    # through work -> done, then print the default output format.
    create_test_project(t, "project-default")
    setup_fixture(t, "output-format-default", "output-format-default")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: output-format-default fixture")

    fo_exit_default = run_first_officer(
        t,
        "Process format-test-entity through all stages.",
        extra_args=["--max-budget-usd", "3.00"],
        log_name="fo-log-default.jsonl",
    )

    log_default = LogParser(t.log_dir / "fo-log-default.jsonl")
    log_default.write_fo_texts(t.log_dir / "fo-texts-default.txt")
    default_output = "\n".join(log_default.fo_texts())

    print()
    print("[Default Output Format Checks]")

    # Verify the entity actually reached terminal status (was processed, not skipped)
    entity_path = t.test_project_dir / "output-format-default" / "_archive" / "format-test-entity.md"
    if not entity_path.exists():
        entity_path = t.test_project_dir / "output-format-default" / "format-test-entity.md"
    entity_fm = read_entity_frontmatter(entity_path)

    t.check("entity reached terminal status (done)",
            entity_fm.get("status") == "done")

    # Default format: terminal state (status and verdict) and entity ID
    t.check("default output mentions terminal status (done)",
            bool(re.search(r"\bdone\b", default_output, re.IGNORECASE)))

    t.check("default output mentions entity ID (001)",
            "001" in default_output)

    t.check("default output mentions verdict",
            bool(re.search(r"PASSED|REJECTED", default_output)))

    print()

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
