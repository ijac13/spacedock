<!-- ABOUTME: Test harness and validation guide for the commission skill. -->
<!-- ABOUTME: Documents non-interactive invocation, sample prompt, and pass/fail criteria. -->

# Commission Skill — Test Harness

How to run the commission skill non-interactively and validate the output.

---

## Automated Test Script

All the checks documented below are automated in `scripts/test_commission.py`. Run from the repo root:

```bash
unset CLAUDECODE && uv run scripts/test_commission.py
```

Defaults to `--model opus --effort low` (~3 minutes). Override with:

```bash
uv run scripts/test_commission.py --model sonnet
uv run scripts/test_commission.py --effort high
```

The script runs commission in a temp directory, validates all checks, reports PASS/FAIL per check, and exits 0 on all-pass / non-zero on any failure. Requires `claude` CLI in PATH. Haiku is not supported — it cannot follow the commission skill.

---

## 1. Running the Test

```bash
unset CLAUDECODE && claude -p "/spacedock:commission ..." \
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
- `unset CLAUDECODE` — required when running from inside a Claude Code session (claude refuses to launch as a subprocess when this variable is set)

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
   v0-test-1/full-cycle-test.md \
   v0-test-1/refit-command.md \
   v0-test-1/multi-pipeline.md
```

Commission generates workflow files only (README, entities). Agents and the status viewer ship with the plugin — commission does not copy them.

Verify the plugin-shipped agent exists:
```bash
ls $REPO_ROOT/agents/first-officer.md
```

Verify commission does NOT generate a workflow-local status script or agents:
```bash
! test -f v0-test-1/status
```

### Status script runs without errors

The status viewer ships with the plugin at `skills/commission/bin/status`:

```bash
$REPO_ROOT/skills/commission/bin/status --workflow-dir v0-test-1
```

Expected output: a table with header row showing ID, SLUG, STATUS, TITLE, SCORE, SOURCE columns, followed by three data rows. All three entities should show `status: ideation`.

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

Each stage section must have specific, mission-relevant content in its Inputs, Outputs, Good, Bad fields — not generic boilerplate.

### First-officer agent structure

The plugin-shipped agent at `agents/first-officer.md` is a thin wrapper that loads its operating contract via skill preloading. Verify:

```bash
# Agent has skills frontmatter for boot loading
grep 'skills:' $REPO_ROOT/agents/first-officer.md

# Agent body identifies as DISPATCHER
grep 'DISPATCHER' $REPO_ROOT/agents/first-officer.md

# Agent references the boot skill as fallback
grep 'spacedock:first-officer' $REPO_ROOT/agents/first-officer.md
```

### First-officer guardrails (assembled content)

Guardrails live in reference files, not the agent file. Use `assembled_agent_content()` from `test_lib.py` to check the full assembled content, or verify the reference files directly:

```bash
# Gate self-approval prohibition
grep -c "self-approve" $REPO_ROOT/skills/first-officer/references/first-officer-shared-core.md

# Dispatch mechanism
grep -c "Agent(" $REPO_ROOT/skills/first-officer/references/claude-first-officer-runtime.md

# Report-once
grep -c "Report.*once\|ONCE" $REPO_ROOT/skills/first-officer/references/first-officer-shared-core.md

# Scaffolding protection
grep -c "scaffolding" $REPO_ROOT/skills/first-officer/references/first-officer-shared-core.md
```

### No leaked template variables

```bash
grep -r '{' v0-test-1/
```

Any match containing `{variable_name}` style text is a failure. Generated files must have all template variables replaced with actual values.

---

## 4. What Good Looks Like

- The generated README is complete enough to follow the workflow without the plugin installed
- `$REPO_ROOT/skills/commission/bin/status --workflow-dir v0-test-1` works on first run with no setup
- Agents ship with the plugin — commission does not generate agent files
- Entity frontmatter is valid YAML and stays valid through all transitions
- No manual intervention is needed from commission through ensign completion

## 5. What Bad Looks Like

- README contains placeholder text like `{mission}` or generic stage descriptions
- Status viewer exits with an error or prints no rows
- Commission generates agent files in `.claude/agents/` (this was removed in 076)
- YAML frontmatter is malformed (missing delimiters, broken indentation, unquoted colons)
- Ensign agents require manual fix-up before they can run
- Hardcoded paths from the skill templates appear in generated files
- Absolute paths appear in the generated README (e.g., `/Users/...`)

---

## 6. Cleanup

```bash
rm -rf v0-test-1/
```

---

## 7. E2E Runtime Tests

E2E tests validate runtime behavior of the first officer and ensign agents. They use static workflow fixtures (no commission step), making them faster and more deterministic.

All E2E tests are Python scripts under `tests/`. Run with:

```bash
unset CLAUDECODE && uv run tests/test_<name>.py
```

### Available E2E tests

| Test | What it validates | Default model |
|------|-------------------|---------------|
| `test_gate_guardrail.py` | FO stops at approval gate, no self-approval | haiku |
| `test_scaffolding_guardrail.py` | FO refuses to edit scaffolding files | haiku |
| `test_rejection_flow.py` | REJECTED validation triggers fix dispatch | haiku |
| `test_merge_hook_guardrail.py` | Merge hooks fire before local merge | haiku |
| `test_dispatch_names.py` | Entity reaches done, proper Agent() dispatch | haiku |
| `test_output_format.py` | Custom and default output formats | haiku |

### How E2E tests work

1. Create an isolated test project in a temp directory (`create_test_project`)
2. Copy a static fixture from `tests/fixtures/` (`setup_fixture`)
3. Install agent copies for the test project (`install_agents`)
4. Run `claude -p --agent spacedock:first-officer --plugin-dir $REPO_ROOT`
5. Parse the JSONL log (`LogParser`) for tool calls and text output
6. Assert behavioral properties (entity state, agent dispatches, guardrail compliance)

### Running with different models

```bash
uv run tests/test_gate_guardrail.py --model opus --effort low
uv run tests/test_rejection_flow.py --model opus
```

### Multi-runtime support

Gate, rejection, and merge-hook tests support `--runtime codex` for Codex E2E testing:

```bash
uv run tests/test_gate_guardrail.py --runtime codex
```

### Static (offline) tests

Static tests validate agent content without running `claude -p`:

```bash
uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q
```

These check assembled agent content, reference file structure, codex skill content, and status script behavior.

---

## 8. Operational Notes

- **Cost:** Commission test ~$0.50-$1.00. E2E tests ~$0.25-$1.00 each.
- **Run time:** Commission ~1-3 min. E2E tests ~1-5 min each.
- **Determinism:** LLM output varies. Checks use keyword grep, not exact strings. A test that passes 19/20 runs is still useful as a smoke test.
- **CLAUDECODE variable:** Must be unset when running tests from inside a Claude Code session.
