# ABOUTME: Executable test script for the commission skill.
# ABOUTME: Runs batch-mode commission, validates output, reports PASS/FAIL per check.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
WORKFLOW_DIR="$TEST_DIR/v0-test-1"
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

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

echo "=== Commission Skill Test ==="
echo "Repo root:  $REPO_ROOT"
echo "Test dir:   $TEST_DIR"
echo ""

# --- Phase 1: Run commission ---

echo "--- Phase 1: Running commission (this takes ~30-60s) ---"

PROMPT="/spacedock:commission

All inputs for this workflow:
- Mission: Design and build Spacedock — a Claude Code plugin for creating plain text workflows
- Entity: A design idea or feature for Spacedock
- Stages: ideation → implementation (agent: pr-lieutenant) → validation → done
- Approval gates: ideation → implementation (new features), validation → done (merging)
- Seed entities:
  1. full-cycle-test — Prove the full ideation → implementation → validation → done cycle works end-to-end (score: 22/25)
  2. refit-command — Add /spacedock refit for examining and upgrading existing workflows (score: 18/25)
  3. multi-pipeline — Support multiple interconnected workflows (shuttle feeding starship) (score: 16/25)
- Location: ./v0-test-1/

Skip interactive questions and confirmation — use these inputs directly. Make reasonable assumptions for anything not specified. Do NOT run the pilot phase — just generate the files and stop."

cd "$TEST_DIR"

CLAUDE_EXIT=0
claude -p "$PROMPT" \
  --plugin-dir "$REPO_ROOT" \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  2>&1 > "$TEST_DIR/test-log.jsonl" || CLAUDE_EXIT=$?

echo ""
if [ $CLAUDE_EXIT -ne 0 ]; then
  echo "WARNING: claude exited with code $CLAUDE_EXIT"
fi

# --- Phase 2: Validate output ---

echo "--- Phase 2: Validation ---"

# -- File existence --
echo ""
echo "[File Existence]"
check "README.md exists"              test -f "$WORKFLOW_DIR/README.md"
check "status script exists"          test -f "$WORKFLOW_DIR/status"
check "full-cycle-test.md exists"     test -f "$WORKFLOW_DIR/full-cycle-test.md"
check "refit-command.md exists"       test -f "$WORKFLOW_DIR/refit-command.md"
check "multi-pipeline.md exists"      test -f "$WORKFLOW_DIR/multi-pipeline.md"
check "first-officer.md exists"       test -f "$TEST_DIR/.claude/agents/first-officer.md"
check "pr-lieutenant.md exists"      test -f "$TEST_DIR/.claude/agents/pr-lieutenant.md"

# -- Status script --
echo ""
echo "[Status Script]"
if [ -f "$WORKFLOW_DIR/status" ]; then
  chmod +x "$WORKFLOW_DIR/status"
  STATUS_OUTPUT="$("$WORKFLOW_DIR/status" 2>&1)" || true
  if [ -n "$STATUS_OUTPUT" ]; then
    pass "status script produces output"
  else
    fail "status script produces output"
  fi
  if echo "$STATUS_OUTPUT" | grep -qi "STATUS\|SCORE"; then
    pass "status output contains header"
  else
    fail "status output contains header"
  fi
  ROW_COUNT=$(echo "$STATUS_OUTPUT" | grep -c "ideation" || true)
  if [ "$ROW_COUNT" -ge 3 ]; then
    pass "status shows 3 entities in ideation"
  else
    fail "status shows 3 entities in ideation (found $ROW_COUNT)"
  fi
else
  fail "status script produces output (file missing)"
  fail "status output contains header (file missing)"
  fail "status shows 3 entities in ideation (file missing)"
fi

# -- Entity frontmatter --
echo ""
echo "[Entity Frontmatter]"
for ENTITY in full-cycle-test refit-command multi-pipeline; do
  ENTITY_FILE="$WORKFLOW_DIR/$ENTITY.md"
  if [ -f "$ENTITY_FILE" ]; then
    # Check YAML delimiters
    FIRST_LINE="$(head -1 "$ENTITY_FILE")"
    if [ "$FIRST_LINE" = "---" ]; then
      pass "$ENTITY.md has opening YAML delimiter"
    else
      fail "$ENTITY.md has opening YAML delimiter"
    fi
    # Check for title field
    if head -10 "$ENTITY_FILE" | grep -q "^title:"; then
      pass "$ENTITY.md has title field"
    else
      fail "$ENTITY.md has title field"
    fi
    # Check for status: ideation
    if head -10 "$ENTITY_FILE" | grep -q "^status:.*ideation"; then
      pass "$ENTITY.md has status: ideation"
    else
      fail "$ENTITY.md has status: ideation"
    fi
  else
    fail "$ENTITY.md has opening YAML delimiter (file missing)"
    fail "$ENTITY.md has title field (file missing)"
    fail "$ENTITY.md has status: ideation (file missing)"
  fi
done

# -- README completeness --
echo ""
echo "[README Completeness]"
if [ -f "$WORKFLOW_DIR/README.md" ]; then
  README="$WORKFLOW_DIR/README.md"
  for SECTION in "File Naming" "Schema" "Stages" "Template" "Commit"; do
    if grep -qi "$SECTION" "$README"; then
      pass "README contains '$SECTION' section"
    else
      fail "README contains '$SECTION' section"
    fi
  done
  for STAGE in "ideation" "implementation" "validation" "done"; do
    if grep -qi "$STAGE" "$README"; then
      pass "README mentions stage '$STAGE'"
    else
      fail "README mentions stage '$STAGE'"
    fi
  done
else
  fail "README completeness checks (file missing)"
fi

# -- First-officer completeness --
echo ""
echo "[First-Officer Completeness]"
FO="$TEST_DIR/.claude/agents/first-officer.md"
if [ -f "$FO" ]; then
  # Frontmatter checks
  if head -20 "$FO" | grep -q "name:.*first-officer"; then
    pass "first-officer has name in frontmatter"
  else
    fail "first-officer has name in frontmatter"
  fi
  if head -20 "$FO" | grep -q "tools:"; then
    pass "first-officer has tools in frontmatter"
  else
    fail "first-officer has tools in frontmatter"
  fi
  # Content checks
  for KEYWORD in "DISPATCHER|dispatcher" "TeamCreate" "Agent\(" "Event Loop|event loop" "Workflow Path|workflow path|WORKFLOW PATH" "initialPrompt"; do
    LABEL="$(echo "$KEYWORD" | sed 's/|/ or /g')"
    if grep -qE "$KEYWORD" "$FO"; then
      pass "first-officer contains '$LABEL'"
    else
      fail "first-officer contains '$LABEL'"
    fi
  done
else
  fail "first-officer completeness checks (file missing)"
fi

# -- First-officer guardrails --
echo ""
echo "[First-Officer Guardrails]"
if [ -f "$FO" ]; then
  if grep -c "MUST use the Agent tool" "$FO" | grep -qv "^0$"; then
    pass "guardrail: Agent tool required"
  else
    fail "guardrail: Agent tool required"
  fi
  if grep -cE "NEVER use.*subagent_type.*first-officer|never.*subagent_type.*first-officer" "$FO" | grep -qv "^0$"; then
    pass "guardrail: subagent_type prohibition"
  else
    fail "guardrail: subagent_type prohibition"
  fi
  if grep -c "TeamCreate" "$FO" | grep -qv "^0$"; then
    pass "guardrail: TeamCreate in startup"
  else
    fail "guardrail: TeamCreate in startup"
  fi
  if grep -cE "Report.*ONCE|report.*once" "$FO" | grep -qv "^0$"; then
    pass "guardrail: report-once"
  else
    fail "guardrail: report-once"
  fi
  if grep -cE "NEVER self-approve|NOT treat ensign.*messages as approval" "$FO" | grep -qv "^0$"; then
    pass "guardrail: gate self-approval prohibition"
  else
    fail "guardrail: gate self-approval prohibition"
  fi
  # Dispatch name must include stage to avoid name collisions across sequential dispatches
  # See: https://github.com/clkao/spacedock/issues/1
  if grep -E 'name=.*\{.*stage' "$FO" | grep -qv "^0$"; then
    pass "guardrail: dispatch name includes stage for uniqueness"
  else
    fail "guardrail: dispatch name includes stage for uniqueness"
  fi
else
  fail "guardrail: Agent tool required (file missing)"
  fail "guardrail: subagent_type prohibition (file missing)"
  fail "guardrail: TeamCreate in startup (file missing)"
  fail "guardrail: report-once (file missing)"
  fail "guardrail: gate self-approval prohibition (file missing)"
fi

# -- README frontmatter: stages block --
echo ""
echo "[README Frontmatter]"
if [ -f "$WORKFLOW_DIR/README.md" ]; then
  README="$WORKFLOW_DIR/README.md"
  # Extract frontmatter (between first and second --- delimiters)
  FM=$(awk 'NR==1{next} /^---$/{exit} {print}' "$README")
  if echo "$FM" | grep -q "^stages:"; then
    pass "README frontmatter has stages block"
  else
    fail "README frontmatter has stages block"
  fi
  if echo "$FM" | grep -q "id-style:"; then
    pass "README frontmatter has id-style"
  else
    fail "README frontmatter has id-style"
  fi
  if echo "$FM" | grep -q "defaults:"; then
    pass "stages block has defaults"
  else
    fail "stages block has defaults"
  fi
  if echo "$FM" | grep -q "states:"; then
    pass "stages block has states list"
  else
    fail "stages block has states list"
  fi
  if echo "$FM" | grep -q "initial: true"; then
    pass "stages has initial state marker"
  else
    fail "stages has initial state marker"
  fi
  if echo "$FM" | grep -q "terminal: true"; then
    pass "stages has terminal state marker"
  else
    fail "stages has terminal state marker"
  fi
  if echo "$FM" | grep -q "gate: true"; then
    pass "stages has at least one gate"
  else
    fail "stages has at least one gate"
  fi
  # Verify dispatch-property bullets are NOT in prose stage sections
  PROSE_WORKTREE=$(grep -c "^\- \*\*Worktree:\*\*" "$README" || true)
  if [ "$PROSE_WORKTREE" -eq 0 ]; then
    pass "no Worktree bullets in prose stage sections"
  else
    fail "no Worktree bullets in prose stage sections (found $PROSE_WORKTREE)"
  fi
  PROSE_GATE=$(grep -cE "^\- \*\*(Approval gate|Human approval):\*\*" "$README" || true)
  if [ "$PROSE_GATE" -eq 0 ]; then
    pass "no approval gate bullets in prose stage sections"
  else
    fail "no approval gate bullets in prose stage sections (found $PROSE_GATE)"
  fi
else
  fail "README frontmatter checks (file missing)"
fi

# -- Entity frontmatter: id field --
echo ""
echo "[Entity ID Field]"
for ENTITY in full-cycle-test refit-command multi-pipeline; do
  ENTITY_FILE="$WORKFLOW_DIR/$ENTITY.md"
  if [ -f "$ENTITY_FILE" ]; then
    if head -15 "$ENTITY_FILE" | grep -q "^id:"; then
      pass "$ENTITY.md has id field"
    else
      fail "$ENTITY.md has id field"
    fi
  else
    fail "$ENTITY.md has id field (file missing)"
  fi
done

# -- First-officer: frontmatter stages reading --
echo ""
echo "[First-Officer Stages Support]"
if [ -f "$FO" ]; then
  if grep -qi "stages.*frontmatter\|frontmatter.*stages\|stages.*block\|Read.*stages" "$FO"; then
    pass "first-officer reads stages from frontmatter"
  else
    fail "first-officer reads stages from frontmatter"
  fi
  # Backward-compatible fallback for pre-stages workflows is a refit concern,
  # not a commission concern. New commissions always generate the stages block.
  # No check needed here.
  if grep -qi "fresh\|Fresh" "$FO"; then
    pass "first-officer supports Fresh stage property"
  else
    fail "first-officer supports Fresh stage property"
  fi
  if grep -qi "dispatch fresh\|always.*fresh\|fresh.*dispatch" "$FO"; then
    pass "first-officer dispatches fresh ensigns"
  else
    fail "first-officer dispatches fresh ensigns"
  fi
  if grep -qi "validation.*test\|Testing Resources\|run.*test\|test.*harness" "$FO"; then
    pass "first-officer has smart validation instructions"
  else
    fail "first-officer has smart validation instructions"
  fi
  if grep -qi "_archive\|archive" "$FO"; then
    pass "first-officer references _archive convention"
  else
    fail "first-officer references _archive convention"
  fi
fi

# -- PR lieutenant agent --
echo ""
echo "[PR Lieutenant Agent]"
PRL="$TEST_DIR/.claude/agents/pr-lieutenant.md"
if [ -f "$PRL" ]; then
  if head -20 "$PRL" | grep -q "name:.*pr-lieutenant"; then
    pass "pr-lieutenant has name in frontmatter"
  else
    fail "pr-lieutenant has name in frontmatter"
  fi
  if grep -qi "ensign" "$PRL"; then
    pass "pr-lieutenant references ensign"
  else
    fail "pr-lieutenant references ensign"
  fi
  if grep -qE '__MISSION__|__SPACEDOCK_VERSION__|__ENTITY_LABEL__' "$PRL"; then
    fail "pr-lieutenant has no unsubstituted __VAR__ markers"
    grep -oE '__[A-Z_]+__' "$PRL" | sort -u | head -5
  else
    pass "pr-lieutenant has no unsubstituted __VAR__ markers"
  fi
else
  fail "pr-lieutenant has name in frontmatter (file missing)"
  fail "pr-lieutenant references ensign (file missing)"
  fail "pr-lieutenant has no unsubstituted __VAR__ markers (file missing)"
fi

# -- No leaked template variables --
echo ""
echo "[No Leaked Template Variables]"
if [ -d "$WORKFLOW_DIR" ]; then
  # Look for {variable_name} patterns (but not code like ${...} or JSON {..."key":})
  LEAKED=$(grep -rE '\{[a-z_]+\}' "$WORKFLOW_DIR" --include="*.md" 2>/dev/null | grep -vE '\$\{' | grep -v 'slug' || true)
  if [ -z "$LEAKED" ]; then
    pass "no leaked template variables"
  else
    fail "no leaked template variables"
    echo "    Found: $LEAKED" | head -5
  fi
else
  fail "no leaked template variables (directory missing)"
fi

# -- No absolute paths --
echo ""
echo "[No Absolute Paths]"
if [ -d "$WORKFLOW_DIR" ]; then
  ABS_PATHS=$(grep -rE '/Users/|/home/|/tmp/' "$WORKFLOW_DIR" --include="*.md" 2>/dev/null || true)
  if [ -z "$ABS_PATHS" ]; then
    pass "no absolute paths in generated files"
  else
    fail "no absolute paths in generated files"
    echo "    Found: $ABS_PATHS" | head -5
  fi
  # Also check the status script
  if [ -f "$WORKFLOW_DIR/status" ]; then
    ABS_IN_STATUS=$(grep -E '/Users/|/home/|/tmp/' "$WORKFLOW_DIR/status" 2>/dev/null || true)
    if [ -z "$ABS_IN_STATUS" ]; then
      pass "no absolute paths in status script"
    else
      fail "no absolute paths in status script"
      echo "    Found: $ABS_IN_STATUS" | head -5
    fi
  fi
else
  fail "no absolute paths (directory missing)"
fi

# --- Phase 3: Summary ---

echo ""
echo "=== Results ==="
TOTAL=$((PASSES + FAILURES))
echo "  $PASSES passed, $FAILURES failed (out of $TOTAL checks)"
echo ""

if [ $FAILURES -gt 0 ]; then
  echo "RESULT: FAIL"
  echo "Test log: $TEST_DIR/test-log.jsonl"
  # Don't clean up on failure so logs can be inspected
  trap - EXIT
  exit 1
else
  echo "RESULT: PASS"
  exit 0
fi
