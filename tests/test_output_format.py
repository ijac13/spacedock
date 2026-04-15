# ABOUTME: E2E test for configurable output format in single-entity mode.
# ABOUTME: Verifies the FO follows README Output Format instructions or falls back to default.

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    assembled_agent_content,
    create_test_project,
    file_contains,
    git_add_commit,
    install_agents,
    read_entity_frontmatter,
    run_first_officer,
    setup_fixture,
)


@pytest.mark.xfail(reason="pending #154 — test assertions target `agents/first-officer.md` but post-#085 skill-preload the content lives in the skill/references layer", strict=False)
@pytest.mark.live_claude
def test_output_format(test_project):
    """FO obeys README Output Format section, falls back to default when absent."""
    t = test_project

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

    print("--- Phase 2: Run FO with custom output format (already-terminal entity) ---")
    create_test_project(t, "project-custom")
    setup_fixture(t, "output-format-custom", "output-format-custom")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: output-format-custom fixture")

    run_first_officer(
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
    t.check("custom output contains RESULT: line",
            bool(re.search(r"RESULT:\s*PASSED", custom_output, re.IGNORECASE)))
    t.check("custom output contains ENTITY: line",
            bool(re.search(r"ENTITY:\s*001", custom_output, re.IGNORECASE)))
    t.check("custom output contains TITLE: line",
            bool(re.search(r"TITLE:\s*Custom format test entity", custom_output, re.IGNORECASE)))
    print()

    print("--- Phase 3: Run FO with default output format (entity starts at backlog) ---")
    create_test_project(t, "project-default")
    setup_fixture(t, "output-format-default", "output-format-default")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: output-format-default fixture")

    run_first_officer(
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
    entity_path = t.test_project_dir / "output-format-default" / "_archive" / "format-test-entity.md"
    if not entity_path.exists():
        entity_path = t.test_project_dir / "output-format-default" / "format-test-entity.md"
    entity_fm = read_entity_frontmatter(entity_path)
    t.check("entity reached terminal status (done)",
            entity_fm.get("status") == "done")
    t.check("default output mentions terminal status (done)",
            bool(re.search(r"\bdone\b", default_output, re.IGNORECASE)))
    t.check("default output mentions entity ID (001)", "001" in default_output)
    t.check("default output mentions verdict",
            bool(re.search(r"PASSED|REJECTED", default_output)))

    t.finish()

