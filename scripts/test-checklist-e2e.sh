# ABOUTME: E2E test for the checklist protocol in the first-officer template.
# ABOUTME: Commissions a pipeline, runs the first officer, validates ensign checklist compliance.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
FAILURES=0
PASSES=0

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

pass() {
  PASSES=$((PASSES + 1))
  echo "  PASS: $1"
}

fail() {
  FAILURES=$((FAILURES + 1))
  echo "  FAIL: $1"
}

echo "=== Checklist Protocol E2E Test ==="
echo "Repo root:  $REPO_ROOT"
echo "Test dir:   $TEST_DIR"
echo ""

# --- Phase 1: Commission a test pipeline ---

echo "--- Phase 1: Commission test pipeline (this takes ~30-60s) ---"

cd "$TEST_DIR"
git init test-project >/dev/null 2>&1
cd "$TEST_DIR/test-project"
git commit --allow-empty -m "init" >/dev/null 2>&1

PROMPT="/spacedock:commission

All inputs for this workflow:
- Mission: Track tasks through stages
- Entity: A task
- Stages: backlog → work → done
- Approval gates: none
- Seed entities:
  1. test-checklist — Verify checklist protocol works (score: 25/25)
- Location: ./checklist-test/

Skip interactive questions and confirmation — use these inputs directly. Make reasonable assumptions for anything not specified. Do NOT run the pilot phase — just generate the files and stop."

CLAUDE_EXIT=0
claude -p "$PROMPT" \
  --plugin-dir "$REPO_ROOT" \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  2>&1 > "$TEST_DIR/commission-log.jsonl" || CLAUDE_EXIT=$?

echo ""
if [ $CLAUDE_EXIT -ne 0 ]; then
  echo "WARNING: commission exited with code $CLAUDE_EXIT"
fi

echo "[Commission Output]"
if [ ! -f "$TEST_DIR/test-project/checklist-test/test-checklist.md" ]; then
  fail "commission produced test-checklist.md"
  echo "  FATAL: Cannot proceed without commissioned pipeline. Aborting."
  exit 1
else
  pass "commission produced test-checklist.md"
fi

if [ ! -f "$TEST_DIR/test-project/.claude/agents/first-officer.md" ]; then
  fail "commission produced first-officer.md"
  echo "  FATAL: Cannot proceed without first-officer agent. Aborting."
  exit 1
else
  pass "commission produced first-officer.md"
fi

# Add acceptance criteria to the test entity
cat >> "$TEST_DIR/test-project/checklist-test/test-checklist.md" << 'AC'

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
AC

# Commit so the first officer has a clean working tree
cd "$TEST_DIR/test-project"
git add -A && git commit -m "commission: initial pipeline with acceptance criteria" >/dev/null 2>&1

echo ""

# --- Phase 2: Run the first officer ---

echo "--- Phase 2: Run first officer (this takes ~60-120s) ---"

cd "$TEST_DIR/test-project"

FO_EXIT=0
claude -p "Process all entities through the pipeline. Process one entity through one stage, then stop." \
  --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > "$TEST_DIR/fo-log.jsonl" || FO_EXIT=$?

echo ""
if [ $FO_EXIT -ne 0 ]; then
  echo "WARNING: first officer exited with code $FO_EXIT"
fi

# --- Phase 3: Validate from the stream-json log ---
#
# The first officer may call TeamDelete before the script can read the
# team inbox. Instead, we validate from the stream-json log which captures:
#   - The Agent() dispatch prompt (contains the checklist)
#   - The first officer's checklist review text (mentions items and statuses)
#
# We use python3 to parse the JSONL and extract the relevant fields.

echo "--- Phase 3: Validation ---"

# Extract validation data from the log
python3 -c "
import json, sys

agent_prompt = ''
fo_texts = []

with open('$TEST_DIR/fo-log.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'tool_use' and block.get('name') == 'Agent':
                        agent_prompt = block.get('input', {}).get('prompt', '')
                    if block.get('type') == 'text':
                        fo_texts.append(block['text'])
        except:
            pass

# Write extracted data for the shell checks
with open('$TEST_DIR/agent-prompt.txt', 'w') as f:
    f.write(agent_prompt)
with open('$TEST_DIR/fo-texts.txt', 'w') as f:
    f.write('\n'.join(fo_texts))
" 2>/dev/null

echo ""
echo "[Ensign Dispatch Prompt]"

# Check 1: Dispatch prompt contains ### Completion checklist section
if grep -qi "Completion checklist\|completion checklist" "$TEST_DIR/agent-prompt.txt" 2>/dev/null; then
  pass "dispatch prompt contains Completion checklist section"
else
  fail "dispatch prompt contains Completion checklist section"
fi

# Check 2: Dispatch prompt contains numbered checklist items with DONE/SKIPPED/FAILED instructions
if grep -qiE "DONE.*SKIPPED.*FAILED|Mark each.*DONE" "$TEST_DIR/agent-prompt.txt" 2>/dev/null; then
  pass "dispatch prompt has DONE/SKIPPED/FAILED instructions"
else
  fail "dispatch prompt has DONE/SKIPPED/FAILED instructions"
fi

# Check 3: Dispatch prompt includes entity acceptance criteria items
if grep -qiE "hello|UTF-8" "$TEST_DIR/agent-prompt.txt" 2>/dev/null; then
  pass "dispatch prompt includes entity acceptance criteria"
else
  fail "dispatch prompt includes entity acceptance criteria"
fi

# Check 4: Dispatch prompt includes stage requirement items (from README Outputs)
# The stage's Outputs say something about "deliverables" or "summary"
if grep -qiE "deliverable|summary" "$TEST_DIR/agent-prompt.txt" 2>/dev/null; then
  pass "dispatch prompt includes stage requirement items"
else
  fail "dispatch prompt includes stage requirement items"
fi

echo ""
echo "[First Officer Checklist Review]"

# Check 5: First officer performed checklist review after ensign completion
if grep -qiE "checklist review|checklist.*complete|all.*items.*DONE|items reported" "$TEST_DIR/fo-texts.txt" 2>/dev/null; then
  pass "first officer performed checklist review"
else
  fail "first officer performed checklist review"
fi

# Check 6: First officer mentions DONE/SKIPPED/FAILED in its review
if grep -qiE "DONE|SKIPPED|FAILED" "$TEST_DIR/fo-texts.txt" 2>/dev/null; then
  pass "first officer review references item statuses"
else
  fail "first officer review references item statuses"
fi

# Check 7: Dispatch prompt has structured completion message template
if grep -qiE "### Checklist|### Summary" "$TEST_DIR/agent-prompt.txt" 2>/dev/null; then
  pass "dispatch prompt has structured completion message template"
else
  fail "dispatch prompt has structured completion message template"
fi

# --- Results ---

echo ""
echo "=== Results ==="
TOTAL=$((PASSES + FAILURES))
echo "  $PASSES passed, $FAILURES failed (out of $TOTAL checks)"
echo ""

if [ $FAILURES -gt 0 ]; then
  echo "RESULT: FAIL"
  echo ""
  echo "Debug info:"
  echo "  Test dir:    $TEST_DIR"
  echo "  FO log:      $TEST_DIR/fo-log.jsonl"
  echo "  Commission:  $TEST_DIR/commission-log.jsonl"
  echo "  Agent prompt: $TEST_DIR/agent-prompt.txt"
  echo "  FO texts:    $TEST_DIR/fo-texts.txt"
  # Don't clean up on failure so logs can be inspected
  trap - EXIT
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
