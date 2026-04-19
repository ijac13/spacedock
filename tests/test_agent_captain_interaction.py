# ABOUTME: E2E behavioral tests for agent-captain interaction guardrails (AC6, AC7).
# ABOUTME: Verifies ensign uses direct text for captain and FO does not prematurely shut down agents.

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    git_add_commit,
    install_agents,
    run_first_officer,
    setup_fixture,
)


def _project_slug(project_dir) -> str:
    resolved = str(Path(project_dir).resolve())
    return re.sub(r"[^a-zA-Z0-9-]", "-", resolved)


def _find_subagent_logs(project_dir) -> dict:
    claude_dir = Path.home() / ".claude" / "projects"
    slug = _project_slug(project_dir)
    project_session_dir = claude_dir / slug
    if not project_session_dir.is_dir():
        return {}

    best_dir = None
    best_mtime = 0
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
    return {lf.stem: lf for lf in sorted(best_dir.glob("*.jsonl"))}


def _send_message_calls(parser: LogParser) -> list[dict]:
    results = []
    for call in parser.tool_calls():
        if call["name"] == "SendMessage":
            inp = call.get("input", {})
            if not isinstance(inp, dict):
                inp = {}
            results.append({"name": "SendMessage", "input": inp})
    return results


def _sm_to(sm: dict) -> str:
    return str(sm["input"].get("to", ""))


def _sm_msg(sm: dict) -> str:
    return str(sm["input"].get("message", ""))


SHUTDOWN_PATTERN = re.compile(
    r"shut\s*down|terminat|kill|(?:^|\s)stop(?:\s|$)|cancel.*agent",
    re.IGNORECASE,
)


# #154 reclassified the original `pending #154` xfail here: this test reads no static FO content,
# so the content-home refresh is irrelevant. The 1/4 live failure is runtime-behavior drift
# (subagent-log discovery under ~/.claude/projects/<slug>/subagents/ returns empty) tracked by #198.
@pytest.mark.xfail(strict=False, reason="pending #198 — runtime subagent-log discovery drift; see docs/plans/fo-runtime-test-failures-post-154.md")
@pytest.mark.live_claude
def test_agent_captain_interaction(test_project, model, effort):
    """FO uses direct text to captain and does not prematurely shut down agents (AC6, AC7)."""
    t = test_project

    print("--- Phase 1: Set up test project from fixture ---")
    project_dir = t.test_project_dir
    setup_fixture(t, "spike-no-gate", "spike-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(project_dir, "setup: agent-captain interaction test")
    t.check_cmd("status script runs without errors",
                ["bash", "spike-pipeline/status"], cwd=project_dir)
    print()

    print("--- Phase 2: Run first officer (claude, this takes ~60-120s) ---")
    abs_workflow = project_dir / "spike-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process the task through the workflow at {abs_workflow}/. "
            "Drive it from backlog through work to done."
        ),
        agent_id="spacedock:first-officer",
        extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
    )
    if fo_exit != 0:
        print("  (may be expected — budget cap)")

    print("--- Phase 3: Validation ---")
    fo_log = LogParser(t.log_dir / "fo-log.jsonl")
    fo_log.write_tool_calls(t.log_dir / "tool-calls.json")
    fo_log.write_fo_texts(t.log_dir / "fo-texts.txt")

    print()
    print("[AC7 — FO Does Not Prematurely Shut Down Agents]")
    fo_sm_calls = _send_message_calls(fo_log)
    print(f"  FO SendMessage calls: {len(fo_sm_calls)}")
    for sm in fo_sm_calls:
        print(f"    to={_sm_to(sm)} msg={_sm_msg(sm)[:100]}")

    completion_evidence = False
    premature_shutdowns = []
    completion_pattern = re.compile(r"complete|done|archived|finished|terminal", re.IGNORECASE)

    for entry in fo_log.entries:
        if entry.get("type") == "tool_result":
            content = entry.get("message", {})
            if isinstance(content, dict):
                content = str(content.get("content", ""))
            else:
                content = str(content)
            if completion_pattern.search(content):
                completion_evidence = True
        if entry.get("type") == "result" and entry.get("subtype") == "success":
            completion_evidence = True
        if entry.get("type") != "assistant" or "message" not in entry:
            continue
        for block in entry["message"].get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "")
                if completion_pattern.search(text):
                    completion_evidence = True
            if block.get("type") != "tool_use":
                continue
            if block.get("name") == "SendMessage":
                inp = block.get("input", {})
                if not isinstance(inp, dict):
                    continue
                msg_raw = inp.get("message", "")
                if not isinstance(msg_raw, str):
                    continue
                if SHUTDOWN_PATTERN.search(msg_raw) and not completion_evidence:
                    premature_shutdowns.append(msg_raw[:200])

    t.check("FO sends no premature shutdown commands before agent completion",
            len(premature_shutdowns) == 0)
    if premature_shutdowns:
        for msg in premature_shutdowns:
            print(f"    PREMATURE SHUTDOWN: {msg}")

    agent_calls = fo_log.agent_calls()
    print(f"  Agent dispatch calls: {len(agent_calls)}")
    terminate_dispatches = [c for c in agent_calls if SHUTDOWN_PATTERN.search(c.get("prompt", ""))]
    t.check("FO sends no termination-related Agent dispatches", len(terminate_dispatches) == 0)
    if terminate_dispatches:
        for call in terminate_dispatches:
            print(f"    TERMINATE DISPATCH: {call['prompt'][:200]}")

    print()
    print("[AC6 — Ensign Communication Pattern]")
    subagent_logs = _find_subagent_logs(project_dir)
    print(f"  Subagent logs found: {len(subagent_logs)}")
    for agent_id, path in subagent_logs.items():
        print(f"    {agent_id}: {path}")

    if not subagent_logs:
        if agent_calls:
            print("  WARNING: FO dispatched agents but no subagent logs found")
        else:
            print("  WARNING: FO did not dispatch any agents")
        t.fail("ensign was dispatched and produced subagent logs")
    else:
        for agent_id, log_path in subagent_logs.items():
            print(f"\n  Analyzing subagent: {agent_id}")
            parser = LogParser(log_path)
            texts = parser.fo_texts()
            print(f"    Direct text blocks: {len(texts)}")
            sm_calls = _send_message_calls(parser)
            print(f"    SendMessage calls: {len(sm_calls)}")
            for sm in sm_calls:
                print(f"      to={_sm_to(sm)} msg={_sm_msg(sm)[:100]}")

            t.check(f"[{agent_id}] ensign produces direct text output", len(texts) > 0)

            bad_send_messages = [sm for sm in sm_calls if _sm_to(sm) != "team-lead"]
            t.check(f"[{agent_id}] SendMessage only targets team-lead (not captain relay)",
                    len(bad_send_messages) == 0)
            if bad_send_messages:
                for sm in bad_send_messages:
                    print(f"    BAD: SendMessage to={_sm_to(sm)}")

            suspicious_relay = []
            for sm in sm_calls:
                msg = _sm_msg(sm)
                to = _sm_to(sm)
                if to == "team-lead" and len(msg) > 500:
                    if not re.search(
                        r"(?:Done|Complete|Finished|clarif|question|block)", msg, re.IGNORECASE,
                    ):
                        suspicious_relay.append(msg[:200])

            if suspicious_relay:
                print(f"    WARNING: {len(suspicious_relay)} possibly relayed content via SendMessage")
                for snippet in suspicious_relay:
                    print(f"      {snippet}")

            t.check(f"[{agent_id}] no suspicious content relay via SendMessage",
                    len(suspicious_relay) == 0)

    t.finish()

