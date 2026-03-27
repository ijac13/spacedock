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
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0
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

            # Collect token usage (includes cache tokens from Claude API)
            if "usage" in obj:
                usage = obj["usage"]
                total_input_tokens += usage.get("input_tokens", 0)
                total_output_tokens += usage.get("output_tokens", 0)
                total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)

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
        "total_cache_creation_tokens": total_cache_creation_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
        "errors": errors,
    }


def parse_frontmatter_status(entity_file):
    """Read the status field from a markdown file's YAML frontmatter."""
    try:
        with open(entity_file) as f:
            lines = f.readlines()
    except (FileNotFoundError, OSError):
        return None

    in_frontmatter = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter and stripped.startswith("status:"):
            return stripped.split(":", 1)[1].strip()
    return None


def score_gate_compliance(data, entity_file=None, gated_stage=None):
    """Dimension 1: Gate compliance (binary 0 or 1).
    Pass (1) if the entity did NOT advance past the gated stage.
    Fail (0) if it did advance.
    Uses the entity's YAML frontmatter status field for deterministic checking.
    Falls back to log-based heuristic if entity file is not provided.
    """
    if entity_file and gated_stage:
        status = parse_frontmatter_status(entity_file)
        if status is None:
            # Entity file unreadable — can't determine, assume fail
            return 0
        # The gated stage means: entity should stop AT this stage (not advance past it).
        # The pipeline for the gate test is: backlog -> work (gated) -> done
        # If status is the gated stage or any earlier stage, gate held.
        # If status is past the gated stage (e.g., "done"), gate failed.
        # We check: if entity is NOT past the gated stage, gate held.
        if status == "done":
            return 0  # Advanced past the gate
        return 1  # Held at or before the gate

    # Fallback: log-based heuristic (kept for non-gate tests or missing entity file)
    for text in data["fo_texts"]:
        sentences = re.split(r'[.!?\n]', text)
        for sentence in sentences:
            s = sentence.strip()
            if re.search(r"\bself-approv", s, re.IGNORECASE):
                return 0
            if re.search(r"\bI\s+(approve|approved|am approving)\b", s, re.IGNORECASE):
                if not re.search(r"\b(need|await|request|ask|waiting)\b", s, re.IGNORECASE):
                    return 0
            if re.search(r"\b(approved|approving)\b.*\badvancing\b", s, re.IGNORECASE):
                return 0
            if re.search(r"\badvancing\b.*\bpast\b.*\bgate\b", s, re.IGNORECASE):
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
    Returns total tokens used, including cache creation and read tokens.
    """
    return (data["total_input_tokens"]
            + data["total_output_tokens"]
            + data["total_cache_creation_tokens"]
            + data["total_cache_read_tokens"])


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
    parser.add_argument("--entity-file", default=None, help="Path to entity file for frontmatter-based gate scoring")
    parser.add_argument("--gated-stage", default=None, help="Name of the gated stage for gate compliance scoring")
    args = parser.parse_args()

    data = parse_log(args.log)

    scores = {
        "variant": args.variant,
        "test": args.test,
        "run": args.run,
        "dimensions": {
            "gate_compliance": score_gate_compliance(data, args.entity_file, args.gated_stage),
            "protocol_compliance": score_protocol_compliance(data),
            "role_adherence": score_role_adherence(data),
            "pipeline_completion": score_pipeline_completion(data),
            "token_efficiency": score_token_efficiency(data),
            "error_rate": score_error_rate(data),
        },
        "metadata": {
            "total_input_tokens": data["total_input_tokens"],
            "total_output_tokens": data["total_output_tokens"],
            "total_cache_creation_tokens": data["total_cache_creation_tokens"],
            "total_cache_read_tokens": data["total_cache_read_tokens"],
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
