# ABOUTME: Live E2E test for standing-teammate mod spawn + FO routing (#162).
# ABOUTME: Verifies `standing: true` mod auto-spawns a teammate and SendMessage roundtrip works.

from __future__ import annotations

import json
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


@pytest.mark.live_claude
@pytest.mark.teams_mode
def test_standing_teammate_spawns_and_roundtrips(test_project, effort):
    """AC-12: standing: true mod spawns a teammate the FO can route to.

    Fixture declares one standing teammate (`echo-agent`) via
    `_mods/echo-agent.md`. The FO MUST, during startup:

    1. Invoke `claude-team spawn-standing` (bash tool call).
    2. Spawn `echo-agent` via Agent() (tool_use with subagent_type +
       name=echo-agent in team config).
    3. Route a SendMessage to echo-agent with `ping` and receive a reply
       containing `ECHO: ping`.

    All three are asserted via session-trace inspection (LogParser on the
    stream-json fo-log.jsonl, which folds in every subagent's tool calls
    and messages).
    """
    t = test_project

    print("--- Phase 1: Set up fixture (workflow in subdir) ---")
    setup_fixture(t, "standing-teammate", "standing-teammate")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: standing-teammate fixture")
    print()

    print("--- Phase 2: Run first officer ---")
    abs_workflow = t.test_project_dir / "standing-teammate"
    fo_exit = run_first_officer(
        t,
        (
            f"Process the workflow at {abs_workflow}/ to terminal completion. "
            "During startup, spawn every standing teammate declared in "
            "_mods/*.md with standing: true. Then drive task 001 through its "
            "stages. The task instructs its ensign to SendMessage echo-agent "
            "with 'ping' and capture the reply — do not skip that step. Stop "
            "once the entity is archived."
        ),
        agent_id="spacedock:first-officer",
        extra_args=["--model", "opus", "--effort", effort, "--max-budget-usd", "2.00"],
    )
    if fo_exit != 0:
        print(f"  (first officer exit code {fo_exit})")

    print()
    print("--- Phase 3: Validation ---")

    fo_log = t.log_dir / "fo-log.jsonl"
    assert fo_log.is_file(), f"FO log not found at {fo_log}"

    log = LogParser(fo_log)

    bash_calls = [c for c in log.tool_calls() if c.get("name") == "Bash"]
    spawn_invocations = [
        c for c in bash_calls
        if "spawn-standing" in c.get("input", {}).get("command", "")
    ]
    assert spawn_invocations, (
        "FO did not invoke `claude-team spawn-standing` during startup. "
        f"Bash commands seen: {[c.get('input', {}).get('command', '')[:80] for c in bash_calls]}"
    )
    print(f"[OK] claude-team spawn-standing invoked {len(spawn_invocations)} time(s)")

    agent_calls = log.agent_calls()
    echo_spawns = [c for c in agent_calls if c.get("name") == "echo-agent"]
    assert echo_spawns, (
        "FO did not dispatch an Agent() call named 'echo-agent'. "
        f"Agent() calls seen: {[(c.get('name'), c.get('subagent_type')) for c in agent_calls]}"
    )
    print(f"[OK] echo-agent Agent() dispatched {len(echo_spawns)} time(s)")

    all_tool_calls = log.tool_calls()
    send_to_echo = [
        c for c in all_tool_calls
        if c.get("name") == "SendMessage"
        and c.get("input", {}).get("to") == "echo-agent"
    ]
    assert send_to_echo, (
        "No SendMessage to echo-agent observed in the session trace. "
        "Either the ensign skipped the step or the FO never dispatched the ensign."
    )
    print(f"[OK] SendMessage to echo-agent observed {len(send_to_echo)} time(s)")

    fo_texts = "\n".join(log.fo_texts())
    user_messages = [
        e for e in log.entries
        if e.get("type") == "user"
    ]
    user_payload = json.dumps(user_messages)
    combined = fo_texts + "\n" + user_payload
    assert re.search(r"ECHO:\s*ping", combined), (
        "No 'ECHO: ping' reply seen in FO texts or teammate messages. "
        "The standing teammate did not round-trip the ping within the test window."
    )
    print("[OK] ECHO: ping reply observed in session trace")

    # AC-14 (cycle-2 extension): dispatched worker prompts must contain the
    # `### Standing teammates available in your team` section listing
    # echo-agent. This proves that `claude-team build` injected the section
    # at dispatch time so ensigns discover standing teammates without the FO
    # having to surface them per-dispatch.
    ensign_agent_calls = [c for c in agent_calls if c.get("name") != "echo-agent"]
    assert ensign_agent_calls, (
        "No stage-worker Agent() dispatches observed (only echo-agent spawn). "
        "Cycle-2 prompt-injection assertion requires at least one ensign dispatch."
    )
    prompts_with_section = [
        c for c in ensign_agent_calls
        if "### Standing teammates available in your team" in c.get("prompt", "")
    ]
    assert prompts_with_section, (
        "No dispatched ensign prompt contained the "
        "`### Standing teammates available in your team` section. "
        f"Ensign Agent() prompts seen: "
        f"{[(c.get('name'), c.get('prompt', '')[:120]) for c in ensign_agent_calls]}"
    )
    print(
        f"[OK] Standing-teammates section present in "
        f"{len(prompts_with_section)}/{len(ensign_agent_calls)} ensign dispatch prompt(s)"
    )
    prompts_listing_echo = [
        c for c in prompts_with_section
        if "echo-agent" in c.get("prompt", "")
    ]
    assert prompts_listing_echo, (
        "Standing-teammates section present but did not list `echo-agent` by name. "
        "Auto-enumeration failed to cross-reference the alive team member."
    )
    print(
        f"[OK] echo-agent listed by name in "
        f"{len(prompts_listing_echo)}/{len(prompts_with_section)} section-bearing prompt(s)"
    )
