---
id: 120
title: build_dispatch helper — structured dispatch assembly (Phase 2 of issue #63)
status: done
source: anthropics/claude-code (local) issue #63 — fuzzy prose dispatch template causes silent failures
score: 0.70
started: 2026-04-13T21:19:53Z
worktree: .worktrees/spacedock-ensign-build-dispatch-structured-helper
mod-block: merge:pr-merge
pr: #90
---

Replace the prose-wearing-code `Agent()` dispatch template in the Claude first-officer runtime adapter with a structured helper. The helper owns deterministic scaffolding (name derivation, team_name wiring, stage definition extraction, guardrail paragraphs, completion rubric); the FO supplies judgment fragments (checklist, feedback context, scope notes) as JSON on stdin; the helper emits a validated dispatch JSON object that the FO forwards to `Agent()` verbatim. This is Phase 2 of local issue #63.

## Packaging — `claude-team build` subcommand (2026-04-13 decision)

The helper ships as a new subcommand on the existing `skills/commission/bin/claude-team` script, not as a standalone `build_dispatch` binary. Rationale:

- Every other planned team-dispatch helper already lives under `claude-team` (`context-budget` today; `verify-member` from #119; `health` from #143). A single `claude-team --help` surface for all dispatch-adjacent helpers.
- Plugin install paths reference `skills/commission/bin/` as-is; adding one new sibling binary requires a scaffolding-reference update, adding a subcommand does not.
- Future codex equivalents (e.g., a `codex-team build` or `codex-agent build` sibling) get the same shape for free.

### Code sharing with `status` via `importlib`

The helper needs workflow-file parsing primitives that already exist in `skills/commission/bin/status`:

- `parse_frontmatter(filepath)` — status:73
- `parse_stages_block(filepath)` — status:97
- `load_active_entity_fields(path, git_root)` — status:229 (worktree-aware reads)
- `find_git_root(start_dir)` — status:904

Do NOT extract these into a new `skills/commission/lib/` package — the project relies on the current skills/bin layout for reference/install stability, and fewer directories is the stated preference. Instead, `claude-team` should import them sideways from `status` using `importlib.util.spec_from_file_location`. This works because `status` has an `if __name__ == '__main__': main()` guard at line 1207 — importing as a module skips the CLI path.

Reference shape (ideation to finalize):

```python
import importlib.util
from pathlib import Path

_here = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_status_lib", _here / "status")
_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_status)
# _status.parse_frontmatter(...) etc.
```

Caveats the ideation must resolve:

1. The import contract between `claude-team` and `status` becomes a runtime-only API. A small pytest should exercise each borrowed function via the sibling-import path so signature drift fails a static test, not a live dispatch.
2. Document the borrowed surface (which `status` functions are "public" for `claude-team`) in a comment at the top of `claude-team` or in a short section of the script's own help text. Otherwise a future edit to `status` may break `claude-team` silently.
3. The same `importlib` pattern is fine for future consumers (e.g., codex-side helpers) but past 2–3 consumers the argument for a proper library module gets stronger; revisit if that happens.

## Problem Statement

The Claude first-officer runtime adapter's `Agent()` dispatch template (lines 51-57 of `claude-first-officer-runtime.md`) mixes four notations in a single code block: `{curly_braces}` for variable substitution, `[BRACKETS imperative]` for copy-paste instructions, `{if condition: '...'}` for conditional logic, and surrounding prose for behavioral context. The FO model must parse all four, resolve conditionals, distinguish slots from instructions, and assemble the final `Agent()` call in one shot. Every assembly step is a place a field can get dropped or mangled silently.

Issue #63 documents the canonical failure: the FO omitted the `name` parameter from `Agent()`, causing a silent sidechain downgrade where the dispatched agent ran outside the team without any error signal. Task #115 documented the completion-signal variant: the team-mode `SendMessage(to="team-lead")` instruction was dropped during assembly, so the FO's idle guardrail waited forever for a message that was never emitted. Both bugs share the same root cause — an LLM-facing template that embeds imperative logic in prose and fails silently when assembly goes wrong.

Task 115 patched the completion-signal symptom; task 118 patched the PR body template. A structured helper that owns deterministic assembly is the deeper treatment that makes the patch-a-symptom pattern unnecessary for dispatch.

## Design sketch (from issue #63)

The helper reads:
- The entity file (extracts title, worktree, entity file path)
- The workflow README (extracts the `### {stage}` subsection verbatim)
- The stage metadata (derives `subagent_type` from `agent:` field, `worker_key`, `name`, `branch`)
- LLM-supplied JSON on stdin (`checklist`, `feedback_context`, `scope_notes`)

The helper validates:
- If `--team` set, `name` must be derivable
- If the stage is a worktree stage, worktree path must exist
- If the stage has `feedback-to`, feedback context must be present
- etc.

The helper emits final dispatch JSON to stdout:

```json
{
  "subagent_type": "spacedock:ensign",
  "name": "spacedock-ensign-{slug}-{stage}",
  "team_name": "{team}",
  "description": "...",
  "prompt": "<fully assembled prompt>"
}
```

The FO calls `Agent()` with those exact fields. No interpretation, no assembly, no conditional branches to forget.

## Open Questions — Resolved

### OQ-1: Helper failure mode

**Resolution:** The runtime adapter will contain a "Break-Glass Manual Dispatch" subsection immediately after the `claude-team build` invocation instructions within the `## Dispatch Adapter` section. The break-glass procedure is:

> **Break-Glass Manual Dispatch:** If `claude-team build` exits non-zero or is unavailable (e.g., Python error, missing file), fall back to direct `Agent()` assembly using the template below. This is a degraded mode — report the helper failure to the captain before proceeding.
>
> ```
> Agent(
>     subagent_type="{dispatch_agent_id}",
>     name="{worker_key}-{slug}-{stage}",
>     team_name="{team_name}",
>     prompt="You are working on: {entity title}\n\nStage: {stage}\n\n### Stage definition:\n\n{copy stage subsection from README verbatim}\n\nRead the entity file at {entity_file_path}.\n\n### Completion checklist\n\n{numbered checklist}\n\n### Completion Signal\n\nSendMessage(to=\"team-lead\", message=\"Done: {entity title} completed {stage}. Report written to {entity_file_path}.\")"
> )
> ```
>
> The break-glass template is intentionally minimal — it omits worktree instructions, feedback-to context, and scope notes. These are acceptable losses in a degraded fallback.

The break-glass section lives at the end of the `## Dispatch Adapter` section, clearly marked as a fallback.

### OQ-2: Helper scope discipline

**Charter:** `claude-team build` assembles a single validated dispatch JSON object from filesystem state and FO-supplied judgment fragments, then exits.

**Non-goals (the helper MUST NEVER):**
- Execute git operations (no `git commit`, `git worktree add`, `git checkout`, etc.)
- Run `status --set` or modify entity frontmatter
- Call `TeamCreate`, `TeamDelete`, or any team lifecycle operation
- Call `Agent()`, `SendMessage`, or any dispatch/communication tool
- Write to any file (it is a pure reader + stdout emitter)
- Maintain persistent state between invocations (no cache, no lockfile, no tempfile)
- Make network requests of any kind
- Exit with side effects beyond stdout (valid JSON) and stderr (error messages)

### OQ-3: Schema versioning

**Mechanism:** Both stdin input and stdout output carry a top-level `"schema_version": 1` integer field.

- **Field name:** `schema_version`
- **Default behavior on unknown version:** The helper exits with code 2 and a stderr message: `error: unsupported input schema_version {N}, expected {M}`. The FO falls back to the break-glass procedure.
- **Runtime adapter assertion:** The adapter prose instructs the FO to set `"schema_version": 1` on every stdin payload. If the helper's output contains a different `schema_version` than the adapter expects, the FO treats it as a helper error and falls back to break-glass.
- **What constitutes a "breaking change":** Adding a required input field, removing an output field, or changing the semantics of an existing field. Adding optional input fields or adding output fields is non-breaking and does NOT increment the version.
- **Precedent:** The repo uses integer versioning for the `id-style` field in workflow README frontmatter — simple and sufficient for internal tooling.

### OQ-4: Bootstrap

**Confirmed:** The plugin install path is `skills/commission/bin/claude-team`. The `claude-team` script is already executable and lives alongside `status` in the same `bin/` directory. No new install-path registration is needed — any reference to `{spacedock_plugin_dir}/skills/commission/bin/` already covers both scripts.

The FO invokes the helper as:

```bash
echo '{...json...}' | {spacedock_plugin_dir}/skills/commission/bin/claude-team build --workflow-dir {workflow_dir}
```

The `{spacedock_plugin_dir}` is resolved the same way the FO already resolves it for `status` and `claude-team context-budget` — from the plugin directory that contains the active skill files. No additional bootstrap is required.

### OQ-5: Multi-runtime strategy

**Decision: Claude-specific.** `claude-team build` emits JSON shaped for Claude Code's `Agent()` tool. A future `codex-team build` (or a `--runtime codex` flag) is a separate task.

**Justification:** The structural differences between Claude `Agent()` and Codex `spawn_agent()` are significant enough that a single output schema cannot serve both without conditional fields that defeat the purpose of structured dispatch:

| Dimension | Claude `Agent()` | Codex `spawn_agent()` |
|-----------|------------------|----------------------|
| Worker identity | `subagent_type` (packaged skill name) | `agent_type="worker"` (always generic) |
| Naming | `name` parameter on `Agent()` | No `name` param; identity is the returned handle |
| Team mode | `team_name` parameter, SendMessage completion | No teams; `wait_agent` for completion |
| Context | Inherits parent context by default | `fork_context=false` required |
| Prompt shape | Single `prompt` string | `message` string with role-resolution preamble |
| Completion signal | `SendMessage(to="team-lead", ...)` in prompt | Return value from `wait_agent` |

Trying to unify these into one output schema would reintroduce the same "conditional logic in data" anti-pattern the helper is designed to eliminate. Codex adapter support is explicitly out of scope (already listed in "Out of scope").

## Input JSON Schema (stdin)

The FO assembles this JSON and pipes it to `claude-team build` on stdin.

| Field | Type | Required | Default | Purpose |
|-------|------|----------|---------|---------|
| `schema_version` | int | yes | — | Must be `1`. Helper rejects unknown versions. |
| `entity_path` | string | yes | — | Absolute path to the entity `.md` file (main-branch copy). |
| `workflow_dir` | string | yes | — | Absolute path to the workflow directory containing `README.md`. |
| `stage` | string | yes | — | Target stage name (e.g., `"ideation"`, `"implementation"`). |
| `checklist` | list[string] | yes | — | Numbered checklist items the FO built from stage outputs and entity ACs. |
| `team_name` | string | no | `null` | Team name from `TeamCreate`. Null or absent means bare mode. |
| `feedback_context` | string | no | `null` | Reviewer findings to relay when dispatching into a `feedback-to` target stage. Required when the stage has `feedback-to`. |
| `scope_notes` | string | no | `null` | FO-supplied additional context (e.g., "focus on the naming validation rule"). |
| `bare_mode` | bool | no | `false` | When true, omit team-mode fields (`team_name`, `name`, completion signal) from the prompt. |

**Refusal behavior:** If a required field is missing or null, the helper exits with code 1 and stderr: `error: missing required field '{field_name}'`. If `stage` names a feedback-to target and `feedback_context` is absent, the helper exits with code 1 and stderr: `error: stage '{stage}' has feedback-to but feedback_context is missing`.

## Output JSON Schema (stdout)

The helper emits exactly this JSON to stdout on success (exit 0). The FO passes the fields to `Agent()` verbatim.

| Field | Type | Always present | Derivation |
|-------|------|----------------|------------|
| `schema_version` | int | yes | Always `1`. |
| `subagent_type` | string | yes | From the stage's `agent:` field in the README frontmatter, defaulting to `spacedock:ensign`. |
| `name` | string | yes in team mode | `{worker_key}-{slug}-{stage}`. Derived from `subagent_type` (`:` → `-` for `worker_key`), entity slug (from filename), and stage name. |
| `team_name` | string | only in team mode | Passed through from input. Omitted when `bare_mode` is true or `team_name` is null. |
| `description` | string | yes | `"{entity_title}: {stage}"` — short, for display only. |
| `prompt` | string | yes | Fully assembled dispatch prompt (see below). |

### Prompt Assembly

The `prompt` field is assembled deterministically from these components in order:

1. **Header:** `"You are working on: {entity_title}\n\nStage: {stage}\n\n"`
2. **Stage definition:** `"### Stage definition:\n\n{stage_subsection_from_README}\n\n"` — the full `### {stage}` subsection from the workflow README, copied verbatim.
3. **Worktree instructions** (conditional, only when the stage has `worktree: true`): working directory, branch name, path constraints, scaffolding guardrails.
4. **Entity read instruction:** `"Read the entity file at {entity_path} for the current spec.\n\n"` — for worktree stages, `entity_path` points to the worktree copy.
5. **Do-not-modify block** (always): `"Do NOT modify YAML frontmatter in entity files.\nDo NOT modify files under agents/ or references/ — these are plugin scaffolding.\n\n"`
6. **Feedback context** (conditional, only when `feedback_context` is present): `"### Feedback from prior review\n\n{feedback_context}\n\n"`
7. **Scope notes** (conditional, only when `scope_notes` is present): embedded as a paragraph after feedback context.
8. **Completion checklist:** `"### Completion checklist\n\nWrite a ## Stage Report section into the entity file when done.\nMark each: DONE, SKIPPED (with rationale), or FAILED (with details).\n\n{numbered_checklist}\n\n### Summary\n{brief description}\n\nEvery checklist item must appear in your report. Do not omit items."`
9. **Completion signal** (conditional, only in team mode): `"\n\n### Completion Signal\n\nThis is a team-mode dispatch. When you finish (after all commits and stage report writes are done), your last action MUST be:\n\n    SendMessage(to=\"team-lead\", message=\"Done: {entity_title} completed {stage}. Report written to {entity_path}.\")\n\nPlain text only. No JSON. Until you send this message, the first officer keeps waiting for that explicit completion message. Idle notifications are normal between-turn state while it waits."`

### Worked Example

Input (fictional task #999 at ideation stage, team mode):
```json
{
  "schema_version": 1,
  "entity_path": "/Users/dev/project/docs/plans/widget-cache.md",
  "workflow_dir": "/Users/dev/project/docs/plans",
  "stage": "ideation",
  "checklist": [
    "1. Define the cache eviction strategy",
    "2. Specify the cache key format",
    "3. Write acceptance criteria with test plan"
  ],
  "team_name": "moonlit-giggling-pillow",
  "feedback_context": null,
  "scope_notes": null,
  "bare_mode": false
}
```

Output:
```json
{
  "schema_version": 1,
  "subagent_type": "spacedock:ensign",
  "name": "spacedock-ensign-widget-cache-ideation",
  "team_name": "moonlit-giggling-pillow",
  "description": "widget cache layer: ideation",
  "prompt": "You are working on: widget cache layer\n\nStage: ideation\n\n### Stage definition:\n\nA task moves to ideation when a pilot starts fleshing out the idea: clarify the problem, explore approaches, and produce a concrete description of what \"done\" looks like.\n\n- **Inputs:** The seed description and any relevant context ...\n- **Outputs:** A fleshed-out task body with problem statement ...\n- **Good:** Clearly scoped, actionable ...\n- **Bad:** Vague hand-waving ...\n\nYour working directory is /Users/dev/project/docs/plans (no worktree for ideation stage). All file reads and writes MUST use paths under /Users/dev/project/docs/plans.\nDo NOT modify YAML frontmatter in entity files.\nDo NOT modify files under agents/ or references/ — these are plugin scaffolding. Reading is fine.\n\nRead the entity file at /Users/dev/project/docs/plans/widget-cache.md for the current spec (problem statement, acceptance criteria, design). Stage reports from prior cycles are appended at the end of the file — you do not need to read them for your current assignment.\n\n### Completion checklist\n\nWrite a ## Stage Report section into the entity file when done.\nMark each: DONE, SKIPPED (with rationale), or FAILED (with details).\n\n1. Define the cache eviction strategy\n2. Specify the cache key format\n3. Write acceptance criteria with test plan\n\n### Summary\n{brief description of what was accomplished}\n\nEvery checklist item must appear in your report. Do not omit items.\n\n### Completion Signal\n\nThis is a team-mode dispatch. When you finish (after all commits and stage report writes are done), your last action MUST be:\n\n    SendMessage(to=\"team-lead\", message=\"Done: widget cache layer completed ideation. Report written to /Users/dev/project/docs/plans/widget-cache.md.\")\n\nPlain text only. No JSON. Until you send this message, the first officer keeps waiting for that explicit completion message. Idle notifications are normal between-turn state while it waits."
}
```

## Validation Rules

The helper enforces these rules before emitting output. On any violation, the helper exits with the stated code and prints the stated message to stderr. No partial output is written to stdout.

1. **Required fields present.** All fields marked required in the input schema must be present and non-null. Exit 1: `error: missing required field '{field_name}'`.
2. **Schema version supported.** `schema_version` must equal `1`. Exit 2: `error: unsupported input schema_version {N}, expected 1`.
3. **Stage exists in workflow.** The `stage` value must match a `### {stage}` heading in the workflow README. Exit 1: `error: stage '{stage}' not found in {workflow_dir}/README.md`.
4. **Worktree stage has worktree path.** If the stage has `worktree: true` in the README frontmatter, the entity's `worktree` frontmatter field must be non-empty AND the directory must exist on disk. Exit 1: `error: worktree stage '{stage}' but entity has no worktree path` or `error: worktree path '{path}' does not exist`.
5. **Feedback context required for feedback-to stages.** If the stage being dispatched is the target of another stage's `feedback-to` (i.e., the entity is being re-dispatched after a rejection), and `feedback_context` is null or empty, exit 1: `error: dispatching to feedback target stage '{stage}' but feedback_context is missing`. Note: this rule fires when the FO signals that this is a feedback re-dispatch, not on every dispatch to a stage that happens to be a feedback-to target. The helper infers this from the presence of `feedback_context` being expected but missing — the FO is responsible for supplying it when routing a rejection.
6. **Subagent type matches stage agent field.** If the stage defines `agent: {value}` in the README frontmatter, `subagent_type` must be set to that value. If absent, default to `spacedock:ensign`. This is derived, not validated against input — the helper computes it internally.
7. **Name length and safety.** The derived `name` (`{worker_key}-{slug}-{stage}`) must be <= 63 characters and match `^[a-z0-9][a-z0-9-]*[a-z0-9]$` (filesystem-safe, no leading/trailing hyphens). Exit 1: `error: derived name '{name}' exceeds 63 characters` or `error: derived name '{name}' contains invalid characters`.
8. **Team name non-empty in team mode.** If `bare_mode` is false and `team_name` is null or empty, exit 1: `error: team mode requires team_name`.
9. **Checklist non-empty.** The `checklist` list must contain at least one item. Exit 1: `error: checklist must not be empty`.
10. **Entity file readable.** The `entity_path` must point to a readable file. Exit 1: `error: entity file not readable at '{path}'`.
11. **Workflow README readable.** `{workflow_dir}/README.md` must be a readable file. Exit 1: `error: workflow README not found at '{path}'`.

## Code Sharing Implementation

### Sideways import from `status`

The `claude-team` script imports four functions from the sibling `status` script using `importlib`. This works because `status` guards its CLI path with `if __name__ == '__main__': main()` (line 1207).

```python
# --- Shared functions imported from sibling `status` script ---
# Borrowed surface: parse_frontmatter, parse_stages_block,
#     load_active_entity_fields, find_git_root
# These functions are tested via the sibling-import path in
# tests/test_claude_team.py::test_status_sibling_import_*
import importlib.util
from pathlib import Path

_here = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_status_lib", _here / "status")
_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_status)

parse_frontmatter = _status.parse_frontmatter
parse_stages_block = _status.parse_stages_block
load_active_entity_fields = _status.load_active_entity_fields
find_git_root = _status.find_git_root
```

### Extension needed: `parse_stages_block` drops fields

The current `parse_stages_block` (status:183-195) constructs its result dict with only `name`, `worktree`, `concurrency`, `gate`, `terminal`, and `initial`. It drops `feedback-to`, `agent`, and `fresh` fields that the raw YAML parse captures. The `build` subcommand needs these fields.

**Fix:** Extend the post-processing loop in `parse_stages_block` to pass through `feedback-to`, `agent`, and `fresh` as optional string fields (preserving their raw values). This is a backward-compatible change — existing callers that don't read these fields are unaffected. The implementation task should include this as a prerequisite patch to `status`.

### Pytest signature-drift guard

A static test in `tests/test_claude_team.py` exercises the sibling-import path and asserts that each borrowed function is callable with its expected signature:

```python
def test_status_sibling_import_parse_frontmatter():
    """Guard against signature drift in status.parse_frontmatter."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_status_lib", STATUS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.parse_frontmatter)
    # Smoke test: parse a known fixture
    result = mod.parse_frontmatter(FIXTURE_ENTITY_PATH)
    assert isinstance(result, dict)
    assert "title" in result
```

One such test per borrowed function (4 tests total). These tests break on import failure or signature change, catching drift before it reaches a live dispatch.

## Runtime Adapter Changes

### Lines to replace

The current dispatch template in `claude-first-officer-runtime.md` (the `## Dispatch Adapter` section, lines 39-57) contains the `Agent(...)` code block with all four mixed notations. The replacement preserves the section heading, sequencing rule, team health check, and idle guardrail — only the dispatch-assembly instructions change.

### New prose (replaces lines 48-57)

The new instructions in the `## Dispatch Adapter` section, after the team health check paragraph:

> **Dispatch assembly via `claude-team build`:**
>
> 1. Assemble the input JSON from the entity, stage, and your judgment:
>    ```json
>    {
>      "schema_version": 1,
>      "entity_path": "{absolute path to entity file}",
>      "workflow_dir": "{absolute path to workflow directory}",
>      "stage": "{target stage name}",
>      "checklist": ["1. ...", "2. ..."],
>      "team_name": "{team_name or null if bare mode}",
>      "feedback_context": "{reviewer findings or null}",
>      "scope_notes": "{additional context or null}",
>      "bare_mode": {true if bare mode, false otherwise}
>    }
>    ```
> 2. Pipe the JSON to the helper:
>    ```
>    echo '<json>' | {spacedock_plugin_dir}/skills/commission/bin/claude-team build --workflow-dir {workflow_dir}
>    ```
> 3. On exit 0, parse the stdout JSON and call `Agent()` with the emitted fields verbatim:
>    ```
>    Agent(
>        subagent_type=output.subagent_type,
>        name=output.name,           // omit if bare mode (field absent)
>        team_name=output.team_name, // omit if bare mode (field absent)
>        prompt=output.prompt
>    )
>    ```
> 4. On non-zero exit, read stderr for the error message, report to captain, and fall back to the Break-Glass Manual Dispatch procedure below.
>
> **Break-Glass Manual Dispatch:** If `claude-team build` exits non-zero or is unavailable, fall back to direct `Agent()` assembly. Report the helper failure to the captain. Use this minimal template:
> ```
> Agent(
>     subagent_type="{dispatch_agent_id}",
>     name="{worker_key}-{slug}-{stage}",
>     team_name="{team_name}",
>     prompt="You are working on: {entity title}\n\nStage: {stage}\n\n### Stage definition:\n\n{copy stage subsection from README verbatim}\n\nRead the entity file at {entity_file_path}.\n\n### Completion checklist\n\n{numbered checklist}\n\n### Completion Signal\n\nSendMessage(to=\"team-lead\", message=\"Done: {entity title} completed {stage}. Report written to {entity_file_path}.\")"
> )
> ```
> The break-glass template omits worktree instructions, feedback context, and scope notes. Use only when the helper is unavailable.

## Acceptance Criteria

1. **AC-1: Subcommand exists.** `skills/commission/bin/claude-team build --help` prints usage and exits 0. No new sibling binary, no `lib/` directory.
   - Test: `test_claude_team_build_help` (pytest, `tests/test_claude_team.py`)

2. **AC-2: Reads entity, README, stdin; emits JSON.** Given valid stdin JSON, entity file, and workflow README, the helper emits well-formed dispatch JSON to stdout and exits 0.
   - Test: `test_build_normal_dispatch` (pytest, `tests/test_claude_team.py`)

3. **AC-3: Team-mode dispatch includes name and team_name.** When `team_name` is provided and `bare_mode` is false, the output includes `name` and `team_name` fields and the prompt includes the completion signal.
   - Test: `test_build_team_mode_dispatch` (pytest)

4. **AC-4: Bare-mode dispatch omits team fields.** When `bare_mode` is true, the output omits `name` and `team_name` and the prompt omits the completion signal.
   - Test: `test_build_bare_mode_dispatch` (pytest)

5. **AC-5: Worktree-stage dispatch includes worktree instructions.** When the stage has `worktree: true`, the prompt includes working directory, branch, and path constraints.
   - Test: `test_build_worktree_stage_dispatch` (pytest)

6. **AC-6: Feedback-stage dispatch includes feedback context.** When `feedback_context` is present, the prompt includes a feedback section.
   - Test: `test_build_feedback_dispatch` (pytest)

7. **AC-7: Each validation rule enforced.** Every rule from the Validation Rules section is enforced with the specified exit code and stderr message.
   - Tests: one pytest per rule, 11 tests total (`test_build_validation_rule_{N}` in `tests/test_claude_team.py`)

8. **AC-8: Schema version checked.** Input with `schema_version: 2` is rejected with exit 2.
   - Test: `test_build_schema_version_rejection` (pytest)

9. **AC-9: Sibling import works and is guarded.** The `importlib` import from `status` succeeds, and 4 signature-drift tests pass.
   - Tests: `test_status_sibling_import_{parse_frontmatter,parse_stages_block,load_active_entity_fields,find_git_root}` (pytest)

10. **AC-10: `parse_stages_block` extended.** The function now includes `feedback-to`, `agent`, and `fresh` fields in its output.
    - Test: `test_parse_stages_block_extra_fields` (pytest, using the `docs/plans/README.md` fixture which has `feedback-to: implementation` and `fresh: true`)

11. **AC-11: Runtime adapter updated.** `claude-first-officer-runtime.md` instructs the FO to use `claude-team build` for dispatch assembly and contains the break-glass fallback.
    - Test: `test_assembled_claude_first_officer_has_structured_dispatch` (static, `tests/test_agent_content.py`)

12. **AC-12: Break-glass documented.** The runtime adapter contains a "Break-Glass Manual Dispatch" section with a minimal direct `Agent()` template.
    - Test: `test_assembled_claude_first_officer_has_break_glass_dispatch` (static, `tests/test_agent_content.py`)

13. **AC-13: Existing suites green.** All existing tests pass: `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py`, `test_dispatch_completion_signal.py`.
    - Test: `make test-static` plus selective E2E re-runs.

14. **AC-14: E2E structured dispatch.** A new E2E test drives the full path: FO assembles stdin, invokes `claude-team build`, forwards output to `Agent()`, worker completes, entity advances.
    - Test: `tests/test_structured_dispatch.py` (E2E via `claude -p`)

## Test Plan

| Test name | Harness | Asserts | Cost |
|-----------|---------|---------|------|
| `test_claude_team_build_help` | pytest | `claude-team build --help` exits 0, prints usage | low |
| `test_build_normal_dispatch` | pytest | Valid input → valid output JSON with all expected fields | low |
| `test_build_team_mode_dispatch` | pytest | Team mode → `name`, `team_name` present; prompt has SendMessage completion signal | low |
| `test_build_bare_mode_dispatch` | pytest | Bare mode → no `name`/`team_name`; prompt has no completion signal | low |
| `test_build_worktree_stage_dispatch` | pytest | Worktree stage → prompt has working dir, branch, path constraints | low |
| `test_build_feedback_dispatch` | pytest | `feedback_context` present → prompt has feedback section | low |
| `test_build_validation_rule_1` through `_11` | pytest | Each validation rule → correct exit code + stderr message | low (11 tests) |
| `test_build_schema_version_rejection` | pytest | `schema_version: 2` → exit 2 + stderr | low |
| `test_status_sibling_import_parse_frontmatter` | pytest | Import succeeds, function callable, returns dict | low |
| `test_status_sibling_import_parse_stages_block` | pytest | Import succeeds, function callable, returns list | low |
| `test_status_sibling_import_load_active_entity_fields` | pytest | Import succeeds, function callable | low |
| `test_status_sibling_import_find_git_root` | pytest | Import succeeds, function callable | low |
| `test_parse_stages_block_extra_fields` | pytest | `feedback-to`, `agent`, `fresh` preserved in output | low |
| `test_assembled_claude_first_officer_has_structured_dispatch` | test_agent_content.py | Adapter references `claude-team build`, has dispatch JSON shape | low |
| `test_assembled_claude_first_officer_has_break_glass_dispatch` | test_agent_content.py | Adapter has "Break-Glass Manual Dispatch" with minimal Agent() template | low |
| `test_structured_dispatch_e2e` | E2E (claude -p) | Full path: FO → helper → Agent() → worker completes → entity advances | high (live runtime, ~$2-3) |

**Total unit/static tests:** ~25 new tests. **Total E2E:** 1 new test.

## Interaction with Adjacent Tasks

- **#119 (`claude-team verify-member`):** Can land in parallel. Both add subcommands to the same `claude-team` script, but they don't share code beyond the existing argparse structure. The `build` subcommand does NOT depend on `verify-member`. Recommend: either can merge first; if both are in flight simultaneously, the second PR rebases against the first's argparse additions. No ordering constraint.

- **#143 (`claude-team health`):** Can land in parallel. Same reasoning — independent subcommand on the same script. No code dependency between `build` and `health`. Recommend: no ordering constraint.

- **Recommended merge order:** No strict dependency, but #119 (band-aids) landing first is slightly preferred because it adds the post-dispatch `verify-member` check that complements the structured dispatch (the helper ensures `name` is always emitted; `verify-member` confirms it took effect). This is a defense-in-depth preference, not a hard dependency.

## Scope Boundary

**In scope:**
- New `build` subcommand on `skills/commission/bin/claude-team`
- Extension to `parse_stages_block` in `status` (add `feedback-to`, `agent`, `fresh` passthrough)
- Update to `skills/first-officer/references/claude-first-officer-runtime.md` (dispatch assembly instructions + break-glass fallback)
- New unit tests in `tests/test_claude_team.py`
- New static assertions in `tests/test_agent_content.py`
- New E2E test `tests/test_structured_dispatch.py`

**Out of scope (deferred):**
- **Codex runtime adapter:** Not updated by this task. The Codex adapter (`codex-first-officer-runtime.md`) continues using its existing `spawn_agent()` prose template. A future `codex-team build` or `--runtime codex` flag is a separate task (per OQ-5 resolution).
- **Old template removal:** This task does NOT remove the old `Agent()` dispatch template from the adapter. The break-glass section preserves a minimal version of it as a fallback. The old full template (with all four notations) is replaced by the `claude-team build` instructions. Coexistence is temporary — the break-glass template is intentionally simplified and serves as the degraded fallback, not the primary path.
- **Generalizing to other fuzzy-template sites:** Feedback rejection flow, gate presentation, event loop — Phase 4 of issue #63.
- **Mod files:** PR body template — task 118.

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **Helper outage blocks all dispatches.** A bug in the Python helper (import error, syntax error, missing dependency) makes every dispatch fail. | Medium | High | Break-glass manual-dispatch fallback documented in the adapter. Unit tests for every code path. The helper has zero external dependencies beyond Python stdlib and the `status` sibling. |
| 2 | **Stdin JSON schema churn.** Frequent changes to required fields break the adapter prose and existing FO sessions. | Low | Medium | Schema versioning (OQ-3). Adding optional fields is non-breaking. The `schema_version` field provides a hard check. |
| 3 | **Sibling import drift.** A refactor of `parse_frontmatter` or `parse_stages_block` in `status` silently breaks `claude-team build`. | Medium | High | Four signature-drift guard tests in `tests/test_claude_team.py`. These run in `make test-static` and catch breakage before it reaches a live dispatch. The borrowed surface is documented in a comment block at the import site. |
| 4 | **Static content test invalidation.** Replacing the adapter's `Agent()` template changes the text that `test_agent_content.py` assertions match. | High (certain) | Low | The implementation must update existing assertions in `test_agent_content.py` that reference the old template wording. Specifically: `test_assembled_claude_first_officer_has_team_health_check` (AC1 asserts `test -f` which stays), `test_assembled_claude_first_officer_dispatch_template_has_team_mode_completion_signal` (must be updated to check the break-glass template or the helper instruction). Each affected test is enumerated in the implementation checklist. |
| 5 | **`parse_stages_block` extension regresses existing callers.** Adding `feedback-to`, `agent`, `fresh` fields to the output dict could break callers that iterate over dict keys. | Low | Low | The extension adds optional keys to dicts in a list. Existing callers use `.get()` or explicit key access — they never iterate all keys. The implementation must verify this by grepping all `parse_stages_block` call sites. |

## Implementation Notes (gate-approved 2026-04-13)

The ideation gate was approved with seven follow-up items from the staff review. These are mandatory for the implementer to address; they are not optional polish.

1. **Correct the line references to the old dispatch template.** The ideation quotes "lines 48-57" (and in one place "lines 51-57") of `skills/first-officer/references/claude-first-officer-runtime.md` as the replacement target. The reviewer confirmed the actual `Agent(...)` block spans **lines 50-57** (line 50 opens the code block, lines 51-56 hold the Agent call, line 57 closes). Re-verify against the current file at implementation start and update any checklist or assertion that references specific line numbers.

2. **Spell out worktree path and branch derivation in the prompt-assembly rules.** Prompt component #3 (worktree instructions, conditional on `worktree: true`) must name where each value comes from:
   - `worktree_path` is read from the entity frontmatter's `worktree` field (relative or absolute — specify one and normalize).
   - `branch` is derived as `{worker_key}/{slug}`, where `worker_key` is the dispatch_agent_id with `:` replaced by `-` (per the existing claude-first-officer runtime adapter convention at around line 30-35).
   - Cross-reference to Validation Rule 4 (worktree path must exist on disk) so the reader sees which field is being validated.

3. **Resolve the feedback-to detection ambiguity.** Validation Rule 5 fires when the stage being dispatched is a feedback-to target, but the stdin schema as written doesn't carry an explicit "this is a feedback re-dispatch" flag. Pick one of the following and encode it in both the input schema and the rule:
   - **Option A (recommended):** FO sets `is_feedback_reflow: true` in stdin when routing a rejection. Helper trusts the flag. Simple, explicit.
   - **Option B:** Helper scans the workflow README for any stage whose `feedback-to` field matches the target stage name, then requires `feedback_context` to be present when that pattern holds. More magical; helper must read the README.
   - Whichever is chosen, the worked example in the Output JSON Schema section should include a feedback-reflow example alongside the ideation example.

4. **Add a break-glass fallback test.** AC-12 asserts the break-glass prose exists in the runtime adapter. That is not enough. Add one of:
   - **Unit test** in `tests/test_claude_team.py` that forces the helper to exit 1 (e.g., via malformed stdin) and asserts the FO's break-glass prose is triggered — this requires a small harness because the FO's recovery path is driven by the runtime prose, not code. If a pure unit test is not feasible, use the static-content harness to assert the break-glass template is reachable and syntactically usable as an `Agent()` call.
   - **Static assertion** that the break-glass template in the adapter, when rendered with stub values, produces a valid Python function call — parse it with `ast.parse` as a sanity check.

5. **Split the E2E test line in the test-plan table.** The "high ($2-3)" cost cell is ambiguous. Replace with two lines:
   - `test_structured_dispatch_happy_path_e2e` — FO assembles JSON, calls helper, forwards to Agent(), minimal worker completes. Estimated cost **$0.50–$1** on haiku/low.
   - `test_structured_dispatch_multistage_e2e` — deferred to #134 (runtime-specific-tests-on-pr) rather than a new standalone E2E, because the multi-stage path is already exercised by `test_dispatch_completion_signal.py` and the full FO pipeline. The implementer should confirm the existing completion-signal test goes green after the helper lands, and note this in the stage report.

6. **Document the FO's input-assembly guardrail.** The helper validates its input, but the FO's prose-based JSON assembly is still a failure vector: if the FO sets `bare_mode: false` when teams are not active (or vice versa), the helper rejects, the FO falls back to break-glass, and the completion signal can be lost. Either:
   - Add a one-sentence guardrail note in the new runtime-adapter prose at the place where the FO is told to assemble stdin: "the `bare_mode` field must match the current dispatch context — never infer it from the stage, always from the live team state." and
   - Add a static assertion in `tests/test_agent_content.py` that the new prose contains that guardrail sentence verbatim.

7. **Resolve the reuse path (SendMessage) scope question.** The runtime adapter has two dispatch surfaces: initial `Agent()` dispatch and `SendMessage(to="team-lead")` reuse-advance of an already-alive ensign. The ideation only covers the initial `Agent()` path. Decide, in this task, which of the following the implementation ships:
   - **Option X (narrow):** `claude-team build` serves only initial `Agent()` dispatch. Reuse continues to use the existing prose-based `SendMessage` template in the runtime adapter. The runtime adapter then has two dispatch surfaces — document this explicitly. Future task to unify.
   - **Option Y (wide):** `claude-team build` serves both paths. Output schema gains a `dispatch_kind: "agent"|"send_message"` field (or a sibling `claude-team send` subcommand). Single dispatch surface in the adapter.
   - Option X is the lower-risk landing for this task; Option Y is the cleaner end-state. Pick one before implementation starts. If Option X, add a task to the Related section filing the eventual Option Y work.

These notes are all implementable without another ideation cycle. Any item that cannot be resolved during implementation (e.g., discovering a structural blocker for item 7) must be raised to the captain before writing code, not silently deferred.

- Codex and Gemini runtime adapter updates (separate tasks after this lands).
- Generalizing the pattern to other fuzzy-template sites (feedback rejection flow, gate presentation, event loop) — Phase 4 of issue #63.
- Mod files (`pr-merge.md`) — separate concern (task 118).

## CI green gate

This task must green `test_dispatch_completion_signal.py` in `make test-live-claude`. The test is currently SKIPPED in the Makefile because the FO drops the `SendMessage(to="team-lead")` completion-signal block from its dispatch prompt — confirmed on both haiku and opus (2026-04-13). The structured helper will make the completion-signal block deterministic, which should resolve this. The implementer must verify the test passes end-to-end and restore it to the active `test-live-claude` target before closing.

## Related

- anthropics/claude-code local issue #63 — umbrella, this is Phase 2.
- Task 119 — Phase 1 band-aids (should land first).
- Task 115 — first completion-signal patch (precedent for the patch-a-symptom pattern that this task replaces).
- Task 118 — PR body template (adjacent fuzzy-template anti-pattern).
- Task 143 — `claude-team health` subcommand (parallel sibling subcommand).

## Stage Report

### Checklist

1. **Restate problem statement with concrete example:** DONE. Problem statement section uses the #63 sidechain-downgrade bug as the canonical illustration and references #115 completion-signal bug as the second instance. Both trace to the same root cause: four mixed notations in one code block.

2. **Survey current Agent() dispatch template:** DONE. Identified exact lines 51-57 of `claude-first-officer-runtime.md`. The template mixes `{curly_braces}`, `[BRACKETS imperative]`, `{if condition: '...'}`, and surrounding prose. The FO performs: (a) resolve each `{variable}`, (b) evaluate each `{if}` conditional, (c) interpret each `[INSTRUCTION]` and copy/paste the referenced content, (d) assemble the final Agent() call — four distinct substitution/assembly steps.

3. **Resolve OQ-1 — Helper failure mode:** DONE. Break-glass manual-dispatch procedure specified. Lives at the end of `## Dispatch Adapter` section. Provides a minimal Agent() template that omits worktree instructions, feedback context, and scope notes. FO must report helper failure to captain before using fallback.

4. **Resolve OQ-2 — Helper scope discipline:** DONE. One-sentence charter defined. Eight explicit non-goals stated in negative terms (no git, no status --set, no TeamCreate/TeamDelete, no Agent calls, no file writes, no persistent state, no network, no side effects beyond stdout/stderr).

5. **Resolve OQ-3 — Schema versioning:** DONE. Integer `schema_version` field on both input and output. Version 1. Unknown version → exit 2 + stderr + break-glass fallback. Breaking vs. non-breaking change definition provided. Precedent cited (id-style in README frontmatter).

6. **Resolve OQ-4 — Bootstrap:** DONE. Confirmed plugin install path. The FO invokes `{spacedock_plugin_dir}/skills/commission/bin/claude-team build --workflow-dir {workflow_dir}` with stdin JSON. No additional bootstrap needed — same resolution path as `status` and `context-budget`.

7. **Resolve OQ-5 — Multi-runtime strategy:** DONE. Decision: Claude-specific. Justified with a 6-dimension comparison table showing structural differences between Claude `Agent()` and Codex `spawn_agent()`. Codex adapter support deferred as separate task.

8. **Lock input JSON schema:** DONE. 9 fields enumerated with type, required/optional, default, and purpose. Refusal behavior specified for missing required fields and missing feedback_context on feedback-to stages.

9. **Lock output JSON schema:** DONE. 6 fields enumerated with derivation rules. Prompt assembly order specified (9 components). Worked example provided (task #999 at ideation stage with full input and output JSON).

10. **Validation rules:** DONE. 11 numbered rules with exit codes and stderr message shapes. Covers: required fields, schema version, stage existence, worktree path, feedback context, subagent type derivation, name length/safety, team name in team mode, checklist non-empty, entity file readable, workflow README readable.

11. **Code-sharing implementation:** DONE. Exact `importlib` code shape provided. Borrowed surface documented in a comment block. Pytest signature-drift guard specified (4 tests). Extension to `parse_stages_block` identified as prerequisite (must add `feedback-to`, `agent`, `fresh` passthrough).

12. **Runtime adapter before/after:** DONE. Lines 48-57 identified as the replacement target. New prose specified: 4-step dispatch assembly + break-glass fallback. The new prose tells the FO to assemble stdin JSON, invoke `claude-team build`, forward output to `Agent()`, and fall back to break-glass on error.

13. **Acceptance criteria upgraded:** DONE. 14 numbered criteria, each naming the test(s) that verify it and the harness. Coverage: subcommand existence, normal/team/bare/worktree/feedback dispatch, all 11 validation rules, schema version, sibling imports, parse_stages_block extension, adapter updates, break-glass documentation, existing suite greenness, E2E.

14. **Test plan upgraded:** DONE. Table with 16+ test entries covering: test name, harness, assertion, and cost. ~25 new unit/static tests, 1 new E2E test. Total estimated E2E cost: ~$2-3.

15. **Interaction with adjacent tasks:** DONE. #119 and #143 can both land in parallel. No hard dependency. Recommended merge order: #119 first (defense-in-depth preference, not a constraint).

16. **Scope boundary:** DONE. In-scope: 6 items (subcommand, status extension, adapter update, 3 test files). Out-of-scope: Codex adapter (deferred per OQ-5), old template removal (replaced by break-glass), generalization to other fuzzy-template sites, mod files.

17. **Risk register:** DONE. 5 risks with mitigations: helper outage (break-glass + tests), schema churn (versioning), sibling import drift (signature-drift tests), static test invalidation (enumerated affected tests), parse_stages_block regression (verified callers use .get()).
