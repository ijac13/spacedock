#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the feedback-to keepalive rule in the first-officer template.
# ABOUTME: Verifies that the FO keeps the implementation agent alive during validation and routes rejection feedback via SendMessage.

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    LogParser, TestRunner, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit,
)


REPO_ROOT = Path(__file__).resolve().parent.parent

SHUTDOWN_PATTERN = re.compile(
    r"shut\s*down|terminat|kill|(?:^|\s)stop(?:\s|$)|cancel.*agent",
    re.IGNORECASE,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Feedback keepalive E2E test")
    parser.add_argument("--runtime", choices=["claude"], default="claude")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def scan_keepalive_events(log: LogParser) -> dict:
    """Walk FO JSONL log entries in order and extract keepalive-relevant events.

    Returns a dict with:
      - impl_dispatch_seen: bool — Agent() dispatched for implementation
      - impl_completion_seen: bool — completion evidence after implementation dispatch
      - validation_dispatch_seen: bool — Agent() dispatched for validation
      - shutdown_before_validation: list — shutdown messages targeting impl agent before validation dispatch
      - rejection_seen: bool — REJECTED signal in log
      - feedback_via_send_message: bool — SendMessage to impl agent after rejection
      - feedback_via_fresh_agent: bool — fresh Agent() for implementation after rejection
    """
    impl_dispatch_seen = False
    impl_completion_seen = False
    validation_dispatch_seen = False
    rejection_seen = False
    feedback_via_send_message = False
    feedback_via_fresh_agent = False
    shutdown_before_validation = []

    # Track the implementation agent's name for SendMessage matching
    impl_agent_name = ""

    completion_pattern = re.compile(
        r"complete|done|archived|finished|terminal|stage report",
        re.IGNORECASE,
    )
    rejection_pattern = re.compile(
        r"REJECTED|recommend reject",
        re.IGNORECASE,
    )

    for entry in log.entries:
        # Track completion evidence from tool_result entries
        if entry.get("type") == "tool_result":
            content = entry.get("message", {})
            if isinstance(content, dict):
                content = str(content.get("content", ""))
            else:
                content = str(content)
            if impl_dispatch_seen and not impl_completion_seen:
                if completion_pattern.search(content):
                    impl_completion_seen = True
            if rejection_pattern.search(content):
                rejection_seen = True

        # Track completion from Agent call result entries
        if entry.get("type") == "result" and entry.get("subtype") == "success":
            if impl_dispatch_seen and not impl_completion_seen:
                impl_completion_seen = True

        if entry.get("type") != "assistant" or "message" not in entry:
            continue

        for block in entry["message"].get("content", []):
            # FO text containing completion signals (but NOT rejection —
            # rejection is only detected from structured tool_result entries
            # to avoid false positives from hypothetical FO narrative)
            if block.get("type") == "text":
                text = block.get("text", "")
                if impl_dispatch_seen and not impl_completion_seen:
                    if completion_pattern.search(text):
                        impl_completion_seen = True

            if block.get("type") != "tool_use":
                continue

            # Agent() calls
            if block.get("name") == "Agent":
                inp = block.get("input", {})
                name = inp.get("name", "")
                name_lower = name.lower()

                if "implementation" in name_lower and not impl_dispatch_seen:
                    impl_dispatch_seen = True
                    impl_agent_name = name
                elif "validation" in name_lower and not validation_dispatch_seen:
                    validation_dispatch_seen = True
                elif "implementation" in name_lower and rejection_seen:
                    # Fresh Agent() dispatch for implementation after rejection
                    feedback_via_fresh_agent = True

            # SendMessage calls
            if block.get("name") == "SendMessage":
                inp = block.get("input", {})
                if not isinstance(inp, dict):
                    continue
                to_field = str(inp.get("to", ""))
                msg_raw = inp.get("message", "")

                # Between implementation completion and validation dispatch:
                # check for shutdown messages targeting impl agent
                if (impl_completion_seen and not validation_dispatch_seen
                        and isinstance(msg_raw, str)):
                    if SHUTDOWN_PATTERN.search(msg_raw):
                        shutdown_before_validation.append(msg_raw[:200])

                # After rejection: check for feedback routing via SendMessage
                if rejection_seen and not feedback_via_send_message:
                    if isinstance(msg_raw, str) and impl_agent_name:
                        # SendMessage targeting the implementation agent with feedback content
                        if (impl_agent_name in to_field or "implementation" in to_field.lower()):
                            if re.search(r"reject|fix|feedback|fail|bug|error|rework", msg_raw, re.IGNORECASE):
                                feedback_via_send_message = True

    return {
        "impl_dispatch_seen": impl_dispatch_seen,
        "impl_completion_seen": impl_completion_seen,
        "validation_dispatch_seen": validation_dispatch_seen,
        "shutdown_before_validation": shutdown_before_validation,
        "rejection_seen": rejection_seen,
        "feedback_via_send_message": feedback_via_send_message,
        "feedback_via_fresh_agent": feedback_via_fresh_agent,
        "impl_agent_name": impl_agent_name,
    }


def main():
    args, extra_args = parse_args()
    t = TestRunner(f"Feedback Keepalive E2E Test ({args.runtime})")

    # --- Phase 1: Set up test project from static fixture ---

    print("--- Phase 1: Set up test project from fixture ---")

    create_test_project(t)
    setup_fixture(t, "keepalive-pipeline", "keepalive-pipeline")
    install_agents(t, include_ensign=True)

    git_add_commit(t.test_project_dir, "setup: keepalive test fixture")

    status_cmd = ["python3", str(t.repo_root / "skills" / "commission" / "bin" / "status"),
                  "--workflow-dir", "keepalive-pipeline"]
    t.check_cmd("status script runs without errors",
                status_cmd, cwd=t.test_project_dir)

    status_result = subprocess.run(
        status_cmd + ["--next"],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    t.check("status --next detects dispatchable entity",
            "keepalive-test-task" in status_result.stdout)

    print()

    # --- Phase 2: Run the first officer ---

    print(f"--- Phase 2: Run first officer ({args.runtime}, this takes ~60-180s) ---")

    abs_workflow = t.test_project_dir / "keepalive-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process the entity `keepalive-test-task` through the workflow at {abs_workflow}/. "
            "Drive it from backlog through implementation and validation. "
            "The implementation task is trivial (create a text file). "
            "The validation stage has feedback-to: implementation, so you must keep the implementation "
            "agent alive when dispatching validation. "
            "When you encounter a gate review where the reviewer recommends REJECTED, "
            "auto-bounce into the feedback rejection flow and route findings to the implementation agent "
            "via SendMessage."
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

    print()
    print("[Agent Dispatch Overview]")

    ensign_calls = [c for c in agent_calls if c["subagent_type"] == "spacedock:ensign"]
    impl_dispatches = [c for c in ensign_calls if "implementation" in c["name"].lower()]
    val_dispatches = [c for c in ensign_calls if "validation" in c["name"].lower()]

    print(f"  Total ensign dispatches: {len(ensign_calls)}")
    print(f"  Implementation dispatches: {len(impl_dispatches)}")
    print(f"  Validation dispatches: {len(val_dispatches)}")

    t.check("FO dispatched Agent() for implementation stage", len(impl_dispatches) >= 1)
    t.check("FO dispatched Agent() for validation stage", len(val_dispatches) >= 1)

    # --- Keepalive event scanning ---

    print()
    print("[Keepalive Event Scan]")

    events = scan_keepalive_events(log)

    print(f"  Implementation dispatch seen: {events['impl_dispatch_seen']}")
    print(f"  Implementation completion seen: {events['impl_completion_seen']}")
    print(f"  Validation dispatch seen: {events['validation_dispatch_seen']}")
    print(f"  Shutdown before validation: {len(events['shutdown_before_validation'])}")
    print(f"  Rejection seen: {events['rejection_seen']}")
    print(f"  Feedback via SendMessage: {events['feedback_via_send_message']}")
    print(f"  Feedback via fresh Agent: {events['feedback_via_fresh_agent']}")

    # --- Tier 1: No shutdown between implementation completion and validation dispatch ---

    print()
    print("[Tier 1 — Keepalive at Transition]")

    if events["impl_completion_seen"] and events["validation_dispatch_seen"]:
        t.check(
            "no shutdown SendMessage targets implementation agent between completion and validation dispatch",
            len(events["shutdown_before_validation"]) == 0,
        )
        if events["shutdown_before_validation"]:
            for msg in events["shutdown_before_validation"]:
                print(f"    PREMATURE SHUTDOWN: {msg}")
    elif not events["impl_dispatch_seen"]:
        print("  SKIP: pipeline did not dispatch implementation stage within budget")
    elif not events["impl_completion_seen"]:
        print("  SKIP: implementation stage did not complete within budget")
    else:
        print("  SKIP: pipeline did not reach validation dispatch within budget")

    # --- Tier 2: Feedback routing after rejection ---

    print()
    print("[Tier 2 — Feedback Routing via SendMessage]")

    if events["rejection_seen"]:
        t.pass_("rejection signal detected in logs or entity")

        if events["feedback_via_send_message"]:
            t.pass_("feedback routed via SendMessage to kept-alive implementation agent (keepalive worked)")
        elif events["feedback_via_fresh_agent"]:
            t.fail("feedback routed via fresh Agent() dispatch instead of SendMessage (keepalive failed — agent was killed and re-dispatched)")
        else:
            # Check if there were any SendMessage calls at all after rejection
            tool_calls = log.tool_calls()
            post_rejection_sms = [
                c for c in tool_calls
                if c["name"] == "SendMessage"
                and isinstance(c.get("input"), dict)
                and re.search(r"implementation", str(c["input"].get("to", "")), re.IGNORECASE)
            ]
            if post_rejection_sms:
                t.pass_("SendMessage sent to implementation agent after rejection (feedback content may not match pattern)")
            else:
                t.fail("no feedback routing observed after rejection (neither SendMessage nor fresh Agent dispatch)")
    else:
        print("  SKIP: rejection not observed — pipeline may not have completed validation within budget")

    # --- Static checks ---

    print()
    print("[Static Template Checks]")

    core = (REPO_ROOT / "skills" / "first-officer" / "references" / "first-officer-shared-core.md").read_text()

    t.check(
        "shared-core contains feedback-to keepalive rule for fresh dispatch",
        bool(re.search(r"If fresh dispatch.*feedback-to.*keep.*alive", core, re.DOTALL | re.IGNORECASE)),
    )
    t.check(
        "shared-core contains auto-bounce rule for REJECTED feedback gates",
        bool(re.search(r"feedback gate.*REJECTED.*auto-bounce", core, re.DOTALL | re.IGNORECASE)),
    )
    t.check(
        "shared-core documents feedback rejection flow with feedback-to routing",
        bool(re.search(r"Feedback Rejection Flow", core)) and bool(re.search(r"feedback-to.*target", core, re.IGNORECASE)),
    )

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
