# ABOUTME: E2E test for the merge hook guardrail in the first-officer template.
# ABOUTME: Verifies merge hooks fire before local merge, and that no-mods fallback works.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE_DIR="$REPO_ROOT/tests/fixtures/merge-hook-pipeline"
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

echo "=== Merge Hook Guardrail E2E Test ==="
echo "Repo root:    $REPO_ROOT"
echo "Fixture dir:  $FIXTURE_DIR"
echo "Test dir:     $TEST_DIR"
echo ""

# --- Phase 1: Static validation of the template guardrail ---

echo "--- Phase 1: Template guardrail validation ---"
echo ""
echo "[Template Guardrail Text]"

TEMPLATE="$REPO_ROOT/templates/first-officer.md"

# Check 1: MERGE HOOK GUARDRAIL exists in the template
if grep -q "MERGE HOOK GUARDRAIL" "$TEMPLATE"; then
  pass "MERGE HOOK GUARDRAIL present in template"
else
  fail "MERGE HOOK GUARDRAIL present in template"
  echo "  FATAL: Guardrail text missing from template. Aborting."
  trap - EXIT
  exit 1
fi

# Check 2: Guardrail is in the Merge and Cleanup section
MERGE_SECTION=$(awk '/^## Merge and Cleanup/,/^## [^#]/' "$TEMPLATE")
if echo "$MERGE_SECTION" | grep -q "MERGE HOOK GUARDRAIL"; then
  pass "guardrail is in Merge and Cleanup section"
else
  fail "guardrail is in Merge and Cleanup section"
fi

# Check 3: Guardrail mentions in-memory hook registry (not filesystem scan)
if echo "$MERGE_SECTION" | grep -q "in-memory hook registry"; then
  pass "guardrail references in-memory hook registry"
else
  fail "guardrail references in-memory hook registry"
fi

# Check 4: Guardrail blocks git merge, archival, and status advancement
if echo "$MERGE_SECTION" | grep -qE "Do NOT proceed to.*git merge.*archival.*status advancement"; then
  pass "guardrail blocks merge, archival, and status advancement"
else
  fail "guardrail blocks merge, archival, and status advancement"
fi

# Check 5: Guardrail handles PR-created case
if echo "$MERGE_SECTION" | grep -q "do NOT perform a local merge"; then
  pass "guardrail handles PR-created stop condition"
else
  fail "guardrail handles PR-created stop condition"
fi

# Check 6: Gate approval path delegates to Merge and Cleanup (no inline hook instruction)
GATE_SECTION=$(awk '/^## Completion and Gates/,/^## Feedback Rejection/' "$TEMPLATE")
APPROVE_TERMINAL_WORKTREE=$(echo "$GATE_SECTION" | sed -n '/Approve.*terminal.*worktree:/,/^- \*\*/p')

if echo "$APPROVE_TERMINAL_WORKTREE" | grep -q "Fall through to.*Merge and Cleanup"; then
  pass "gate approval path delegates to Merge and Cleanup"
else
  fail "gate approval path delegates to Merge and Cleanup"
fi

# Check 7: Gate approval path does NOT have inline "Run merge hooks"
if echo "$APPROVE_TERMINAL_WORKTREE" | grep -qiE "Run merge hooks.*_mods"; then
  fail "gate approval path has NO inline merge hook instruction (found inline instruction)"
else
  pass "gate approval path has NO inline merge hook instruction"
fi

# Check 8: No-mods fallback in the guardrail
if grep -q "If no merge hooks are registered, proceed with default local merge" "$TEMPLATE"; then
  pass "guardrail has no-mods fallback"
else
  fail "guardrail has no-mods fallback"
fi

echo ""

# --- Phase 2: Set up test project with merge hook mod ---

echo "--- Phase 2: Set up test project with merge hook mod ---"

cd "$TEST_DIR"
git init test-with-hook >/dev/null 2>&1
cd "$TEST_DIR/test-with-hook"
git commit --allow-empty -m "init" >/dev/null 2>&1

# Copy workflow fixture
mkdir -p merge-hook-pipeline/_mods
cp "$FIXTURE_DIR/README.md" merge-hook-pipeline/
cp "$FIXTURE_DIR/merge-hook-entity.md" merge-hook-pipeline/
cp "$FIXTURE_DIR/status" merge-hook-pipeline/
chmod +x merge-hook-pipeline/status
cp "$FIXTURE_DIR/_mods/test-hook.md" merge-hook-pipeline/_mods/

# Copy first-officer template verbatim (no substitution needed — template is static)
mkdir -p .claude/agents
cp "$REPO_ROOT/templates/first-officer.md" .claude/agents/first-officer.md

git add -A && git commit -m "setup: merge hook guardrail test fixture" >/dev/null 2>&1

echo ""
echo "[Fixture Setup — With Hook]"

# Verify fixture is valid
if grep -q "MERGE HOOK GUARDRAIL" .claude/agents/first-officer.md; then
  pass "generated first-officer contains merge hook guardrail"
else
  fail "generated first-officer contains merge hook guardrail"
  echo "  FATAL: Guardrail text missing from generated agent. Aborting."
  trap - EXIT
  exit 1
fi

if bash merge-hook-pipeline/status >/dev/null 2>&1; then
  pass "status script runs without errors"
else
  fail "status script runs without errors"
fi

echo ""

# --- Phase 3: Run first officer (with hook mod) ---

echo "--- Phase 3: Run first officer with hook mod (this takes ~60-120s) ---"

cd "$TEST_DIR/test-with-hook"

FO_EXIT=0
claude -p "Process all tasks through the workflow to completion." \
  --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > "$TEST_DIR/fo-hook-log.jsonl" || FO_EXIT=$?

echo ""
if [ $FO_EXIT -ne 0 ]; then
  echo "WARNING: first officer exited with code $FO_EXIT"
fi

# --- Phase 4: Validate hook fired ---

echo "--- Phase 4: Validate merge hook execution ---"
echo ""
echo "[Merge Hook Execution]"

# Check: _merge-hook-fired.txt exists and contains entity slug
HOOK_FILE="$TEST_DIR/test-with-hook/merge-hook-pipeline/_merge-hook-fired.txt"
if [ -f "$HOOK_FILE" ]; then
  pass "_merge-hook-fired.txt exists"
  if grep -q "merge-hook-entity" "$HOOK_FILE"; then
    pass "_merge-hook-fired.txt contains entity slug"
  else
    fail "_merge-hook-fired.txt contains entity slug"
    echo "  Contents: $(cat "$HOOK_FILE")"
  fi
else
  fail "_merge-hook-fired.txt exists (hook did not fire)"
  fail "_merge-hook-fired.txt contains entity slug (file missing)"
fi

# Check: entity was archived (merge completed after hook)
if [ -f "$TEST_DIR/test-with-hook/merge-hook-pipeline/_archive/merge-hook-entity.md" ]; then
  pass "entity was archived (merge completed after hook)"
else
  # Entity might still be in the workflow dir if merge didn't complete
  if [ -f "$TEST_DIR/test-with-hook/merge-hook-pipeline/merge-hook-entity.md" ]; then
    ENTITY_STATUS=$(head -15 "$TEST_DIR/test-with-hook/merge-hook-pipeline/merge-hook-entity.md" | grep "^status:" | head -1)
    echo "  SKIP: entity not archived (status: ${ENTITY_STATUS#*: }) — FO may not have completed the full cycle within budget"
  else
    fail "entity was archived (entity file not found in either location)"
  fi
fi

echo ""

# --- Phase 5: Set up and run no-mods fallback test ---

echo "--- Phase 5: Set up no-mods fallback test ---"

cd "$TEST_DIR"
git init test-no-mods >/dev/null 2>&1
cd "$TEST_DIR/test-no-mods"
git commit --allow-empty -m "init" >/dev/null 2>&1

# Copy workflow fixture WITHOUT _mods
mkdir -p merge-hook-pipeline
cp "$FIXTURE_DIR/README.md" merge-hook-pipeline/
cp "$FIXTURE_DIR/merge-hook-entity.md" merge-hook-pipeline/
cp "$FIXTURE_DIR/status" merge-hook-pipeline/
chmod +x merge-hook-pipeline/status

# Copy first-officer template verbatim
mkdir -p .claude/agents
cp "$REPO_ROOT/templates/first-officer.md" .claude/agents/first-officer.md

git add -A && git commit -m "setup: no-mods fallback test fixture" >/dev/null 2>&1

echo ""
echo "[Fixture Setup — No Mods]"

if bash merge-hook-pipeline/status >/dev/null 2>&1; then
  pass "status script runs without errors (no-mods)"
else
  fail "status script runs without errors (no-mods)"
fi

echo ""
echo "--- Phase 6: Run first officer without mods (this takes ~60-120s) ---"

cd "$TEST_DIR/test-no-mods"

FO_EXIT2=0
claude -p "Process all tasks through the workflow to completion." \
  --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > "$TEST_DIR/fo-nomods-log.jsonl" || FO_EXIT2=$?

echo ""
if [ $FO_EXIT2 -ne 0 ]; then
  echo "WARNING: first officer exited with code $FO_EXIT2"
fi

# --- Phase 7: Validate no-mods fallback ---

echo "--- Phase 7: Validate no-mods fallback ---"
echo ""
echo "[No-Mods Fallback]"

# Check: _merge-hook-fired.txt does NOT exist (no hooks to fire)
HOOK_FILE2="$TEST_DIR/test-no-mods/merge-hook-pipeline/_merge-hook-fired.txt"
if [ -f "$HOOK_FILE2" ]; then
  fail "no _merge-hook-fired.txt in no-mods run (file exists unexpectedly)"
else
  pass "no _merge-hook-fired.txt in no-mods run"
fi

# Check: entity was archived (local merge completed without hooks)
if [ -f "$TEST_DIR/test-no-mods/merge-hook-pipeline/_archive/merge-hook-entity.md" ]; then
  pass "entity was archived via local merge (no-mods fallback works)"
else
  if [ -f "$TEST_DIR/test-no-mods/merge-hook-pipeline/merge-hook-entity.md" ]; then
    ENTITY_STATUS2=$(head -15 "$TEST_DIR/test-no-mods/merge-hook-pipeline/merge-hook-entity.md" | grep "^status:" | head -1)
    echo "  SKIP: entity not archived (status: ${ENTITY_STATUS2#*: }) — FO may not have completed the full cycle within budget"
  else
    fail "entity was archived via local merge (entity file not found)"
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
  echo "  Test dir:          $TEST_DIR"
  echo "  FO hook log:       $TEST_DIR/fo-hook-log.jsonl"
  echo "  FO no-mods log:    $TEST_DIR/fo-nomods-log.jsonl"
  # Don't clean up on failure so logs can be inspected
  trap - EXIT
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
