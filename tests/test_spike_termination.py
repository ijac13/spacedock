#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Spike experiments for session termination behavior in `claude -p` mode.
# ABOUTME: Runs three experiments (A, B, C) to determine how/whether the FO terminates naturally.

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit,
    read_entity_frontmatter,
)


def analyze_termination(log_path: Path, label: str) -> dict:
    """Analyze a stream-json log to determine how the session ended."""
    if not log_path.exists():
        print(f"  [{label}] Log file not found: {log_path}")
        return {"terminated": False, "mechanism": "missing_log"}

    entries = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not entries:
        print(f"  [{label}] Log file empty")
        return {"terminated": False, "mechanism": "empty_log"}

    # Look at the last few entries for termination signals
    last_entries = entries[-10:]

    # Check for budget exhaustion
    budget_exhausted = any(
        "budget" in json.dumps(e).lower() or "max_budget" in json.dumps(e).lower()
        for e in last_entries
    )

    # Check for natural end — last assistant message has no tool calls
    assistant_msgs = [
        e for e in entries
        if e.get("type") == "assistant" and "message" in e
    ]

    natural_end = False
    last_msg_text = ""
    if assistant_msgs:
        last_msg = assistant_msgs[-1]
        content = last_msg.get("message", {}).get("content", [])
        has_tool_use = any(b.get("type") == "tool_use" for b in content)
        text_blocks = [b.get("text", "") for b in content if b.get("type") == "text"]
        last_msg_text = " ".join(text_blocks)
        natural_end = not has_tool_use

    # Check for explicit result/system messages at end
    last_type = entries[-1].get("type", "unknown") if entries else "unknown"
    result_entry = entries[-1] if entries else {}

    # Check if the session includes a "result" type entry
    result_entries = [e for e in entries if e.get("type") == "result"]
    has_result = len(result_entries) > 0
    result_data = result_entries[-1] if result_entries else {}

    # Check stop reason from last assistant message
    stop_reason = ""
    if assistant_msgs:
        stop_reason = assistant_msgs[-1].get("message", {}).get("stop_reason", "")

    # Determine termination mechanism
    mechanism = "unknown"
    if has_result:
        # claude -p produces a "result" entry at the end
        result_reason = result_data.get("subtype", result_data.get("reason", ""))
        if "budget" in str(result_data).lower():
            mechanism = "budget_cap"
        elif natural_end:
            mechanism = "natural_end"
        else:
            mechanism = f"result_entry:{result_reason}"
    elif budget_exhausted:
        mechanism = "budget_cap"
    elif natural_end:
        mechanism = "natural_end"

    # Wallclock time
    first_ts = None
    last_ts = None
    for e in entries:
        ts = e.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

    wallclock_s = None
    if first_ts and last_ts:
        from datetime import datetime
        try:
            d1 = datetime.fromisoformat(first_ts[:19])
            d2 = datetime.fromisoformat(last_ts[:19])
            wallclock_s = int((d2 - d1).total_seconds())
        except (ValueError, TypeError):
            pass

    info = {
        "terminated": True,
        "mechanism": mechanism,
        "natural_end": natural_end,
        "budget_exhausted": budget_exhausted,
        "has_result_entry": has_result,
        "stop_reason": stop_reason,
        "last_type": last_type,
        "last_msg_text": last_msg_text[:200] if last_msg_text else "",
        "total_entries": len(entries),
        "assistant_msgs": len(assistant_msgs),
        "wallclock_s": wallclock_s,
    }

    print(f"  [{label}] Mechanism: {mechanism}")
    print(f"  [{label}] Natural end (last msg has no tool calls): {natural_end}")
    print(f"  [{label}] Budget exhausted: {budget_exhausted}")
    print(f"  [{label}] Stop reason: {stop_reason}")
    print(f"  [{label}] Has result entry: {has_result}")
    print(f"  [{label}] Last entry type: {last_type}")
    print(f"  [{label}] Total entries: {len(entries)}, assistant msgs: {len(assistant_msgs)}")
    print(f"  [{label}] Wallclock: {wallclock_s}s" if wallclock_s else f"  [{label}] Wallclock: ?")
    if last_msg_text:
        print(f"  [{label}] Last text: {last_msg_text[:150]}")

    return info


def run_experiment(
    runner: TestRunner,
    fixture: str,
    pipeline_dir: str,
    prompt: str,
    label: str,
    log_name: str,
    budget: str = "3.00",
) -> dict:
    """Run a single spike experiment and return analysis."""
    print(f"\n--- Experiment {label} ---")
    print(f"  Prompt: {prompt}")
    print(f"  Fixture: {fixture}")
    print(f"  Budget: ${budget}")

    # Fresh project for each experiment (unique dir to avoid commit collisions)
    project_dir = runner.test_dir / f"test-project-{label}"
    subprocess.run(["git", "init", str(project_dir)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=project_dir,
    )
    runner.test_project_dir = project_dir
    setup_fixture(runner, fixture, pipeline_dir)
    install_agents(runner)
    git_add_commit(runner.test_project_dir, f"setup: {label} fixture")

    # Run the first officer
    exit_code = run_first_officer(
        runner,
        prompt,
        extra_args=["--max-budget-usd", budget],
        log_name=log_name,
    )

    print(f"\n  [{label}] Exit code: {exit_code}")

    # Check entity state after run
    entity_file = runner.test_project_dir / pipeline_dir / "test-entity.md"
    archive_file = runner.test_project_dir / pipeline_dir / "_archive" / "test-entity.md"

    final_file = archive_file if archive_file.is_file() else entity_file
    entity_status = "not_found"
    if final_file.is_file():
        fm = read_entity_frontmatter(final_file)
        entity_status = fm.get("status", "unknown")
        archived = final_file == archive_file
        print(f"  [{label}] Entity status: {entity_status} (archived: {archived})")
    else:
        print(f"  [{label}] Entity file not found!")

    # Analyze termination
    log_path = runner.log_dir / log_name
    analysis = analyze_termination(log_path, label)
    analysis["exit_code"] = exit_code
    analysis["entity_status"] = entity_status

    # Write detailed log analysis
    log_parser = LogParser(log_path)
    log_parser.write_fo_texts(runner.log_dir / f"{label}-texts.txt")
    log_parser.write_agent_prompt(runner.log_dir / f"{label}-agent-prompts.txt")

    return analysis


def main():
    runner = TestRunner("Spike: Session Termination in claude -p", keep_test_dir=True)

    results = {}

    # Experiment A: Baseline — does the FO terminate naturally?
    results["A"] = run_experiment(
        runner,
        fixture="spike-no-gate",
        pipeline_dir="spike-workflow",
        prompt="Report workflow status.",
        label="A-baseline",
        log_name="spike-a.jsonl",
    )

    # Experiment B: Prompt-directed termination
    results["B"] = run_experiment(
        runner,
        fixture="spike-no-gate",
        pipeline_dir="spike-workflow",
        prompt="Process test-entity through all stages, then stop.",
        label="B-directed",
        log_name="spike-b.jsonl",
    )

    # Experiment C: Gated workflow, prompt-directed
    results["C"] = run_experiment(
        runner,
        fixture="spike-gated",
        pipeline_dir="spike-workflow",
        prompt="Process test-entity through all stages, then stop.",
        label="C-gated",
        log_name="spike-c.jsonl",
    )

    # --- Summary ---
    print("\n\n=== SPIKE SUMMARY ===\n")

    for exp_id, data in results.items():
        print(f"Experiment {exp_id}:")
        print(f"  Mechanism:     {data.get('mechanism', '?')}")
        print(f"  Natural end:   {data.get('natural_end', '?')}")
        print(f"  Entity status: {data.get('entity_status', '?')}")
        print(f"  Exit code:     {data.get('exit_code', '?')}")
        print(f"  Wallclock:     {data.get('wallclock_s', '?')}s")
        print()

    # Determine answers to the four spike questions
    print("=== SPIKE ANSWERS ===\n")

    # Q1: What controls session termination?
    natural_count = sum(1 for d in results.values() if d.get("mechanism") == "natural_end")
    budget_count = sum(1 for d in results.values() if d.get("mechanism") == "budget_cap")
    print(f"Q1: What controls session termination in claude -p?")
    print(f"    Natural end: {natural_count}/3 experiments")
    print(f"    Budget cap:  {budget_count}/3 experiments")
    print()

    # Q2: Can prompt instructions reliably trigger termination?
    b_natural = results["B"].get("mechanism") == "natural_end"
    b_done = results["B"].get("entity_status") == "done"
    print(f"Q2: Can prompt instructions reliably trigger termination?")
    print(f"    Exp B (directed): natural_end={b_natural}, entity_done={b_done}")
    print()

    # Q3: Does -p prompt override initialPrompt?
    # If the entity advanced past backlog in B or C, the FO saw the user prompt
    b_advanced = results["B"].get("entity_status") not in ("backlog", "not_found")
    c_advanced = results["C"].get("entity_status") not in ("backlog", "not_found")
    print(f"Q3: Does -p prompt reach the FO (override/supplement initialPrompt)?")
    print(f"    Exp B advanced: {b_advanced}")
    print(f"    Exp C advanced: {c_advanced}")
    print()

    # Q4: Can template prose override the event loop?
    # If A hangs but B terminates, prompt prose can override
    a_natural = results["A"].get("mechanism") == "natural_end"
    print(f"Q4: Can prompt override event loop behavior?")
    print(f"    Exp A (baseline, no 'stop' instruction): natural_end={a_natural}")
    print(f"    Exp B (with 'then stop'): natural_end={b_natural}")
    print()

    print(f"Test dir preserved at: {runner.test_dir}")
    print()

    # Write summary to file
    summary_path = runner.log_dir / "spike-summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()
