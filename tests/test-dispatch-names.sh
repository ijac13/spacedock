# ABOUTME: E2E test for dispatch name uniqueness across stages.
# ABOUTME: Verifies each Agent() dispatch uses a unique name to prevent shutdown collisions.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE_DIR="$REPO_ROOT/tests/fixtures/no-gate-pipeline"
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

echo "=== Dispatch Name Uniqueness E2E Test ==="
echo "Repo root:    $REPO_ROOT"
echo "Fixture dir:  $FIXTURE_DIR"
echo "Test dir:     $TEST_DIR"
echo ""

# --- Phase 1: Set up test project from static fixture ---

echo "--- Phase 1: Set up test project from fixture ---"

cd "$TEST_DIR"
git init test-project >/dev/null 2>&1
cd "$TEST_DIR/test-project"
git commit --allow-empty -m "init" >/dev/null 2>&1

# Copy pipeline fixture
mkdir -p dispatch-pipeline
cp "$FIXTURE_DIR/README.md" dispatch-pipeline/
cp "$FIXTURE_DIR/dispatch-name-test.md" dispatch-pipeline/
cp "$FIXTURE_DIR/status" dispatch-pipeline/
chmod +x dispatch-pipeline/status

# Generate first-officer agent from template
mkdir -p .claude/agents
sed \
  -e 's|__MISSION__|Dispatch name uniqueness test|g' \
  -e 's|__DIR__|dispatch-pipeline|g' \
  -e 's|__DIR_BASENAME__|dispatch-pipeline|g' \
  -e 's|__PROJECT_NAME__|dispatch-test|g' \
  -e 's|__ENTITY_LABEL__|task|g' \
  -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
  -e 's|__CAPTAIN__|CL|g' \
  -e 's|__FIRST_STAGE__|backlog|g' \
  -e 's|__LAST_STAGE__|done|g' \
  -e 's|__SPACEDOCK_VERSION__|test|g' \
  "$REPO_ROOT/templates/first-officer.md" > .claude/agents/first-officer.md

git add -A && git commit -m "setup: no-gate pipeline fixture" >/dev/null 2>&1

echo ""
echo "[Fixture Setup]"

# Verify the generated agent has stage in the dispatch name pattern
if grep -qE 'name=.*\{.*stage' .claude/agents/first-officer.md; then
  pass "generated first-officer has stage in dispatch name"
else
  fail "generated first-officer has stage in dispatch name"
  echo "  FATAL: Dispatch name fix missing from generated agent. Aborting."
  trap - EXIT
  exit 1
fi

# Verify the fixture pipeline is valid
if bash dispatch-pipeline/status >/dev/null 2>&1; then
  pass "status script runs without errors"
else
  fail "status script runs without errors"
fi

if bash dispatch-pipeline/status --next 2>/dev/null | grep -q "dispatch-name-test"; then
  pass "status --next detects dispatchable entity"
else
  fail "status --next detects dispatchable entity"
fi

echo ""

# --- Phase 2: Run the first officer ---

echo "--- Phase 2: Run first officer (this takes ~60-180s) ---"

cd "$TEST_DIR/test-project"

FO_EXIT=0
claude -p "Process all tasks through the pipeline to completion." \
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

# --- Phase 3: Validate dispatch name uniqueness ---

echo "--- Phase 3: Validation ---"

# Extract all Agent() dispatch names from the stream-json log
python3 -c "
import json, sys

dispatch_names = []

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
                        agent_input = block.get('input', {})
                        name = agent_input.get('name', '')
                        if name:
                            dispatch_names.append(name)
        except:
            pass

with open('$TEST_DIR/dispatch-names.txt', 'w') as f:
    for name in dispatch_names:
        f.write(name + '\n')

# Write summary
with open('$TEST_DIR/dispatch-summary.txt', 'w') as f:
    f.write('total: %d\n' % len(dispatch_names))
    f.write('unique: %d\n' % len(set(dispatch_names)))
    if len(dispatch_names) != len(set(dispatch_names)):
        from collections import Counter
        dupes = [n for n, c in Counter(dispatch_names).items() if c > 1]
        f.write('duplicates: %s\n' % ', '.join(dupes))
" 2>/dev/null

echo ""
echo "[Dispatch Names]"

# Show all dispatch names found
if [ -f "$TEST_DIR/dispatch-names.txt" ] && [ -s "$TEST_DIR/dispatch-names.txt" ]; then
  echo "  Names found:"
  while IFS= read -r name; do
    echo "    - $name"
  done < "$TEST_DIR/dispatch-names.txt"
else
  echo "  (no dispatch names found)"
fi

echo ""
echo "[Uniqueness Checks]"

# Check 1: At least 2 dispatches occurred (entity should go through work and review)
DISPATCH_COUNT=$(wc -l < "$TEST_DIR/dispatch-names.txt" 2>/dev/null | tr -d ' ')
if [ "${DISPATCH_COUNT:-0}" -ge 2 ]; then
  pass "at least 2 dispatches occurred ($DISPATCH_COUNT total)"
else
  fail "at least 2 dispatches occurred (got ${DISPATCH_COUNT:-0} — need >=2 to test uniqueness)"
fi

# Check 2: All dispatch names are unique (no duplicates)
if [ "${DISPATCH_COUNT:-0}" -gt 0 ]; then
  UNIQUE_COUNT=$(sort -u "$TEST_DIR/dispatch-names.txt" | wc -l | tr -d ' ')
  if [ "$DISPATCH_COUNT" = "$UNIQUE_COUNT" ]; then
    pass "all dispatch names are unique ($UNIQUE_COUNT unique out of $DISPATCH_COUNT)"
  else
    fail "all dispatch names are unique ($UNIQUE_COUNT unique out of $DISPATCH_COUNT — duplicates found)"
    if [ -f "$TEST_DIR/dispatch-summary.txt" ]; then
      grep "^duplicates:" "$TEST_DIR/dispatch-summary.txt" | sed 's/^/    /'
    fi
  fi
else
  fail "all dispatch names are unique (no dispatches to check)"
fi

# Check 3: Dispatch names contain stage identifiers
NAMES_WITH_STAGE=0
while IFS= read -r name; do
  # Check if the name contains a known stage name as a suffix component
  if echo "$name" | grep -qE '-(work|review|implementation|ideation|validation)$'; then
    NAMES_WITH_STAGE=$((NAMES_WITH_STAGE + 1))
  fi
done < "$TEST_DIR/dispatch-names.txt" 2>/dev/null

if [ "${DISPATCH_COUNT:-0}" -gt 0 ] && [ "$NAMES_WITH_STAGE" -eq "${DISPATCH_COUNT:-0}" ]; then
  pass "all dispatch names include stage suffix ($NAMES_WITH_STAGE of $DISPATCH_COUNT)"
else
  fail "all dispatch names include stage suffix ($NAMES_WITH_STAGE of ${DISPATCH_COUNT:-0})"
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
  echo "  Test dir:         $TEST_DIR"
  echo "  FO log:           $TEST_DIR/fo-log.jsonl"
  echo "  Dispatch names:   $TEST_DIR/dispatch-names.txt"
  echo "  Dispatch summary: $TEST_DIR/dispatch-summary.txt"
  # Don't clean up on failure so logs can be inspected
  trap - EXIT
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
