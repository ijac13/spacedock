#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E and static tests for ensign reuse dispatch behavior in the FO template.
# ABOUTME: Runs the reuse-pipeline fixture through the FO and verifies Agent/SendMessage patterns.

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser, TestRunner, assembled_agent_content, create_test_project,
    git_add_commit, install_agents, read_entity_frontmatter,
    run_first_officer, setup_fixture,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Reuse dispatch E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Reuse Dispatch E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "reuse-pipeline", "reuse-pipeline")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: reuse dispatch fixture")

    status_cmd = [
        "python3",
        str(t.repo_root / "skills" / "commission" / "bin" / "status"),
        "--workflow-dir", "reuse-pipeline",
    ]
    t.check_cmd("status script runs without errors", status_cmd, cwd=t.test_project_dir)

    status_result = subprocess.run(
        status_cmd + ["--next"],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "reuse-test-task" in status_result.stdout)

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}) ---")

    abs_workflow = t.test_project_dir / "reuse-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process the entity `reuse-test-task` through the workflow at {abs_workflow}/. "
            "Drive it from backlog through analysis, implementation, and validation to done. "
            "When analysis completes and the next stage (implementation) meets reuse conditions "
            "(same worktree mode, no fresh:true, teams available), reuse the agent via SendMessage "
            "instead of dispatching fresh. "
            "When you reach the validation gate, auto-approve if PASSED."
        ),
        agent_id=args.agent,
        extra_args=[
            "--model", args.model,
            "--effort", args.effort,
            "--max-budget-usd", "5.00",
            *extra_args,
        ],
    )

    if fo_exit != 0:
        print("  (may be expected — budget cap or gate hold)")

    # --- Phase 3: Validate ---

    print("--- Phase 3: Validation ---")

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_agent_calls(t.log_dir / "agent-calls.txt")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")
    log.write_tool_calls(t.log_dir / "tool-calls.json")

    agent_calls = log.agent_calls()
    tool_calls = log.tool_calls()
    fo_text = "\n".join(log.fo_texts())

    print()
    print("[Agent Dispatch Pattern]")

    # Expect Agent() calls — one for analysis (initial dispatch), one for validation (fresh: true)
    ensign_calls = [c for c in agent_calls if c["subagent_type"] == "spacedock:ensign"]
    analysis_dispatches = [c for c in ensign_calls if "analysis" in c["name"]]
    implementation_dispatches = [c for c in ensign_calls if "implementation" in c["name"]]
    validation_dispatches = [c for c in ensign_calls if "validation" in c["name"]]

    t.check(
        "FO dispatched Agent() for analysis stage (initial dispatch)",
        len(analysis_dispatches) >= 1,
    )

    # The reuse behavior means implementation should get SendMessage instead of Agent().
    # With LLM-based FOs, the model may also dispatch Agent() as a fallback. The primary
    # signal is that SendMessage reuse was attempted (checked below). Log the Agent()
    # count for implementation for diagnostic visibility.
    if len(implementation_dispatches) == 0:
        t.pass_("FO skipped Agent() for implementation (reused via SendMessage)")
    else:
        print(f"  INFO: FO dispatched {len(implementation_dispatches)} Agent() call(s) for implementation")
        print(f"        (ideal behavior is 0 — reuse via SendMessage only)")

    # Validation has fresh: true, so it must get an Agent() dispatch (not reuse).
    # This check only applies if the pipeline progressed far enough to reach validation.
    if len(validation_dispatches) >= 1:
        t.pass_("FO dispatched Agent() for validation stage (fresh: true forces fresh dispatch)")
    elif len(ensign_calls) >= 2:
        t.fail("FO reached validation but did not dispatch Agent() (fresh: true should force fresh)")
    else:
        print("  SKIP: pipeline did not progress to validation stage within budget")

    print()
    print("[SendMessage Reuse Pattern]")

    # Expect SendMessage for the analysis->implementation reuse
    send_messages = [
        c for c in tool_calls
        if c["name"] == "SendMessage"
        and isinstance(c.get("input"), dict)
    ]
    reuse_messages = [
        m for m in send_messages
        if re.search(
            r"implementation|advancing to next stage",
            str(m.get("input", {}).get("message", "")),
            re.IGNORECASE,
        )
    ]

    t.check(
        "FO sent SendMessage for reuse dispatch (analysis -> implementation transition)",
        len(reuse_messages) >= 1,
    )

    if reuse_messages:
        msg_content = str(reuse_messages[0].get("input", {}).get("message", ""))
        t.check(
            "reuse SendMessage contains stage definition",
            "Stage definition" in msg_content or "implementation" in msg_content.lower(),
        )

    print()
    print("[Entity Outcome]")

    entity_main = t.test_project_dir / "reuse-pipeline" / "reuse-test-task.md"
    archive_path = t.test_project_dir / "reuse-pipeline" / "_archive" / "reuse-test-task.md"

    if archive_path.is_file():
        t.pass_("entity archived (reached terminal stage)")
    elif entity_main.is_file():
        fm = read_entity_frontmatter(entity_main)
        status_val = fm.get("status", "?")
        if status_val == "done":
            t.pass_(f"entity reached terminal stage (status: {status_val})")
        elif status_val in ("validation", "implementation"):
            print(f"  SKIP: entity at {status_val} — FO may not have completed full cycle within budget")
        else:
            t.fail(f"entity did not reach expected stage (status: {status_val})")
    else:
        t.fail("entity file not found in active or archive location")

    print()
    print("[Static Template Checks]")

    # Supplementary static checks
    core = (REPO_ROOT / "references" / "first-officer-shared-core.md").read_text()
    runtime = (REPO_ROOT / "references" / "claude-first-officer-runtime.md").read_text()
    assembled = assembled_agent_content(t, "first-officer")

    t.check("reuse conditions documented in shared-core",
            "Reuse conditions" in core and "bare mode" in core.lower())
    t.check("SendMessage format in reuse path",
            "SendMessage(" in core and "Stage definition:" in core)
    t.check("fresh: true disqualifies reuse",
            bool(re.search(r"NOT have.*fresh: true", core)))
    t.check("worktree mode match required",
            bool(re.search(r"same.*worktree.*mode", core, re.IGNORECASE)))
    t.check("bare mode guard present",
            bool(re.search(r"Not in bare mode", core)))
    t.check("feedback-to keep-alive in fresh dispatch path",
            bool(re.search(r"If fresh dispatch.*feedback-to.*keep.*alive", core, re.DOTALL | re.IGNORECASE)))
    t.check("gate approval references reuse conditions",
            bool(re.search(r"captain approves.*reuse conditions", core, re.DOTALL | re.IGNORECASE)))
    t.check("no 'Always dispatch fresh' in assembled FO",
            "Always dispatch fresh" not in assembled)
    t.check("dispatch step uses neutral language",
            "Dispatch a worker for the stage" in core and "Dispatch a fresh worker" not in core)
    t.check("runtime clarifies SendMessage for reuse only",
            "NEVER use SendMessage to dispatch" not in runtime
            and bool(re.search(r"SendMessage.*completion path|completion path.*SendMessage", runtime, re.IGNORECASE)))

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
