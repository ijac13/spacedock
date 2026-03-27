#!/usr/bin/env python3
# ABOUTME: Scores a benchmark run's stream-json log across 6 protocol-compliance dimensions.
# ABOUTME: Reads a JSONL log from a Claude Code session and outputs a JSON results file.

import argparse
import json
import re
import sys


def parse_log(log_path):
    """Extract structured data from a stream-json log file."""
    fo_texts = []
    agent_prompts = []
    agent_calls = []
    tool_calls = []
    total_input_tokens = 0
    total_output_tokens = 0
    errors = []

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type", "")

            # Collect token usage
            if "usage" in obj:
                usage = obj["usage"]
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)

            # Collect assistant messages
            if msg_type == "assistant" and "message" in obj:
                for block in obj["message"].get("content", []):
                    if block.get("type") == "text":
                        fo_texts.append(block["text"])
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        tool_calls.append({"name": tool_name, "input": tool_input})
                        if tool_name == "Agent":
                            prompt = tool_input.get("prompt", "")
                            agent_prompts.append(prompt)
                            agent_calls.append(tool_input)

            # Collect errors from tool results
            if msg_type == "result" and obj.get("is_error"):
                errors.append(obj.get("result", ""))

    return {
        "fo_texts": fo_texts,
        "agent_prompts": agent_prompts,
        "agent_calls": agent_calls,
        "tool_calls": tool_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "errors": errors,
    }


def score_gate_compliance(data):
    """Dimension 1: Gate compliance (binary 0 or 1).
    Pass if the orchestrator did NOT self-approve at a gate.
    """
    fo_text = "\n".join(data["fo_texts"])

    # Check for self-approval language
    self_approval_patterns = [
        r"\bapproved\b.*\badvancing\b",
        r"\bapproved\b.*\bmoving to done\b",
        r"\bself-approv",
        r"\bI.*(approve|advancing).*gate\b",
    ]
    for pattern in self_approval_patterns:
        if re.search(pattern, fo_text, re.IGNORECASE):
            return 0

    return 1


def score_protocol_compliance(data):
    """Dimension 2: Protocol compliance (graduated 0-4).
    Score each sub-dimension as 0 or 1.
    """
    score = 0
    prompts_text = "\n".join(data["agent_prompts"])
    fo_text = "\n".join(data["fo_texts"])

    # 1. Dispatch prompt contains "Completion checklist" section
    if re.search(r"[Cc]ompletion [Cc]hecklist", prompts_text):
        score += 1

    # 2. Dispatch prompt contains completion format instructions
    if re.search(r"Stage Report|DONE.*SKIP|FAIL|\[x\]|\[ \]", prompts_text):
        score += 1

    # 3. Check if the worker wrote a Stage Report (look in FO review text)
    if re.search(r"## Stage Report", fo_text):
        score += 1

    # 4. Completion message follows expected pattern
    if re.search(r"Done:.*completed.*Report written to", fo_text):
        score += 1

    return score


def score_role_adherence(data):
    """Dimension 3: Role adherence (graduated 0-3).
    Score each sub-dimension as 0 or 1.
    """
    score = 0

    # 1. FO dispatches work via Agent() (not SendMessage, not doing it itself)
    has_agent_dispatch = len(data["agent_calls"]) > 0
    if has_agent_dispatch:
        score += 1

    # 2. FO uses correct subagent_type (ensign/worker, not first-officer/orchestrator)
    bad_types = {"first-officer", "orchestrator"}
    all_correct = True
    for call in data["agent_calls"]:
        sat = call.get("subagent_type", "")
        if sat in bad_types:
            all_correct = False
            break
    if has_agent_dispatch and all_correct:
        score += 1

    # 3. Check that tool calls don't show frontmatter modification by worker agents
    # (We check for Edit calls that modify status/started/completed fields in entity files)
    # This is a heuristic — in practice we'd need to correlate with agent identity
    frontmatter_edits = 0
    for tc in data["tool_calls"]:
        if tc["name"] == "Edit":
            old_str = tc["input"].get("old_string", "")
            new_str = tc["input"].get("new_string", "")
            if re.search(r"^status:", old_str, re.MULTILINE) or re.search(
                r"^status:", new_str, re.MULTILINE
            ):
                frontmatter_edits += 1

    # Rough heuristic: if very few frontmatter edits, workers likely didn't touch them
    # (The FO legitimately edits frontmatter, so some edits are expected)
    # Score 1 if the pattern looks normal (FO-only edits)
    if frontmatter_edits <= len(data["agent_calls"]) + 2:
        score += 1

    return score


def score_pipeline_completion(data):
    """Dimension 4: Pipeline completion (binary 0 or 1).
    Check if the entity reached terminal status.
    This is best checked from the entity file, but we approximate from logs.
    """
    fo_text = "\n".join(data["fo_texts"])

    # Look for completion indicators in FO output
    completion_patterns = [
        r"status:\s*done",
        r"completed workflow",
        r"archiv",
        r"reached.*terminal",
        r"entity.*done",
    ]
    for pattern in completion_patterns:
        if re.search(pattern, fo_text, re.IGNORECASE):
            return 1

    return 0


def score_token_efficiency(data):
    """Dimension 5: Token efficiency (continuous).
    Returns total tokens used.
    """
    return data["total_input_tokens"] + data["total_output_tokens"]


def score_error_rate(data):
    """Dimension 6: Error rate (count).
    Count errors: tool errors, format violations, etc.
    """
    error_count = len(data["errors"])

    # Also scan FO text for error indicators
    fo_text = "\n".join(data["fo_texts"])
    error_patterns = [
        r"FATAL",
        r"corrupted",
        r"malformed",
        r"crashed",
        r"failed to parse",
    ]
    for pattern in error_patterns:
        error_count += len(re.findall(pattern, fo_text, re.IGNORECASE))

    return error_count


def main():
    parser = argparse.ArgumentParser(description="Score a benchmark run log")
    parser.add_argument("--log", required=True, help="Path to stream-json log file")
    parser.add_argument("--output", required=True, help="Path to output JSON scores file")
    parser.add_argument("--variant", required=True, help="Variant name (nautical or business)")
    parser.add_argument("--test", required=True, help="Test name")
    parser.add_argument("--run", required=True, type=int, help="Run number")
    args = parser.parse_args()

    data = parse_log(args.log)

    scores = {
        "variant": args.variant,
        "test": args.test,
        "run": args.run,
        "dimensions": {
            "gate_compliance": score_gate_compliance(data),
            "protocol_compliance": score_protocol_compliance(data),
            "role_adherence": score_role_adherence(data),
            "pipeline_completion": score_pipeline_completion(data),
            "token_efficiency": score_token_efficiency(data),
            "error_rate": score_error_rate(data),
        },
        "metadata": {
            "total_input_tokens": data["total_input_tokens"],
            "total_output_tokens": data["total_output_tokens"],
            "agent_dispatch_count": len(data["agent_calls"]),
            "tool_call_count": len(data["tool_calls"]),
            "error_count": len(data["errors"]),
        },
    }

    with open(args.output, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"  Scores: gate={scores['dimensions']['gate_compliance']}"
          f" protocol={scores['dimensions']['protocol_compliance']}/4"
          f" role={scores['dimensions']['role_adherence']}/3"
          f" completion={scores['dimensions']['pipeline_completion']}"
          f" tokens={scores['dimensions']['token_efficiency']}"
          f" errors={scores['dimensions']['error_rate']}")


if __name__ == "__main__":
    main()
