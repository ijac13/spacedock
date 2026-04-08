#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E behavioral tests for agent-captain interaction guardrails (AC6, AC7).
# ABOUTME: Verifies ensign uses direct text for captain and FO does not prematurely shut down agents.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser,
    TestRunner,
    create_test_project,
    git_add_commit,
    install_agents,
    run_first_officer,
    setup_fixture,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _project_slug(project_dir: str | Path) -> str:
    """Compute the Claude Code project slug for a directory path.

    Claude Code replaces all non-alphanumeric characters (except dashes) in
    the resolved path with dashes.
    """
    resolved = str(Path(project_dir).resolve())
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", resolved)
    return slug


def find_subagent_logs(project_dir: str | Path) -> dict[str, Path]:
    """Find subagent JSONL logs for the most recent session in a project."""
    claude_dir = Path.home() / ".claude" / "projects"
    slug = _project_slug(project_dir)
    project_session_dir = claude_dir / slug
    if not project_session_dir.is_dir():
        return {}

    best_dir: Path | None = None
    best_mtime: float = 0
    for session_dir in project_session_dir.iterdir():
        if not session_dir.is_dir():
            continue
        subagents_dir = session_dir / "subagents"
        if subagents_dir.is_dir():
            mtime = subagents_dir.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best_dir = subagents_dir

    if best_dir is None:
        return {}

    logs: dict[str, Path] = {}
    for log_file in sorted(best_dir.glob("*.jsonl")):
        logs[log_file.stem] = log_file
    return logs


def send_message_calls(parser: LogParser) -> list[dict]:
    """Extract SendMessage tool calls from a parsed log."""
    results = []
    for call in parser.tool_calls():
        if call["name"] == "SendMessage":
            inp = call.get("input", {})
            if not isinstance(inp, dict):
                inp = {}
            results.append({"name": "SendMessage", "input": inp})
    return results


def sm_to(sm: dict) -> str:
    """Get the 'to' field from a SendMessage call."""
    return str(sm["input"].get("to", ""))


def sm_msg(sm: dict) -> str:
    """Get the 'message' field from a SendMessage call."""
    return str(sm["input"].get("message", ""))


SHUTDOWN_PATTERN = re.compile(
    r"shut\s*down|terminat|kill|(?:^|\s)stop(?:\s|$)|cancel.*agent",
    re.IGNORECASE,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Agent-captain interaction guardrails E2E test"
    )
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument(
        "--model", default="haiku", help="Model to use (default: haiku)"
    )
    parser.add_argument(
        "--effort", default="low", help="Effort level (default: low)"
    )
    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Agent-Captain Interaction Guardrails E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project ---

    print("--- Phase 1: Set up test project from fixture ---")

    project_dir = create_test_project(t)
    setup_fixture(t, "spike-no-gate", "spike-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(project_dir, "setup: agent-captain interaction test")

    t.check_cmd(
        "status script runs without errors",
        ["bash", "spike-pipeline/status"],
        cwd=project_dir,
    )

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}, this takes ~60-120s) ---")

    abs_workflow = project_dir / "spike-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process the task through the workflow at {abs_workflow}/. "
            "Drive it from backlog through work to done."
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
        print("  (may be expected — budget cap)")

    # --- Phase 3: FO log analysis (AC7) ---

    print("--- Phase 3: Validation ---")

    fo_log = LogParser(t.log_dir / "fo-log.jsonl")
    fo_log.write_tool_calls(t.log_dir / "tool-calls.json")
    fo_log.write_fo_texts(t.log_dir / "fo-texts.txt")

    print()
    print("[AC7 — FO Does Not Prematurely Shut Down Agents]")

    fo_sm_calls = send_message_calls(fo_log)
    print(f"  FO SendMessage calls: {len(fo_sm_calls)}")

    for sm in fo_sm_calls:
        print(f"    to={sm_to(sm)} msg={sm_msg(sm)[:100]}")

    # Scan FO log entries in order. A shutdown is "premature" only if it
    # happens before the FO has evidence that the agent's work is done.
    # Completion evidence: FO text mentioning "complete", "done", "archived",
    # or tool_result containing completion signals.
    completion_evidence = False
    premature_shutdowns = []

    completion_pattern = re.compile(
        r"complete|done|archived|finished|terminal",
        re.IGNORECASE,
    )

    for entry in fo_log.entries:
        # Detect completion evidence from tool_result entries
        if entry.get("type") == "tool_result":
            content = entry.get("message", {})
            if isinstance(content, dict):
                content = str(content.get("content", ""))
            else:
                content = str(content)
            if completion_pattern.search(content):
                completion_evidence = True

        # Detect completion evidence from result entries (Agent call completions)
        if entry.get("type") == "result" and entry.get("subtype") == "success":
            completion_evidence = True

        if entry.get("type") != "assistant" or "message" not in entry:
            continue

        for block in entry["message"].get("content", []):
            # FO text output mentioning completion is evidence
            if block.get("type") == "text":
                text = block.get("text", "")
                if completion_pattern.search(text):
                    completion_evidence = True

            # Check for shutdown SendMessage calls
            if block.get("type") != "tool_use":
                continue
            if block.get("name") == "SendMessage":
                inp = block.get("input", {})
                if not isinstance(inp, dict):
                    continue
                msg_raw = inp.get("message", "")
                # Protocol messages (dicts like {"type": "shutdown_request"})
                # are normal team teardown, not behavioral shutdowns
                if not isinstance(msg_raw, str):
                    continue
                if SHUTDOWN_PATTERN.search(msg_raw) and not completion_evidence:
                    premature_shutdowns.append(msg_raw[:200])

    t.check(
        "FO sends no premature shutdown commands before agent completion",
        len(premature_shutdowns) == 0,
    )

    if premature_shutdowns:
        for msg in premature_shutdowns:
            print(f"    PREMATURE SHUTDOWN: {msg}")

    # Check for Agent tool calls with termination-like prompts
    agent_calls = fo_log.agent_calls()
    print(f"  Agent dispatch calls: {len(agent_calls)}")

    terminate_dispatches = [
        call for call in agent_calls
        if SHUTDOWN_PATTERN.search(call.get("prompt", ""))
    ]

    t.check(
        "FO sends no termination-related Agent dispatches",
        len(terminate_dispatches) == 0,
    )

    if terminate_dispatches:
        for call in terminate_dispatches:
            print(f"    TERMINATE DISPATCH: {call['prompt'][:200]}")

    # --- Phase 4: Subagent log analysis (AC6) ---

    print()
    print("[AC6 — Ensign Communication Pattern]")

    subagent_logs = find_subagent_logs(project_dir)
    print(f"  Subagent logs found: {len(subagent_logs)}")
    for agent_id, path in subagent_logs.items():
        print(f"    {agent_id}: {path}")

    if not subagent_logs:
        # Check if the FO dispatched any agents at all
        if agent_calls:
            print("  WARNING: FO dispatched agents but no subagent logs found")
            print("  Subagent logs may not have been written (budget exhaustion mid-dispatch)")
        else:
            print("  WARNING: FO did not dispatch any agents")
            print("  This can happen if the FO used bare mode or processed inline")
        t.fail("ensign was dispatched and produced subagent logs")
    else:
        for agent_id, log_path in subagent_logs.items():
            print(f"\n  Analyzing subagent: {agent_id}")
            parser = LogParser(log_path)

            texts = parser.fo_texts()
            print(f"    Direct text blocks: {len(texts)}")

            sm_calls = send_message_calls(parser)
            print(f"    SendMessage calls: {len(sm_calls)}")

            for sm in sm_calls:
                print(f"      to={sm_to(sm)} msg={sm_msg(sm)[:100]}")

            # AC6 check 1: Ensign produces direct text output (captain-visible)
            t.check(
                f"[{agent_id}] ensign produces direct text output",
                len(texts) > 0,
            )

            # AC6 check 2: SendMessage only targets team-lead (not captain relay)
            bad_send_messages = [
                sm for sm in sm_calls
                if sm_to(sm) != "team-lead"
            ]

            t.check(
                f"[{agent_id}] SendMessage only targets team-lead (not captain relay)",
                len(bad_send_messages) == 0,
            )

            if bad_send_messages:
                for sm in bad_send_messages:
                    print(f"    BAD: SendMessage to={sm_to(sm)}")

            # AC6 check 3: No long prose relayed via SendMessage
            # Completion signals are short; content relay would be longer
            suspicious_relay = []
            for sm in sm_calls:
                msg = sm_msg(sm)
                to = sm_to(sm)
                if to == "team-lead" and len(msg) > 500:
                    if not re.search(
                        r"(?:Done|Complete|Finished|clarif|question|block)",
                        msg,
                        re.IGNORECASE,
                    ):
                        suspicious_relay.append(msg[:200])

            if suspicious_relay:
                print(f"    WARNING: {len(suspicious_relay)} possibly relayed content via SendMessage")
                for snippet in suspicious_relay:
                    print(f"      {snippet}")

            t.check(
                f"[{agent_id}] no suspicious content relay via SendMessage",
                len(suspicious_relay) == 0,
            )

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
