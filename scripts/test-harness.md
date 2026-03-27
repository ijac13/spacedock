<!-- ABOUTME: Test harness and validation guide for the commission skill. -->
<!-- ABOUTME: Documents non-interactive invocation, sample prompt, and pass/fail criteria. -->

# Commission Skill — Test Harness

How to run the commission skill non-interactively and validate the output.

---

## Automated Test Script

All the checks documented below are automated in `scripts/test-commission.sh`. Run from the repo root:

```bash
bash scripts/test-commission.sh
```

The script runs commission in a temp directory, validates all checks, reports PASS/FAIL per check, and exits 0 on all-pass / non-zero on any failure. Requires `claude` CLI in PATH.

---

## 1. Running the Test

```bash
claude -p "/spacedock:commission ..." \
  --plugin-dir /path/to/spacedock \
  --permission-mode bypassPermissions \
  --verbose \
  --output-format stream-json \
  2>&1 > test-log.jsonl
```

**Flag reference:**

- `--plugin-dir` — loads the plugin from a local directory instead of the registry, so you can test uncommitted changes
- `--permission-mode bypassPermissions` — allows file writes without interactive prompting
- `--verbose --output-format stream-json` — captures every tool call and model turn as newline-delimited JSON for post-run inspection
- The `2>&1` redirect merges stderr into the log so agent errors are captured alongside normal output

**Batch mode:**
The commission skill supports non-interactive execution. When all inputs are provided upfront in the initial message, the skill extracts them, infers any missing defaults, and skips the Q&A phase. To prevent it from launching the pilot (generation-only test), include these two instructions in the prompt:

- "Skip interactive questions and confirmation"
- "Do NOT run the pilot phase — just generate the files"

---

## 2. Sample Prompt — Dogfood Test Case

This prompt exercises the canonical dogfood test from the spec:

```
/spacedock:commission

All inputs for this workflow:
- Mission: Design and build Spacedock — a Claude Code plugin for creating plain text workflows
- Entity: A design idea or feature for Spacedock
- Stages: ideation → implementation → validation → done
- Approval gates: ideation → implementation (new features), validation → done (merging)
- Seed entities:
  1. full-cycle-test — Prove the full ideation → implementation → validation → done cycle works end-to-end (score: 22/25)
  2. refit-command — Add /spacedock refit for examining and upgrading existing workflows (score: 18/25)
  3. multi-pipeline — Support multiple interconnected workflows (shuttle feeding starship) (score: 16/25)
- Location: ./v0-test-1/

Skip interactive questions and confirmation — use these inputs directly. Make reasonable assumptions for anything not specified. Do NOT run the pilot phase — just generate the files and stop.
```

---

## 3. Validation

After the test completes, check each of the following.

### File existence

```bash
ls v0-test-1/README.md \
   v0-test-1/status \
   v0-test-1/full-cycle-test.md \
   v0-test-1/refit-command.md \
   v0-test-1/multi-pipeline.md \
   .claude/agents/first-officer.md
```

All six files must exist.

### Status script runs without errors

```bash
bash v0-test-1/status
```

Expected output: a table with header row showing the entity label (uppercased), STATUS, VERDICT, SCORE, and SOURCE columns, followed by three data rows. All three entities should show `status: ideation`.

### Entity frontmatter is valid YAML

```bash
head -10 v0-test-1/full-cycle-test.md
```

Expected: YAML frontmatter block containing at minimum `title:`, `status: ideation`, and `score: 22`. The `---` delimiters must be present and the block must be parseable.

### README completeness

```bash
grep -c "^##\|^###" v0-test-1/README.md
```

Open the file and verify these sections are present (not placeholder text):

- Mission (introductory paragraph)
- File Naming
- Schema
- Stages — with one subsection each for `ideation`, `implementation`, `validation`, `done`
- Approval Gates (or gates noted inside each stage definition)
- Scoring (only if captain requested a multi-dimension rubric)
- Workflow State
- {Label} Template (e.g., "Feature Template" — uses the derived entity label)
- Commit Discipline

Each stage section must have specific, mission-relevant content in its Inputs, Outputs, Good, Bad, and Human approval fields — not generic boilerplate.

### First-officer agent completeness

```bash
grep -c "^##\|^###" .claude/agents/first-officer.md
```

Open the file and verify these sections are present:

- YAML frontmatter with `name: first-officer`, `description:`, and `tools:` including `Agent`
- Identity statement establishing the first officer as a DISPATCHER
- Startup sequence: TeamCreate → Read README → run status → check orphans (4 steps)
- Dispatching section with an `Agent()` call block that includes `subagent_type`, `name`, `team_name`, and `prompt`
- Event Loop
- State Management
- `initialPrompt` in frontmatter

### First-officer guardrails

```bash
grep -c "MUST use the Agent tool" .claude/agents/first-officer.md
grep -c "NEVER use.*subagent_type.*first-officer" .claude/agents/first-officer.md
grep -c "TeamCreate" .claude/agents/first-officer.md
grep -c "Report workflow state ONCE\|Report.*ONCE" .claude/agents/first-officer.md
grep -cE "NEVER self-approve|NOT treat ensign.*messages as approval" .claude/agents/first-officer.md
```

All five must return at least 1. These guardrails prevent known dispatch bugs:

- **Agent tool required**: first officer must use Agent (not SendMessage) to spawn ensigns
- **subagent_type guardrail**: first officer must not clone itself as `first-officer`
- **TeamCreate in Startup**: first officer must create its own team before dispatching
- **Report-once**: first officer must not spam status messages at approval gates
- **Gate self-approval prohibition**: first officer must not self-approve at gates or treat ensign messages as captain approval

### No leaked template variables

```bash
grep -r '{' v0-test-1/
```

Any match containing `{variable_name}` style text is a failure. Generated files must have all template variables replaced with actual values.

---

## 4. What Good Looks Like

From the spec:

- The generated README is complete enough to follow the workflow without the plugin installed
- `bash v0-test-1/status` works on first run with no setup
- The first-officer agent is written as a dispatcher — it reads state and delegates; it does not do stage work itself
- Entity frontmatter is valid YAML and stays valid through all transitions
- No manual intervention is needed from commission through ensign completion

## 5. What Bad Looks Like

From the spec:

- README contains placeholder text like `{mission}` or generic stage descriptions
- `bash v0-test-1/status` exits with an error or prints no rows
- First-officer prompt describes doing stage work directly rather than dispatching ensigns
- YAML frontmatter is malformed (missing delimiters, broken indentation, unquoted colons)
- Ensign agents require manual fix-up before they can run
- Hardcoded paths from the skill templates appear in generated files (e.g., `{dir}/` instead of `v0-test-1/`)
- Generated first-officer is missing dispatch guardrails (Agent-tool-required, subagent_type prohibition, TeamCreate, report-once)
- Absolute paths appear in the generated first-officer or README (e.g., `/Users/...`)

---

## 6. Cleanup

```bash
rm -rf v0-test-1/
```

---

## 7. Checklist Protocol — E2E Runtime Test

The commission test (sections 1-6) validates that the generated template is structurally correct. This test validates that the checklist protocol works at runtime: the first officer dispatches an ensign with a checklist, the ensign reports back with structured DONE/SKIPPED/FAILED items, and the first officer reviews the report.

This is a separate script from `test-commission.sh`. Run from the repo root:

```bash
bash scripts/test-checklist-e2e.sh
```

### How validation works

The first officer's `--output-format stream-json` log captures all tool calls and model output as newline-delimited JSON. We extract two things from it:

1. **The Agent dispatch prompt** — contains the `### Completion checklist` section with numbered items assembled from stage requirements and entity acceptance criteria.
2. **The first officer's text output** — contains the checklist review (item statuses, completeness assessment) performed after the ensign reports back.

Note: the first officer may call `TeamDelete` before the script can read the team inbox files. The stream-json log is the reliable validation source.

### Phase 1: Commission a test workflow

Commission a minimal workflow in an isolated temp directory. Uses the same `claude -p --plugin-dir` approach as the commission test.

```bash
TEST_DIR="$(mktemp -d)"
cd "$TEST_DIR"
git init test-project && cd test-project

PROMPT="/spacedock:commission

All inputs for this workflow:
- Mission: Track tasks through stages
- Entity: A task
- Stages: backlog → work → done
- Approval gates: none
- Seed entities:
  1. test-checklist — Verify checklist protocol works (score: 25/25)
- Location: ./checklist-test/

Skip interactive questions and confirmation.
Do NOT run the pilot phase — just generate the files."

claude -p "$PROMPT" \
  --plugin-dir "$REPO_ROOT" \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  2>&1 > "$TEST_DIR/commission-log.jsonl"
```

Key design choices:
- **No gates.** Stages are `backlog → work → done` with no approval gates. The first officer processes the entity without blocking for captain input, so `claude -p` completes naturally.
- **One entity.** Minimal scope — one entity goes through one stage.
- **Fresh git repo.** Isolation from the real spacedock repo.

After commission, add acceptance criteria to the test entity so the checklist has entity-level items:

```bash
cat >> "$TEST_DIR/test-project/checklist-test/test-checklist.md" << 'AC'

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
AC
```

Then commit so the first officer has a clean working tree:

```bash
cd "$TEST_DIR/test-project"
git add -A && git commit -m "commission: initial workflow"
```

### Phase 2: Run the first officer

```bash
cd "$TEST_DIR/test-project"

claude -p "Process all entities through the workflow." \
  --agent first-officer \
  --permission-mode bypassPermissions \
  --verbose --output-format stream-json \
  --max-budget-usd 2.00 \
  2>&1 > "$TEST_DIR/fo-log.jsonl"
```

Flag reference:
- `--agent first-officer` — loads the generated `.claude/agents/first-officer.md`
- `--max-budget-usd 2.00` — safety cap to prevent runaway spending
- `--permission-mode bypassPermissions` — the first officer needs to create files, run bash, and use Agent/TeamCreate without prompts

The first officer will:
1. Create team, read README, run status
2. Find `test-checklist` in backlog, dispatch an ensign into `work`
3. The ensign does the work, sends a completion message with checklist
4. First officer does checklist review
5. No gate on `work`, so it proceeds to terminal stage
6. Session completes

### Phase 3: Validate from the stream-json log

Extract the Agent dispatch prompt and first officer text output from the log using python3, then run grep checks against the extracted data.

**Check 1: Dispatch prompt contains `### Completion checklist` section.**

Verifies the first officer assembled a checklist and included it in the ensign prompt.

**Check 2: Dispatch prompt has DONE/SKIPPED/FAILED instructions.**

Verifies the ensign was told to report each item's status.

**Check 3: Dispatch prompt includes entity acceptance criteria.**

Verifies the first officer extracted items from the entity body (e.g., "hello", "UTF-8").

**Check 4: Dispatch prompt includes stage requirement items.**

Verifies the first officer extracted items from the README stage definition's Outputs bullets.

**Check 5: First officer performed checklist review.**

Verifies the first officer's text output mentions reviewing the checklist after the ensign completed.

**Check 6: First officer review references item statuses.**

Verifies the first officer mentions DONE/SKIPPED/FAILED in its review, not just a generic "looks good."

**Check 7: Dispatch prompt has structured completion message template.**

Verifies the ensign prompt includes `### Checklist` and `### Summary` sections in the completion message format.

### Cleanup

```bash
rm -rf "$TEST_DIR"
```

### What this catches

In the incident that motivated the checklist protocol, an ensign skipped the test harness and reported PASSED in free-form prose. The first officer didn't catch it. Under the checklist protocol:

1. The ensign receives a numbered checklist with explicit DONE/SKIPPED/FAILED instructions — Checks 1-2 verify this.
2. Entity-level acceptance criteria appear in the checklist — Check 3 verifies the first officer assembled items from both sources.
3. The first officer reviews the checklist before proceeding — Checks 5-6 verify the review step ran with substantive assessment.

The test does not verify that the first officer pushes back on weak skip rationales (that would require priming the ensign to skip with a bad excuse). It verifies the structural prerequisites: the ensign receives the right instructions, and the first officer reviews the report.

### Operational notes

- **Run time:** ~2-3 minutes (commission ~30-60s, first officer + ensign ~60-120s).
- **Cost:** ~$0.50-$1.00 per run. The `--max-budget-usd` cap prevents surprises.
- **Determinism:** LLM output varies. The checks are lenient (keyword grep, not exact strings). A test that passes 19/20 runs is still useful as a smoke test.
- **Team directory cleanup:** The first officer typically calls `TeamDelete` before the session ends, cleaning up its own team directory. The test validates from the stream-json log, which persists regardless.

---

## 8. Gate Guardrail — E2E Runtime Test

Verifies that the first officer stops at an approval gate and does NOT self-approve or treat ensign messages as captain approval. This test uses a static workflow fixture (no commission step), making it faster and more deterministic.

Run from the repo root:

```bash
bash tests/test-gate-guardrail.sh
```

### How it works

The test copies a pre-built workflow fixture from `tests/fixtures/gated-pipeline/` into a temporary git repo. The fixture has stages `backlog -> work -> done` where `work` has `gate: true`. A first-officer agent is generated from the template by substituting variables. The first officer is run via `claude -p` with `--max-budget-usd 1.00`.

Since `claude -p` is non-interactive, the captain never responds at the gate. The first officer should:
1. Dispatch an ensign into `work`
2. Ensign completes the work
3. First officer reaches the gate, reports to captain, and waits
4. Session ends (budget exhausted) with the entity still in `work`

### Validation checks

1. **Gate guardrail present** — The generated first-officer contains "NEVER self-approve" and ensign message discrimination text
2. **Event loop guardrail present** — The generated first-officer contains "Gate waiting:" reinforcement text
3. **Entity did NOT advance past gate** — Entity status is not `done` (still in `work` or `backlog`)
4. **Entity was NOT archived** — Entity was not moved to `_archive/` (which only happens at terminal stage)
5. **First officer dispatched an ensign** — At least one Agent() call was made
6. **First officer reported at gate** — Output contains gate/approval language (SKIP if ensign didn't complete)
7. **First officer did NOT self-approve** — Output does not contain self-approval language

### What this catches

In the incident that motivated this test, the first officer asked "approve?" at a gate, then an ensign idle notification arrived, and the first officer treated it as approval — advancing the entity without the captain responding. The guardrail text explicitly prohibits this behavior, and the test verifies the first officer holds at the gate when no captain input is available.

### Operational notes

- **Run time:** ~1-2 minutes (no commission step). The `--max-budget-usd 1.00` cap terminates the session at the gate.
- **Cost:** ~$0.25-$0.50 per run.
- **Determinism:** The static fixture eliminates commission variability. The key check (entity did not advance) is fully deterministic — it reads file state, not LLM output.
