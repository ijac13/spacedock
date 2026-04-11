#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E regression test for team-mode dispatch completion-signal in the FO template.
# ABOUTME: Drives an FO through a team-dispatched worktree stage and asserts status advances.

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit, read_entity_frontmatter,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Dispatch completion-signal E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def skip_result(reason: str) -> None:
    print(f"  SKIP: {reason}")
    print()
    print("=== Results ===")
    print("  0 passed, 0 failed, 1 skipped")
    print()
    print("RESULT: SKIP")
    sys.exit(0)


def probe_claude_runtime(model: str) -> tuple[bool, str]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    cmd = [
        "claude", "-p", "Reply with OK and nothing else.",
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--max-budget-usd", "0.20",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, f"claude preflight for model {model!r} produced no result within 30s"

    if result.returncode != 0:
        return False, f"claude preflight for model {model!r} exited {result.returncode}"

    if '"type":"result"' not in result.stdout and '"type": "result"' not in result.stdout:
        return False, f"claude preflight for model {model!r} returned no stream-json result record"

    return True, ""


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Dispatch Completion-Signal E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "completion-signal-pipeline", "completion-signal-pipeline")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: completion-signal regression fixture")

    status_cmd = [
        "python3",
        str(t.repo_root / "skills" / "commission" / "bin" / "status"),
        "--workflow-dir", "completion-signal-pipeline",
    ]
    t.check_cmd("status script runs without errors", status_cmd, cwd=t.test_project_dir)

    print()

    # --- Phase 2: Run the first officer ---

    # Prompt intentionally refers to "all tasks" (plural) so the FO stays in normal
    # team-mode dispatch instead of single-entity mode. The bug only manifests in
    # team mode — bare mode dispatches return inline and never need the SendMessage
    # completion signal.

    print(f"--- Phase 2: Run first officer ({args.runtime}) ---")

    ok, reason = probe_claude_runtime(args.model)
    if not ok:
        skip_result(
            f"live Claude runtime unavailable before FO dispatch: {reason}. "
            "This environment cannot currently prove or disprove the haiku regression."
        )

    abs_workflow = t.test_project_dir / "completion-signal-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/ to terminal completion. "
            "Drive every dispatchable task through its stages until the entity reaches the done "
            "stage and the local merge path archives it. Stop once the entity is archived."
        ),
        agent_id=args.agent,
        extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "3.00", *extra_args],
    )
    if fo_exit != 0:
        print(f"  (first officer exit code {fo_exit} — may be expected for the pre-fix hang case)")
    # Pre-fix: the FO hits the 600s timeout (exit 124) because it cannot cleanly
    # shut down the team-dispatched ensign after it goes idle — the
    # SendMessage(to="team-lead", ...) completion signal the FO is waiting for was
    # never emitted by the worker. Post-fix: the ensign sends completion promptly,
    # the FO processes it, and exits cleanly within the timeout.
    t.check("first officer exited cleanly within timeout (no pre-fix hang)", fo_exit == 0)

    # --- Phase 3: Validate entity advanced without manual captain intervention ---

    print()
    print("--- Phase 3: Validation ---")
    print()
    print("[Entity Advancement]")

    entity_main = t.test_project_dir / "completion-signal-pipeline" / "completion-signal-task.md"
    entity_archive = t.test_project_dir / "completion-signal-pipeline" / "_archive" / "completion-signal-task.md"

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_agent_calls(t.log_dir / "agent-calls.txt")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")
    log.write_agent_prompt(t.log_dir / "agent-prompts.txt")

    agent_calls = log.agent_calls()
    ensign_calls = [c for c in agent_calls if "ensign" in c["subagent_type"]]
    t.check("FO dispatched at least one ensign", len(ensign_calls) > 0)

    # Core assertion: the entity must have advanced past the dispatched `work` stage.
    # Pre-fix: the ensign writes its stage report and goes idle, so the FO's DISPATCH
    # IDLE GUARDRAIL waits indefinitely — the entity stays at status=work until the
    # session times out or the budget cap hits.
    # Post-fix: the ensign SendMessages completion, the FO treats that as completion,
    # and the entity advances to done (or is archived via the default local merge path).
    if entity_archive.is_file():
        t.pass_("entity advanced and was archived without manual captain intervention")
    elif entity_main.is_file():
        fm = read_entity_frontmatter(entity_main)
        status_val = fm.get("status", "")
        if status_val == "done":
            t.pass_(f"entity advanced to terminal stage (status: {status_val})")
        else:
            t.fail(
                f"entity did NOT advance past dispatched stage (status: {status_val!r}). "
                "This reproduces the bug: team-dispatched ensign sent no completion signal, "
                "so the FO's DISPATCH IDLE GUARDRAIL waited forever."
            )
    else:
        t.fail("entity file missing from both main and _archive (unexpected state)")

    # Sanity check: the dispatched ensign prompt should carry the completion-signal
    # instruction. This is an additional guard against a regression where the fix
    # exists in the template but the prompt assembly drops it.
    last_prompt = log.agent_prompt()
    if ensign_calls:
        if 'SendMessage(to="team-lead"' in last_prompt:
            t.pass_("dispatched ensign prompt carries SendMessage completion-signal instruction")
        else:
            t.fail(
                'dispatched ensign prompt does NOT carry SendMessage(to="team-lead", ...) '
                "instruction — the FO dropped the completion signal from its dispatch template."
            )

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
