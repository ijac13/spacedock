---
id: 159
title: "FO shared-core: avoid full-file staleness echoes from Read + `status --set` pattern"
status: validation
source: "github.com/clkao/spacedock#96 — `status --set` triggers full-file staleness echoes when FO has Read the entity body; Claude Code dumps entire current file as a system-reminder on the turn after a Bash-driven mutation"
started: 2026-04-15T20:37:50Z
completed:
verdict:
score: 0.80
worktree: .worktrees/spacedock-ensign-status-set-staleness-echo-mitigation
issue: "#96"
pr:
---

When the FO Reads an entity file and then calls `status --set` via Bash to update frontmatter, Claude Code's file-staleness safety net can emit the **entire current file** as a `<system-reminder>` on the next turn. Cost scales linearly with entity body size. Long-running workflows (triage batches, plans with many cycle reports) silently pay tens of thousands of cache-write tokens per frontmatter transition when the echo fires.

## Why it fires (from upstream #96)

- Claude Code tracks files touched by `Read` / `Edit`.
- `Edit` tool changes are diffed; CC knows what changed.
- Bash-driven changes (incl. `status --set`) are opaque, so CC can fall back to dumping the full current state on the next turn so the assistant can't operate on stale knowledge.
- No diff-awareness for external modifications → the reminder may include every line of the file regardless of what changed.

## In-session observations (2026-04-15)

The echo is more nuanced than #96's original description:

1. **`status --set` without a prior full-file `Read` of the same entity** — subsequent system-reminders surface only the **modified region** (frontmatter + lead-body) as a diff, not the full file. CC already has smart diff behavior on some paths; the full-file echo is not universal.
2. **`Grep` + Bash-mutation of the same file** — no staleness echo observed on the next turn (probe file `grep-fixture.md`, 23 KB, section-anchor Grep, `echo >>` mutation, follow-up Bash call). This supports the hypothesis that `Grep` does not register as file-tracking for CC's staleness system.
3. **Full-file `Read` + `status --set` + follow-up Bash** — in the captain-run probe on `/tmp` files, no echo. In the pilot-run probe on `.worktrees/probe-96/workflow/probe-entity.md` (23 KB, project-tree, full Read, `status --set status=done`, follow-up `ls`), also no echo in this session. The #96 echo appears fragile across sessions/harness-versions; the upstream issue remains credible (captain observed it) but reproduction is not universal.
4. **`Read` tool token cap** — Claude Code's `Read` refuses files exceeding ~25k tokens, forcing offset/limit Reads. The #96 scenario therefore concerns medium entities (say 10 KB–60 KB bodies), not arbitrarily large ones.

These observations shift the design away from "mitigate every Bash-mutation echo" toward "mitigate the specific Read-then-mutation pattern, and route the FO away from needing a full-file Read of the entity body at all."

The echo pathway may be session-state-sensitive (harness version, prior tool-call history, file realpath vs. symlink), which is exactly the kind of variable that **discipline-based prose** (prefer Grep over Read) is the right mitigation for: even when the echo isn't reproducible in a probe, the prose eliminates the trigger surface cheaply.

## Proposed approach (option 1 + option 2; option 3 deferred)

### Option 1 — FO shared-core prose discipline (primary)

Update `skills/first-officer/references/first-officer-shared-core.md`:

- **`## Completion and Gates`** — when inspecting a stage report, feedback cycle, or cycle-N summary, use `Grep` with the section heading as anchor (e.g., `Grep ^## Stage Report`, `Grep ^### Feedback Cycle 2`) instead of full-file `Read`. A targeted Grep returns the section in bounded tokens and does not register in CC's staleness tracker based on probe-2 evidence.
- **`## Dispatch`** — when loading an entity body to compose a dispatch prompt, prefer `Grep` for the specific sections needed (problem statement, acceptance criteria, stage report). Full `Read` only when the entity body is small (< 5 KB) or every section is needed.
- **`## Probe and Ideation Discipline`** (already created by #157) — add a bullet: "avoid the Read + `status --set` pattern on an entity ≥ 10 KB. Grep the sections you need, or use the `status --set` stdout diff for frontmatter confirmation, instead of re-Reading the file after a `--set` mutation."

Also update `skills/first-officer/references/claude-first-officer-runtime.md` (not the codex one) with a pointer to the shared-core guidance, scoped as a Claude-runtime-specific behavior.

### Option 2 — `status --set` stdout emits a frontmatter diff

Current stdout prints only `field: new_value` per updated field. Extend to emit a structured before/after for every touched field, so the FO has the precise mutation in bash output without re-Reading:

```
status: ideation -> done
completed:  -> 2026-04-15T21:02:17Z
```

Shape rationale: one-line-per-field `old -> new`, arrow-separated, with an empty string rendered as blank. Preserves existing callers that grep the stdout for `field:` (new shape starts with `field: old -> new` which still matches `^status:` etc.), but callers that pattern-match the full line must be audited. The implementation lives in `skills/commission/bin/status`'s `--set` branch (around lines 1267–1281) and is ~20 lines of Python.

### Option 3 — Sidecar frontmatter file (DEFERRED per captain)

Split `{slug}.md` into `{slug}.meta.yaml` + `{slug}.md`. Bigger architectural shift (touches every commissioned workflow, every `status --set` call site, every FO prose reference to entity structure). **Deferred** — not in this task's scope. Revisit only if options 1+2 prove insufficient or if another task needs a cross-sync / shared-metadata layer.

## Scope — Claude-runtime primary, Codex verification light

The staleness-echo mechanism described in #96 is a Claude Code harness behavior. Codex's FO runtime accesses files via shell commands (`cat`, `sed`, `grep`) through `exec`, not through a tracked Read tool with a staleness-diff injector. The prose in `codex-first-officer-runtime.md` contains no analogous mechanism (searched for "stale|echo|Read" — only `send_input` echo references, unrelated to file-tracking).

**Decision:** Ship the option-1 prose in `first-officer-shared-core.md` + Claude-runtime adapter only. Do NOT add a Codex-runtime-specific bullet. Implementation stage MUST run one light Codex probe (contrived Read-equivalent via `cat`, then `bash` mutation, in a `codex exec` session) to confirm no echo mechanism exists. If the probe finds an equivalent surface, fold it into scope with a runtime-agnostic rule; otherwise keep Claude-only.

## Sequencing constraint

#157's implementation branch (`spacedock-ensign/claude-team-respect-stage-model`) has already added the `## Probe and Ideation Discipline` section and a probe-discipline bullet to `first-officer-shared-core.md`. #159's prose touches the same file (same section + `## Dispatch` + `## Completion and Gates`). When #159 reaches implementation stage, the implementation worktree MUST branch off the #157 branch (not `main`) to avoid merge conflicts. If #157 has merged to `main` before #159 implementation starts, branch off `main` normally.

## Acceptance criteria

### AC-1 (empirical: Grep does not trigger the echo on a project-tree file ≥ 20 KB) — BLOCKING

A probe run creates a project-tree markdown fixture ≥ 20 KB, uses `Grep` to extract a section, mutates the file via Bash (`echo >>`), then issues a follow-up tool call. The subsequent turn's system-reminder must not contain a full-file echo of the fixture. Evidence: the probe transcript (captured as `## Probe evidence` below for ideation; re-run during implementation validation). Verifier: manual inspection of the implementation-stage cycle-1 transcript.

**Status for this ideation:** DONE — see `## Probe evidence` section 2 below.

### AC-2 (prose: `first-officer-shared-core.md` prefers Grep over Read for section extraction) — BLOCKING

Static test: `grep -E "prefer.*Grep|section.*anchor.*Grep" skills/first-officer/references/first-officer-shared-core.md` returns at least one match in `## Completion and Gates` or `## Dispatch` or `## Probe and Ideation Discipline`. Verifier: a shell-based test added to `skills/first-officer/tests/` (or similar) that greps the shared-core file for the specific phrases. Budget: trivial.

### AC-3 (`status --set` stdout emits frontmatter diff) — BLOCKING

Unit test: invoke `status --set <slug> status=done` on a fixture entity with prior `status: ideation`. Assert stdout contains `status: ideation -> done` (or the chosen arrow form). Extend to cover: clearing a field (`worktree=`) emits `worktree: <old> -> `; adding a field not previously in frontmatter emits `archived:  -> <timestamp>`; bare timestamp fields (`completed`) auto-fill and render as `completed:  -> <ISO>`. Verifier: pytest-style tests in `skills/commission/tests/test_status_set.py`. Budget: modest, ~40 LOC test + ~20 LOC implementation.

### AC-4 (Codex runtime verification) — BLOCKING (small)

Implementation-stage probe: one `codex exec` session runs a contrived equivalent of Read-then-Bash-mutate on a project-tree file, captures the transcript, and checks for any full-file echo or equivalent staleness-reminder. Verifier: transcript snippet committed to the implementation PR description or a `.probe-evidence/` file. If the probe finds no echo, record "Codex probe negative, Claude-runtime-only prose is sufficient." If it finds an echo, escalate back to ideation to rescope. Budget: one Codex session, ~5 minutes.

### AC-5 (in-session token-delta evidence) — OPT-IN, NON-BLOCKING

Per captain: optional. If a long-running FO workflow session is available during or after implementation, compare cache-write-tokens-per-FO-turn before vs. after the prose + stdout-diff changes land. This is confirmation, not a gate. Verifier: debrief entry citing the token delta, or a skip-rationale if no comparable session is available.

## Test plan

| Test | Type | Cost | Notes |
|---|---|---|---|
| AC-1 Grep-vs-Read probe | live observational | 1 session turn | Fragile across harness versions; capture transcript snippet. |
| AC-2 shared-core prose grep | static / shell | trivial | Part of the FO test suite or a one-off CI check. |
| AC-3 `status --set` diff stdout | unit | ~40 LOC | Python unit test on the `--set` branch; runs on every CI. |
| AC-4 Codex probe | live observational | ~5 min Codex session | One-off during implementation; evidence goes in PR. |
| AC-5 token-delta | live session comparison | opportunistic | Debrief-level; non-blocking. |

**No parametrized live-test matrix across runtimes is needed** unless AC-4 finds a Codex echo. Budget total: small. The heaviest cost is the one-off Codex probe in implementation.

## Scope boundary

This task ships:

- ~5–10 lines of prose in `skills/first-officer/references/first-officer-shared-core.md` (edits to `## Completion and Gates`, `## Dispatch`, `## Probe and Ideation Discipline`).
- ~2 lines in `skills/first-officer/references/claude-first-officer-runtime.md` pointing to the shared-core rule.
- ~20 lines of Python in `skills/commission/bin/status` (the `--set` stdout diff emission).
- ~40 LOC of new tests (`test_status_set.py` diff-emission cases, optional shell test for prose).

If AC-1 or AC-4 finds the working assumption wrong (Grep DOES trigger the echo, or Codex HAS an equivalent mechanism), rescope ideation rather than expand implementation silently.

## Probe evidence

Recorded during this ideation session on 2026-04-15. Fixtures created under `/Users/clkao/git/spacedock/.worktrees/probe-96/` (gitignored ephemeral area).

### Probe 1 — Grep + Bash mutation (AC-1 supporting evidence)

- Fixture: `grep-fixture.md`, 23,019 bytes, 3 sections × 50 lines each with section-heading anchors.
- Sequence: `Grep ^## Section` → `Bash echo "## Section Zeta ..." >> grep-fixture.md && wc -l` → follow-up `Bash ls -la`.
- Result: Grep returned the 5 section-heading lines. The Bash-mutation turn and the follow-up `ls` turn produced system-reminders containing ONLY the standard "task tools haven't been used" nudge — no full-file echo, no diff, no reference to `grep-fixture.md`.
- Interpretation: `Grep` did not register the file in CC's staleness tracker. Evidence supports the AC-1 hypothesis that Grep is a safe substitute for Read when the FO only needs a bounded section.

### Probe 2 — Full-file Read + `status --set` + follow-up Bash (echo-reproduction attempt)

- Fixture: `.worktrees/probe-96/workflow/probe-entity.md`, 23,002 bytes, with frontmatter (`status: ideation`) and a minimal companion `README.md` declaring ideation + done stages so `status --set` accepts it.
- Sequence: full `Read` of `probe-entity.md` → `Bash python3 skills/commission/bin/status --workflow-dir .../workflow --set probe-entity status=done` → follow-up `Bash ls -la`.
- Result: `status --set` wrote the mutation and printed `status: done` on stdout. The follow-up `ls` turn produced no full-file echo — only the same task-tools nudge.
- Interpretation: this in-session run did **not** reproduce the #96 echo. The echo appears session/harness-sensitive. This does not invalidate #96 (the captain observed it in a real FO session); it does mean the mitigation's value is primarily **preventive**: make the echo impossible to trigger via prose discipline, even when the probe cannot reliably force it.

### Probe 3 — Read tool token cap (incidental finding)

- Attempting `Read` on a 92 KB fixture (no offset/limit) failed with "File content (25484 tokens) exceeds maximum allowed tokens (25000)."
- Interpretation: the CC `Read` tool caps at ~25k tokens. The #96 scenario concerns medium entity bodies (roughly 10 KB–60 KB); truly huge entities already force the FO to use offset/limit Reads. This narrows AC-1's realistic fixture band.

### Codex probe deferred to implementation

Per captain directive on scope, the Codex probe is a light verification step during implementation (AC-4), not a blocking ideation prerequisite. The Codex runtime adapter contains no file-staleness mechanism today (grep for `stale|echo|Read|full.*file` in `codex-first-officer-runtime.md` returns only unrelated `send_input` references). Default assumption: Codex has no equivalent surface; verify cheaply in implementation.

## Stage Report — Ideation

**Summary:** Ideation complete. Problem scope narrowed per in-session probe evidence to the Read + `status --set` pattern on medium entities, with Grep-vs-Read as the primary mitigation lever. Option 3 (sidecar frontmatter) dropped per captain. Codex scope defaulted to Claude-only with a cheap verification AC during implementation. Acceptance criteria and test plan sized to match: small prose change + small `status --set` stdout enhancement + one Codex probe.

Checklist coverage:

1. **Read task body via Grep on section headings** — DONE. Grepped `## Why it fires`, `## Mitigation options`, `## Scope note`, `## Acceptance criteria` on the original draft. Three mitigation options and four draft ACs identified.
2. **Read upstream GitHub issue #96 body** — DONE. Fetched via `gh api repos/clkao/spacedock/issues/96 --jq .body`. The spec matches what `docs/plans/status-set-staleness-echo-mitigation.md` had quoted; no surprises.
3. **Codex scope probe / decision** — DONE (decision; live probe deferred to implementation per pragmatic rationale). Claude-runtime-only prose by default. Codex runtime adapter has no equivalent mechanism today; implementation runs one `codex exec` verification (AC-4). If positive, rescope.
4. **Grep-vs-Read empirical verification on project-tree files** — DONE. See `## Probe evidence` section 1: Grep + Bash-mutation + follow-up Bash produced no full-file echo on a 23 KB project-tree fixture. Evidence supports option-1 prose.
5. **Diff-style reminder observation baked into problem statement** — DONE. See `## In-session observations` points 1 and 3. The full-file echo is not universal; `status --set` on a not-previously-Read entity already emits only the modified region. The mitigation targets the specific Read-then-mutation pattern.
6. **Sidecar frontmatter deferred** — DONE. Option 3 dropped from scope with a brief rationale. Noted as future architectural follow-up, not this task.
7. **Merge sequencing noted** — DONE. See `## Sequencing constraint`: implementation branches off `spacedock-ensign/claude-team-respect-stage-model` (the #157 branch) unless that branch has merged to `main` first.
8. **Fleshed-out ideation content** — DONE. Problem statement, proposed approach, ACs with verifiers, test plan, scope boundary, and probe evidence all present. Body ~140 lines, within the target.
9. **Acceptance criteria shape** — DONE. AC-1 (empirical Grep-echo), AC-2 (shared-core prose), AC-3 (`status --set` diff stdout), AC-4 (Codex verification, cheap), AC-5 (token-delta opt-in). AC-1 and AC-2 map directly to captain guidance; AC-3 chooses the `old -> new` shape; AC-4 is the Codex probe held at implementation; AC-5 is non-blocking per captain.
10. **Test plan shape** — DONE. Static grep on prose, unit tests on `status --set` stdout, one live Grep-echo probe, one Codex probe, optional token-delta evidence. Budget: small.
11. **Scope boundary** — DONE. ~5–10 lines shared-core prose, ~2 lines Claude-runtime pointer, ~20 lines `status --set` Python, ~40 LOC tests. Rescope clause explicit.
12. **Commit the revised ideation content** — DONE. Committed as `ideation: #159 ...`.
13. **Write Stage Report — Ideation** — DONE (this section). Committed as `report: #159 ideation stage report`.
14. **SendMessage team-lead completion signal** — pending at end of turn.
