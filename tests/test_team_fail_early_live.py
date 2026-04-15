#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Live behavioral checks for #149 fail-early team-infrastructure defense.
# ABOUTME: AC-6-live asserts fresh-suffixed TeamCreate name; AC-1-live asserts no pre-dispatch config.json probe.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser,
    TestRunner,
    _isolated_claude_env,
    assembled_agent_content,
    create_test_project,
    emit_skip_result,
    git_add_commit,
    install_agents,
    probe_claude_runtime,
    run_first_officer,
    setup_fixture,
)


TEAM_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-\d{8}-\d{4}-[a-z0-9]+$")
CONFIG_PROBE_PATTERN = re.compile(r"test\s+-f\b.*\.claude/teams/.*config\.json")


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Fail-early live behavioral tests")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    parser.add_argument(
        "--check",
        choices=["all", "team-create-name", "no-predispatch-probe"],
        default="all",
        help="Which behavioral check to run (default: all)",
    )
    return parser.parse_known_args()


def run_fo_once(t: TestRunner, args: argparse.Namespace, extra_args: list[str]) -> Path:
    """Set up a fixture, run the FO once in teams mode, return the log path."""
    create_test_project(t)
    setup_fixture(t, "multi-stage-pipeline", "dispatch-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: fail-early live test fixture")

    abs_workflow = t.test_project_dir / "dispatch-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/. "
            "Drive the entity from backlog through to completion."
        ),
        agent_id=args.agent,
        extra_args=[
            "--model", args.model,
            "--effort", args.effort,
            "--max-budget-usd", "2.00",
            *extra_args,
        ],
    )
    if fo_exit != 0:
        print("  (non-zero FO exit — may be expected under budget caps)")

    return t.log_dir / "fo-log.jsonl"


def check_team_create_name(t: TestRunner, log_path: Path) -> None:
    """AC-6-live: TeamCreate's team_name matches the fresh-suffixed pattern."""
    print()
    print("[AC-6-live: fresh-suffixed TeamCreate name]")

    log = LogParser(log_path)
    team_create_calls = [
        call for call in log.tool_calls() if call["name"] == "TeamCreate"
    ]

    if not team_create_calls:
        print("  SKIP: no TeamCreate call observed in FO log (likely bare-mode fallback).")
        return

    first = team_create_calls[0]
    team_name = first["input"].get("team_name", "")
    ok = bool(TEAM_NAME_PATTERN.match(team_name))
    label = (
        f"TeamCreate team_name matches fresh-suffixed pattern "
        f"(captured: {team_name!r})"
    )
    t.check(label, ok)
    if not ok:
        print(f"    expected regex: {TEAM_NAME_PATTERN.pattern}")


def check_no_predispatch_probe(t: TestRunner, log_path: Path) -> None:
    """AC-1-live: no Bash(test -f …config.json) call precedes the first Agent() dispatch."""
    print()
    print("[AC-1-live: no pre-dispatch config.json probe]")

    log = LogParser(log_path)
    calls = log.tool_calls()

    agent_index: int | None = None
    for i, call in enumerate(calls):
        if call["name"] == "Agent":
            agent_index = i
            break

    if agent_index is None:
        print("  SKIP: no Agent() call observed in FO log.")
        return

    pre_agent_bash = [
        call for call in calls[:agent_index]
        if call["name"] == "Bash"
    ]
    violations = [
        call["input"].get("command", "")
        for call in pre_agent_bash
        if CONFIG_PROBE_PATTERN.search(call["input"].get("command", ""))
    ]

    label = "no pre-dispatch Bash(test -f …config.json) probe before first Agent()"
    t.check(label, not violations)
    for v in violations:
        print(f"    violation: {v!r}")


def main() -> None:
    args, extra_args = parse_args()

    env = _isolated_claude_env()
    if env is None:
        emit_skip_result(
            "no ~/.claude/benchmark-token — live claude runtime isolation unavailable."
        )

    ok, reason = probe_claude_runtime(args.model)
    if not ok:
        emit_skip_result(f"claude runtime preflight failed: {reason}")

    t = TestRunner(f"Fail-Early Live Behavioral Test ({args.runtime}, {args.model})")

    log_path = run_fo_once(t, args, extra_args)

    if args.check in ("all", "team-create-name"):
        check_team_create_name(t, log_path)
    if args.check in ("all", "no-predispatch-probe"):
        check_no_predispatch_probe(t, log_path)

    t.results()


if __name__ == "__main__":
    main()
