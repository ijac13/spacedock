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
- Pipeline Path (with a repo-root-relative path, not an absolute path or template variable)
- `initialPrompt` in frontmatter

### First-officer guardrails

```bash
grep -c "MUST use the Agent tool" .claude/agents/first-officer.md
grep -c "NEVER use.*subagent_type.*first-officer" .claude/agents/first-officer.md
grep -c "TeamCreate" .claude/agents/first-officer.md
grep -c "Report pipeline state ONCE\|Report.*ONCE" .claude/agents/first-officer.md
```

All four must return at least 1. These guardrails prevent known dispatch bugs:

- **Agent tool required**: first officer must use Agent (not SendMessage) to spawn ensigns
- **subagent_type guardrail**: first officer must not clone itself as `first-officer`
- **TeamCreate in Startup**: first officer must create its own team before dispatching
- **Report-once**: first officer must not spam status messages at approval gates

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
