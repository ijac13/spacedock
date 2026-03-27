# ABOUTME: E2E test for dispatch name collision fix across consecutive stages.
# ABOUTME: Verifies an entity completes the full pipeline without agents getting killed by stale shutdowns.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE_DIR="$REPO_ROOT/tests/fixtures/multi-stage-pipeline"
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

echo "=== Dispatch Name Collision E2E Test ==="
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
  -e 's|__MISSION__|Dispatch name collision test|g' \
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

# --- Phase 3: Validate full pipeline completion ---

echo "--- Phase 3: Validation ---"

echo ""
echo "[Pipeline Completion]"

# The core test: did the entity make it through the full pipeline?
# Before the fix, the second dispatch would get killed by a stale shutdown
# request from the first, leaving the entity stuck mid-pipeline.

# Check entity file — it may have been archived to _archive/
ENTITY_FILE="$TEST_DIR/test-project/dispatch-pipeline/dispatch-name-test.md"
ARCHIVE_FILE="$TEST_DIR/test-project/dispatch-pipeline/_archive/dispatch-name-test.md"

if [ -f "$ARCHIVE_FILE" ]; then
  FINAL_FILE="$ARCHIVE_FILE"
  pass "entity was archived (reached terminal stage)"
elif [ -f "$ENTITY_FILE" ]; then
  FINAL_FILE="$ENTITY_FILE"
  echo "  INFO: entity still in main directory (not archived)"
else
  fail "entity file exists"
  FINAL_FILE=""
fi

# Check 1: Entity reached 'done' status
if [ -n "$FINAL_FILE" ]; then
  ENTITY_STATUS=$(head -15 "$FINAL_FILE" | grep "^status:" | head -1)
  ENTITY_STATUS_VAL="${ENTITY_STATUS#*: }"
  if [ "$ENTITY_STATUS_VAL" = "done" ]; then
    pass "entity reached done status"
  else
    fail "entity reached done status (stuck at: $ENTITY_STATUS_VAL)"
  fi
fi

# Check 2: Entity advanced past the first non-initial stage
# Even if it didn't reach done, it should have gotten past 'work'
if [ -n "$FINAL_FILE" ]; then
  if [ "$ENTITY_STATUS_VAL" = "backlog" ]; then
    fail "entity advanced past backlog"
  else
    pass "entity advanced past backlog (status: $ENTITY_STATUS_VAL)"
  fi
fi

# Check 3: At least 2 Agent() dispatches occurred (work + review minimum)
DISPATCH_COUNT=$(python3 -c "
import json
count = 0
with open('$TEST_DIR/fo-log.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'tool_use' and block.get('name') == 'Agent':
                        count += 1
        except: pass
print(count)
" 2>/dev/null)

if [ "${DISPATCH_COUNT:-0}" -ge 2 ]; then
  pass "multiple dispatches occurred ($DISPATCH_COUNT Agent() calls)"
else
  fail "multiple dispatches occurred (got ${DISPATCH_COUNT:-0} — expected >=2 for work + review)"
fi

# Check 4: Entity has completed timestamp set
if [ -n "$FINAL_FILE" ]; then
  COMPLETED_VAL=$(head -15 "$FINAL_FILE" | grep "^completed:" | head -1)
  COMPLETED_VAL="${COMPLETED_VAL#*: }"
  if [ -n "$COMPLETED_VAL" ]; then
    pass "entity has completed timestamp"
  else
    fail "entity has completed timestamp"
  fi
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
  echo "  Test dir:      $TEST_DIR"
  echo "  FO log:        $TEST_DIR/fo-log.jsonl"
  echo "  Entity file:   $FINAL_FILE"
  # Don't clean up on failure so logs can be inspected
  trap - EXIT
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
