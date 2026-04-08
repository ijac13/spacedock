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
    CodexLogParser, TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, run_codex_first_officer, run_first_officer, git_add_commit,
    rejection_follow_up_observed, rejection_signal_present,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Rejection flow E2E test")
    parser.add_argument("--runtime", choices=["claude", "codex"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Rejection Flow E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from static fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    fixture_dir = t.repo_root / "tests" / "fixtures" / "rejection-flow"
    setup_fixture(t, "rejection-flow", "rejection-pipeline")
    if args.runtime == "claude":
        install_agents(t, include_ensign=True)

    # Copy the buggy implementation and tests into the repo root
    shutil.copy2(fixture_dir / "math_ops.py", t.test_project_dir)
    tests_dir = t.test_project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    shutil.copy2(fixture_dir / "tests" / "test_add.py", tests_dir)

    git_add_commit(t.test_project_dir, "setup: rejection flow fixture with buggy implementation")

    status_cmd = ["python3", str(t.repo_root / "skills" / "commission" / "bin" / "status"),
                  "--workflow-dir", "rejection-pipeline"]
    t.check_cmd("status script runs without errors",
                status_cmd, cwd=t.test_project_dir)

    status_result = subprocess.run(
        status_cmd + ["--next"],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "buggy-add-task" in status_result.stdout)

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}) ---")

    if args.runtime == "claude":
        abs_workflow = t.test_project_dir / "rejection-pipeline"
        fo_exit = run_first_officer(
            t,
            f"Process all tasks through the workflow at {abs_workflow}/. When you encounter a gate review where the reviewer recommends REJECTED, confirm the rejection so the feedback flow routes fixes back to implementation.",
            agent_id=args.agent,
            extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "5.00", *extra_args],
        )

        if fo_exit != 0:
            print("  (may be expected — budget cap or gate hold)")
    else:
        fo_exit = run_codex_first_officer(
            t,
            "rejection-pipeline",
            agent_id=args.agent,
            run_goal=(
                "Process only the entity `buggy-add-task`. "
                "Drive the workflow until validation finishes and you can report the rejection verdict "
                "and the follow-up target. Then stop immediately. "
            "Do not start a second repair cycle after reporting that first rejection outcome. "
            "When you dispatch workers, use the exact Codex pattern "
            "`spawn_agent(agent_type=\"worker\", fork_context=false, message=<fully self-contained prompt>)` "
            "followed by `wait_agent(...)`."
        ),
            timeout_s=300,
        )
        t.check("Codex launcher exited cleanly", fo_exit == 0)

    # --- Phase 3: Validate ---

    print("--- Phase 3: Validation ---")

    if args.runtime == "claude":
        log = LogParser(t.log_dir / "fo-log.jsonl")
        log.write_agent_calls(t.log_dir / "agent-calls.txt")
        log.write_fo_texts(t.log_dir / "fo-texts.txt")
        agent_calls = log.agent_calls()
        fo_text = "\n".join(log.fo_texts())
        worker_messages = ""
    else:
        log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
        log.write_text(t.log_dir / "codex-fo-text.txt")
        agent_calls = []
        fo_text = log.full_text()
        worker_messages = "\n".join(log.completed_agent_messages())

    print()
    print("[Rejection Flow Behavior]")

    entity_main = t.test_project_dir / "rejection-pipeline" / "buggy-add-task.md"
    worktrees_dir = t.test_project_dir / ".worktrees"

    if args.runtime == "claude":
        ensign_calls = [c for c in agent_calls if c["subagent_type"] == "spacedock:ensign"]
        t.check("FO dispatched an ensign for validation stage", len(ensign_calls) > 0)
    else:
        t.check("at least one worker completed", bool(worker_messages.strip()))

    t.check(
        "reviewer stage report contains REJECTED recommendation",
        rejection_signal_present("rejection-pipeline", "buggy-add-task", entity_main, worktrees_dir, worker_messages, fo_text),
    )

    if args.runtime == "claude":
        ensign_count = len(ensign_calls)
        if ensign_count >= 3:
            t.pass_(f"FO dispatched ensign for fix after rejection ({ensign_count} total ensign dispatches)")
        elif ensign_count >= 2:
            t.fail(f"FO dispatched ensign for fix after rejection (only {ensign_count} ensign dispatches — missing fix dispatch)")
        else:
            t.fail(f"FO dispatched ensign for fix after rejection (only {ensign_count} ensign dispatches)")
    else:
        spawn_count = log.spawn_count()
        t.check(
            "multiple worker dispatches occurred",
            spawn_count >= 2 or bool(re.search(r"validation|implementation", worker_messages, re.IGNORECASE)),
        )
        t.check(
            "follow-up work after rejection was observable",
            rejection_follow_up_observed("rejection-pipeline", "buggy-add-task", worktrees_dir, worker_messages, fo_text),
        )
        worktree_candidates = [
            worktrees_dir / "ensign-buggy-add-task",
            worktrees_dir / "spacedock-ensign-buggy-add-task",
        ]
        t.check("worker uses safe worktree key", any(path.is_dir() for path in worktree_candidates))
        t.check(
            "logical packaged id does not leak into worktree path",
            all("spacedock:ensign" not in path.as_posix() for path in worktree_candidates if path.is_dir()),
        )
        branches = subprocess.run(
            ["git", "branch", "--list"],
            capture_output=True,
            text=True,
            cwd=t.test_project_dir,
            check=True,
        ).stdout
        t.check(
            "validation dispatch uses the shared safe branch name",
            "ensign/buggy-add-task" in branches or "spacedock-ensign/buggy-add-task" in branches,
        )

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
