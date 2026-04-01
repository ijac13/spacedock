#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Spike experiments for session termination behavior in claude -p mode.
# ABOUTME: Runs 3 experiments (A: baseline, B: prompt-directed, C: gated) and captures logs.

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, LogParser, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit,
    read_entity_frontmatter,
)


def analyze_termination(log_path: Path) -> dict:
    """Analyze a stream-json log for termination signals."""
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

    result = {
        "total_entries": len(entries),
        "assistant_messages": 0,
        "tool_calls": 0,
        "last_assistant_text": "",
        "has_result_message": False,
        "result_text": "",
        "budget_exceeded": False,
        "natural_end": False,
        "last_type": "",
        "end_turn_count": 0,
        "last_stop_reason": "",
    }

    for entry in entries:
        msg_type = entry.get("type", "")
        result["last_type"] = msg_type

        if msg_type == "assistant" and "message" in entry:
            result["assistant_messages"] += 1
            content = entry["message"].get("content", [])
            has_tool_call = False
            for block in content:
                if block.get("type") == "text":
                    result["last_assistant_text"] = block["text"][:500]
                if block.get("type") == "tool_use":
                    has_tool_call = True
                    result["tool_calls"] += 1

            stop_reason = entry["message"].get("stop_reason", "")
            result["last_stop_reason"] = stop_reason
            if stop_reason == "end_turn":
                result["end_turn_count"] += 1
                if not has_tool_call:
                    result["natural_end"] = True

        if msg_type == "error":
            error_text = json.dumps(entry)
            if "budget" in error_text.lower() or "limit" in error_text.lower():
                result["budget_exceeded"] = True

        if msg_type == "result":
            result["has_result_message"] = True
            result_text = str(entry.get("result", ""))
            result["result_text"] = result_text[:500]
            if "budget" in result_text.lower():
                result["budget_exceeded"] = True

    return result


def create_experiment_project(t, experiment_name):
    """Create a uniquely-named test project for one experiment."""
    import subprocess, tempfile
    project_dir = t.test_dir / f"test-project-{experiment_name.lower()}"
    subprocess.run(["git", "init", str(project_dir)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=project_dir,
    )
    t.test_project_dir = project_dir
    return project_dir


def run_experiment(t, name, fixture, pipeline_dir, prompt, extra_args=None):
    """Run a single spike experiment and return analysis."""
    print(f"\n{'='*60}")
    print(f"EXPERIMENT {name}")
    print(f"{'='*60}")
    print(f"Fixture: {fixture}")
    print(f"Prompt: {prompt}")
    if extra_args:
        print(f"Extra args: {extra_args}")
    print()

    # Fresh test project for each experiment
    create_experiment_project(t, name)
    setup_fixture(t, fixture, pipeline_dir)
    install_agents(t)
    git_add_commit(t.test_project_dir, f"setup: {name} experiment fixture")

    log_name = f"exp-{name.lower()}-log.jsonl"

    all_args = ["--max-budget-usd", "3.00"]
    if extra_args:
        all_args.extend(extra_args)

    start = time.time()
    exit_code = run_first_officer(t, prompt, extra_args=all_args, log_name=log_name)
    elapsed = time.time() - start

    log_path = t.log_dir / log_name
    analysis = analyze_termination(log_path)

    # Check entity final state
    entity_file = t.test_project_dir / pipeline_dir / "test-entity.md"
    entity_fm = {}
    if entity_file.is_file():
        entity_fm = read_entity_frontmatter(entity_file)

    # Write FO texts for inspection
    parser = LogParser(log_path)
    texts_path = t.log_dir / f"exp-{name.lower()}-texts.txt"
    parser.write_fo_texts(texts_path)

    print(f"\n--- Experiment {name} Results ---")
    print(f"  Exit code:         {exit_code}")
    print(f"  Elapsed:           {elapsed:.1f}s")
    print(f"  Assistant msgs:    {analysis['assistant_messages']}")
    print(f"  Tool calls:        {analysis['tool_calls']}")
    print(f"  Natural end:       {analysis['natural_end']}")
    print(f"  Budget exceeded:   {analysis['budget_exceeded']}")
    print(f"  Has result msg:    {analysis['has_result_message']}")
    print(f"  Last type:         {analysis['last_type']}")
    print(f"  Entity status:     {entity_fm.get('status', 'N/A')}")
    print(f"  Last text preview: {analysis['last_assistant_text'][:200]}")
    print()

    return {
        "name": name,
        "exit_code": exit_code,
        "elapsed": elapsed,
        "analysis": analysis,
        "entity_status": entity_fm.get("status", "N/A"),
    }


def main():
    t = TestRunner("Spike: Session Termination in claude -p", keep_test_dir=True)

    results = {}

    # Experiment A: Baseline — does the FO terminate naturally?
    results["A"] = run_experiment(
        t, "A",
        fixture="spike-no-gate",
        pipeline_dir="spike-no-gate",
        prompt="Report workflow status.",
    )

    # Experiment B: Prompt-directed termination
    results["B"] = run_experiment(
        t, "B",
        fixture="spike-no-gate",
        pipeline_dir="spike-no-gate",
        prompt="Process test-entity through all stages, then stop.",
    )

    # Experiment C: Gated workflow, prompt-directed
    results["C"] = run_experiment(
        t, "C",
        fixture="spike-gated",
        pipeline_dir="spike-gated",
        prompt="Process test-entity through all stages, then stop.",
    )

    # Summary
    print("\n" + "="*60)
    print("SPIKE SUMMARY")
    print("="*60)

    for name, r in results.items():
        terminated = r["analysis"]["natural_end"] and not r["analysis"]["budget_exceeded"]
        print(f"\n  Experiment {name}:")
        print(f"    Terminated naturally: {terminated}")
        print(f"    Exit code: {r['exit_code']}, Elapsed: {r['elapsed']:.1f}s")
        print(f"    Entity final status: {r['entity_status']}")

    # Write summary JSON
    summary_path = t.log_dir / "spike-summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Full summary: {summary_path}")
    print(f"  Log dir: {t.log_dir}")

    # Answer the spike questions
    print("\n" + "="*60)
    print("SPIKE QUESTION ANSWERS")
    print("="*60)

    a_natural = results["A"]["analysis"]["natural_end"] and not results["A"]["analysis"]["budget_exceeded"]
    b_natural = results["B"]["analysis"]["natural_end"] and not results["B"]["analysis"]["budget_exceeded"]
    c_natural = results["C"]["analysis"]["natural_end"] and not results["C"]["analysis"]["budget_exceeded"]

    print(f"\n  Q1: What controls session termination in claude -p?")
    if a_natural or b_natural:
        print(f"    -> LLM-driven: The LLM produces a final turn with no tool calls.")
    else:
        print(f"    -> Budget exhaustion: Sessions run until --max-budget-usd is hit.")

    print(f"\n  Q2: Can prompt instructions reliably trigger termination?")
    if b_natural and not a_natural:
        print(f"    -> YES: Prompt-directed termination works (B terminated, A did not).")
    elif b_natural and a_natural:
        print(f"    -> MAYBE: Both A and B terminated naturally. Prompt may not be needed.")
    else:
        print(f"    -> NO: Prompt-directed termination is unreliable.")

    print(f"\n  Q3: Does -p prompt override initialPrompt?")
    b_status = results["B"]["entity_status"]
    if b_status != "backlog":
        print(f"    -> YES: Entity advanced (status={b_status}), so -p prompt reached the FO.")
    else:
        print(f"    -> UNCLEAR: Entity stayed in backlog. -p prompt may not have overridden initialPrompt.")

    print(f"\n  Q4: Can template prose override the event loop?")
    if b_natural:
        print(f"    -> YES: 'then stop' in the prompt overrode the event loop's 'until captain ends session'.")
    else:
        print(f"    -> NO: Event loop prose won.")

    print()


if __name__ == "__main__":
    main()
