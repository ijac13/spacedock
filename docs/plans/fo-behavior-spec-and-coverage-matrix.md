---
id: 202
title: "FO behavior spec + coverage matrix as source of truth"
status: ideation
source: "session 2026-04-18 — reflecting on the flake-task backlog (13 open tasks, mostly class-A/B LLM-output-brittleness). Captain observation: without a structured inventory of desired FO behaviors mapped to tests and model coverage, every flake triage is ad-hoc and every fix risks deflecting ambient flakes to new tasks without addressing the root class. Spec-as-source-of-truth: prose (FO SKILL + runtime adapters) and code (tests) should conform to the spec, not vice versa."
started: 2026-04-19T16:58:51Z
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Why this matters

The flake-tracking backlog grew to 13 tasks this session, most in class A (haiku protocol adherence), class B (FO bootstrap discipline), and class C (LLM-output brittleness in behavioral tests). Workers repeatedly deflected adjacent flakes into new tasks rather than addressing root causes. The FO (me) approved each deflection because I had no way to evaluate "is this flake in a critical behavior or a redundant assertion?"

The root gap: **we have no structured inventory of desired FO behaviors.** FO contract prose is scattered across `SKILL.md`, `shared-core.md`, `claude-first-officer-runtime.md`, `codex-first-officer-runtime.md`. Tests are scattered across `tests/test_*.py`. Nothing ties them together. Every flake question begins with "go grep the prose."

**Without an inventory we can't answer:**

- Which desired FO behaviors have zero test coverage?
- Which behaviors are tested redundantly (and therefore safe to xfail in one place)?
- What is the flake rate of behavior X on model Y, mode Z?
- Which prose imperatives are load-bearing vs decorative?
- When we add a behavior to prose, does an assertion exist for it?

The captain's framing: **the spec is the source of truth. Prose and code are derivatives that must conform.** If prose drifts from the spec, the spec wins (or the spec is updated with a documented change). If code drifts, same. This inverts the current situation where prose+code drift independently and we debug by grep.

## Proposed approach

Adopt **RFC 2119 (MUST/SHOULD/MAY) requirements + requirements traceability matrix (RTM)** as the format. Each requirement gets:

- A stable ID (`FO-R-NNN`)
- Level (MUST / SHOULD / MAY / MUST NOT)
- Area tag (bootstrap, dispatch, gate-review, merge, team-mgmt, standing-teammate, error-recovery, …)
- Prose anchor (file:line range of the current contract prose)
- Test coverage (list of tests + assertion kind: static / live / behavioral)
- Model×mode coverage (which CI jobs exercise this)
- Flake status per cell (green / flaky-tracked / xfailed / uncovered)
- Status (covered / partial / uncovered / deprecated)

Rendered shape: **one markdown file per requirement** with YAML frontmatter (queryable) + prose body (readable). OR one aggregate markdown with a big table + anchors. Captain to pick during ideation; both shapes have worked in other projects.

Source-of-truth semantics:

1. FO prose (`SKILL.md`, `references/*.md`) links TO the spec by requirement ID.
2. Tests have a docstring or marker naming the requirement ID they verify.
3. New behaviors are added to the spec FIRST, then prose + tests are added to conform.
4. Flake tasks are resolved by updating the spec's status (fix / retire / mark model-specific xfail) — not by filing new tasks and hoping someone notices.

## Initial deliverables

1. **Format choice.** Picking between (a) one-file-per-requirement YAML+MD, (b) single aggregate markdown, or (c) hybrid (aggregate for browsing, individual files for deep linking).
2. **Enumerate requirements from current prose.** Grep `MUST|MUST NOT|SHOULD|NEVER|always|never` across `skills/first-officer/**/*.md` and the workflow README's FO-relevant bits. Assign IDs. First pass: ~30-50 requirements likely.
3. **Map tests to requirements.** For each test in `tests/test_*.py`, identify which requirement(s) it asserts. Flag tests that verify nothing specific (surface-level smoke).
4. **Stamp current coverage + flake rates.** Per requirement × model × mode cell, stamp from recent CI (last 2 weeks would capture post-#186 unpin + all this session's PRs).
5. **Identify gaps.** Uncovered requirements (no test) + redundantly-covered requirements + load-bearing flaky requirements.
6. **Refactor prose to reference spec IDs.** `SKILL.md` and runtime adapters point at `FO-R-NNN` instead of restating; spec body carries the authoritative prose.
7. **Refactor tests to declare which requirements they assert.** Docstring convention or pytest marker (`@pytest.mark.requirement("FO-R-013")`).
8. **Queryability tooling.** Shell/Python helpers: `fo-spec list --uncovered`, `fo-spec list --flaky --model opus-4-7`, `fo-spec coverage --test test_gate_guardrail`.

## Acceptance criteria

**AC-1 — Spec format chosen and documented.**
Verified by: one top-level file (`skills/first-officer/references/fo-behavior-spec/README.md` or similar) documents the chosen format — RFC 2119 imperatives + RTM, file layout (individual vs aggregate), ID scheme, area tags, status enum.

**AC-2 — Initial spec enumerates ≥30 FO requirements.**
Verified by: the spec directory (or aggregate file) contains ≥30 entries with stable IDs, each with at minimum: level, area, prose anchor, one-line description. Count may rise through iteration; 30 is the minimum floor.

**AC-3 — Every test in `tests/test_*.py` maps to at least one requirement (or is flagged unmapped).**
Verified by: a tooling run (or static audit) produces a mapping table; flagged unmapped tests have a documented rationale or are deleted.

**AC-4 — Coverage matrix stamps flake status for every covered requirement.**
Verified by: for each covered requirement, the spec records its status on at minimum claude-live, claude-live-bare, claude-live-opus, codex-live (green / flaky-tracked / xfailed / untested). "Flaky-tracked" cells cite the tracking task ID.

**AC-5 — Uncovered requirements are explicitly listed.**
Verified by: the spec has an "uncovered requirements" view or query that returns the set of `MUST / SHOULD` imperatives without test coverage.

**AC-6 — FO prose (SKILL.md + runtime adapters) references spec IDs.**
Verified by: `grep -c 'FO-R-' skills/first-officer/references/*.md skills/first-officer/SKILL.md` returns a substantial count (≥10 references as a floor for "the conforming refactor started").

**AC-7 — At least one tooling helper lands.**
Verified by: `fo-spec list --uncovered` or equivalent shell/Python invocation returns a parseable list. Single helper is sufficient for MVP; more can follow.

**AC-8 — Static suite green post-merge.**
Verified by: `make test-static` passes on main.

## Test plan

- **Static, primary:** grep-style verifications of AC-1 through AC-7. Each assertion is O(cheap) — file existence, frontmatter parsing, cross-reference count.
- **No live tests required.** The inventory is a structural artifact, not runtime behavior.
- **Cost:** low (~$3-5 for ideation; ~$10-15 for implementation depending on how much prose refactoring AC-6 entails).

## Out of scope

- **Fixing the open flake tasks.** The inventory INFORMS how to fix them; it does not itself fix them. After #202 lands, subsequent tasks (including potentially a consolidated "FO haiku protocol hardening program") pick from the coverage matrix.
- **Formal specification languages** (TLA+, Alloy, Z). Overkill for prose-driven FO; mentioned in format alternatives and rejected.
- **Gherkin / BDD harness.** Partial fit; may be adopted later for specific scenario-heavy areas but not required for v1 spec.
- **Cross-workflow spec generalization.** #202 scope is the Spacedock FO contract only. If the spec format proves useful, other workflows may adopt it separately.

## Cross-references

- **All open flake tasks** (#141, #155, #160, #161, #171, #194, #195, #196, #197, #198, #200, plus pending test_merge_hook_guardrail filing): these should be re-evaluated against the coverage matrix once #202 lands. Some may consolidate into a single root-cause task; some may be recategorized as uncovered-requirements; some may close as redundant.
- **#199** — FO agent-shutdown discipline + team-health command. Adjacent: both #199 and #202 are about making the FO's operational state observable and structured. #199 covers the runtime (team members vs entity state); #202 covers the behavioral contract (requirements vs tests vs coverage). Compatible; different layers.
- **#112** — multi-player claim semantics. Also adjacent via the agent-stamp concept. Not a dependency.

---

# Ideation revision — disentangled spec (captain-directed)

> The sections above are the v0 seed. Captain critique: v0 bundles four layers into one artifact (stable requirements + test map + prose map + per-run flake status), producing an artifact that is perpetually one commit stale on every axis. This revision replaces the **Proposed approach**, **Initial deliverables**, and **Acceptance criteria** sections above with a star-schema design. The rest of the seed body (Why this matters, Out of scope, Cross-references) stands.

## Layering (star schema)

Four layers, each owned by exactly one source. The spec owns L1 only.

| Layer | Content | Source of truth | Update cadence |
|---|---|---|---|
| **L1** | Stable requirements: ID, level (RFC 2119), area tag, one-line description, rationale | `skills/first-officer/references/fo-behavior-spec/requirements.md` | Slow — changes when a behavior is added / deprecated / re-leveled |
| **L2** | Test→requirement mapping | Declared **in test files** via `@pytest.mark.requirement("FO-R-NNN")` | Changes with tests; discovered by tooling, never stamped |
| **L3** | Prose→requirement mapping | Declared **in prose files** via `<!-- FO-R-NNN -->` HTML-comment anchors | Changes with prose; discovered by tooling, never stamped |
| **L4** | Per-run coverage + flake rate | Derived at query time from (a) current test source, (b) `gh run list` + `gh run view` CI history | Volatile; never committed |

L1 is the dimension table. L2/L3/L4 are fact sources; views join them.

### The one coupling retained: `known_flaky` on L1

Some behaviors are inherently flaky on a specific model family (e.g. Haiku's tendency to drop formatting imperatives). That is a **slow-changing semantic fact about the requirement**, not a per-run rate. Keeping it in L1 as an optional list of `{model, mode, reason, tracking_task}` means the spec can answer "should I expect FO-R-013 to be reliable on Haiku today" without going to CI history. It is distinct from L4's per-run rate: L4 says "last 50 runs had 3% failure on opus-4-7"; `known_flaky` says "Haiku is expected to trip this; tracked in #197". This field updates only when the *situation* changes, not every CI run.

All other v0 couplings (prose anchors as file:line ranges in the spec, per-cell flake stamps, explicit uncovered-requirements list) are removed.

## Format decision

### L1: hybrid aggregate + queryable frontmatter

`skills/first-officer/references/fo-behavior-spec/requirements.md` — single aggregate markdown file. Each requirement is a second-level section (`## FO-R-NNN`) with a fenced `requirement` YAML block containing structured fields, followed by a markdown prose body for rationale.

Rejected alternatives:
- **One file per requirement.** Strong for deep-linking but imposes high directory churn on a repo this size (~30-50 files landing in one PR, future churn on every re-level). Review cost compounds.
- **Pure aggregate table.** Simple but loses rationale; frontmatter-queryability requires a per-row YAML island anyway.

### L2: pytest marker only

`@pytest.mark.requirement("FO-R-013")` — the decorator is structured (toolable via `pytest --collect-only -q --strict-markers`), grep-able (`rg 'requirement\\("FO-R-'`), survives test renames, and stacks cleanly when one test covers multiple requirements. Docstring headers are rejected: parsing is fragile and they don't survive refactor tools.

Register the marker in `pyproject.toml` / `pytest.ini` with `--strict-markers` so typos fail loudly at collection.

### L3: HTML-comment anchors

`<!-- FO-R-013 -->` immediately above the governing prose block. Invisible in rendered markdown, grep-able, stable under prose edits, composable (multiple anchors can precede a block that asserts several requirements). Inline `[FO-R-013]` citations are rejected because they leak into reader-facing text. A separate xref file is rejected because it creates a third source of truth to keep synchronized.

### L4: tooling-only, never committed

A `fo-spec` helper (single script, `skills/first-officer/tools/fo_spec.py` or similar) implements query subcommands. Output is structured (JSON with human-table renderer); no derived state is written back into the repo.

## Blast radius for an ID rename

If `FO-R-013` is renamed to `FO-R-014`:
- L1: one edit in `requirements.md`
- L2: `rg -l 'FO-R-013' tests/` then sed across matches
- L3: `rg -l 'FO-R-013' skills/` then sed across matches
- L4: re-runs free

The tooling SHOULD ship a `fo-spec rename FO-R-013 FO-R-014` subcommand to automate all three edits atomically. Treat ID renames as the hardest maintenance operation; the tooling earning its keep depends on handling this well.

## Requirement record schema (L1)

```yaml
# inside a fenced ```requirement block under `## FO-R-NNN`
id: FO-R-013
level: MUST  # MUST | MUST_NOT | SHOULD | SHOULD_NOT | MAY
area: dispatch  # bootstrap | dispatch | gate-review | merge | team-mgmt | standing-teammate | error-recovery | ...
summary: "FO emits completion-signal literal when forwarding a dispatch prompt."
known_flaky:  # optional; omit entirely when empty
  - model: haiku-4-5
    mode: claude-live
    reason: "Haiku paraphrases parenthesis-equals syntax to English."
    tracking_task: 197
```

The prose body under the YAML block carries rationale, references to prior incidents, and any reader-facing explanation. No file:line prose anchors — tooling discovers those from L3.

Deliberately absent from L1: test list, prose-location list, coverage cells, flake rates. All derived.

## Tooling (L4 queries) — load-bearing

Now that coverage is never stamped, **the tooling is the only way to see it**. AC-7's "at least one tooling helper" is elevated from MVP nice-to-have to load-bearing.

Minimum viable subcommands for this task to count as done:

- `fo-spec list` — print all requirements with level/area/summary.
- `fo-spec list --uncovered` — requirements with zero pytest markers referencing them.
- `fo-spec list --unanchored` — requirements with zero prose anchors referencing them.
- `fo-spec tests FO-R-013` — tests that mark this requirement.
- `fo-spec prose FO-R-013` — prose locations that anchor this requirement.
- `fo-spec orphans` — pytest markers and prose anchors whose IDs are not in `requirements.md`.
- `fo-spec validate` — static check: every ID in tests/prose exists in spec; every spec ID is well-formed. Exits non-zero on drift. Wired into `make test-static`.

Out of scope for v1, left for a follow-up:
- `fo-spec coverage --model opus-4-7` (requires `gh` API calls; punt to a separate task to keep v1 offline-only).
- Flake-rate queries over CI history.

Rationale for offline-only v1: the `gh` API layer adds auth, rate-limit, and network-flake surface that would swamp the structural work. Ship L1/L2/L3 plumbing first; CI-history views layer on cleanly once the schema is stable.

## Revised acceptance criteria

AC-1 through AC-8 below supersede the v0 set. AC-4 (per-cell flake stamps) is removed. AC-5 (uncovered list) becomes a tooling query. AC-7 (tooling) is load-bearing.

**AC-1 — Spec layout and schema documented.**
`skills/first-officer/references/fo-behavior-spec/README.md` documents: the four-layer model, L1 file location, requirement record schema, L2 marker convention, L3 anchor convention, and `fo-spec` subcommand list.
*Test:* static — file exists, contains sections named `Layering`, `Requirement schema`, `Marker convention`, `Anchor convention`, `Tooling`.

**AC-2 — `requirements.md` enumerates ≥30 FO requirements.**
Each entry has an `## FO-R-NNN` heading, a fenced `requirement` YAML block with `id`, `level`, `area`, `summary`, and a prose body.
*Test:* static — `fo-spec validate` parses the file cleanly; count of `## FO-R-` headings ≥30; every YAML block is valid and its `id` matches the heading.

**AC-3 — `fo-spec` tool ships with the seven subcommands listed above.**
*Test:* unit tests (`tests/test_fo_spec.py`) — one test per subcommand, using a small fixture `requirements.md` + fixture test dir + fixture prose dir. `validate` has a positive and a negative case (drift detected → non-zero exit).

**AC-4 — Pytest marker registered and at least one real test adopts it.**
`pyproject.toml` / `pytest.ini` registers `requirement` as a known marker under `--strict-markers`. At least one existing test in `tests/test_*.py` carries `@pytest.mark.requirement("FO-R-NNN")` mapping to a real spec ID.
*Test:* static — `pytest --collect-only -q` does not warn about unknown `requirement` marker; `fo-spec tests FO-R-NNN` returns the adopted test.

**AC-5 — At least one prose anchor lands in FO references.**
At least one `<!-- FO-R-NNN -->` anchor in `skills/first-officer/**/*.md` mapping to a real spec ID.
*Test:* static — `fo-spec prose FO-R-NNN` returns the anchored location.

**AC-6 — `fo-spec validate` is wired into `make test-static`.**
Drift (unknown ID in tests or prose, malformed YAML, duplicate IDs) fails the static suite.
*Test:* integration — `make test-static` runs `fo-spec validate`; a deliberate drift in a scratch branch causes non-zero exit.

**AC-7 — `fo-spec list --uncovered` and `--unanchored` run against the real repo and produce a parseable list.**
The lists are the v1 answer to "what's the gap"; they replace the v0 static "uncovered requirements" section.
*Test:* integration — run against live repo; output parses as the documented format (JSON or table).

**AC-8 — Static suite green post-merge.**
*Test:* `make test-static` passes on main.

**Removed from v0:** AC-4 (per-cell flake stamps), AC-5 (static uncovered-requirements list), AC-6's "≥10 references floor" (replaced by AC-5's "at least one anchor" proof-of-life; large-scale prose refactor is a separate follow-up task, not an MVP gate).

## Revised test plan

- **Static verification of spec format:** `fo-spec validate` parsing the committed `requirements.md`.
- **Tooling unit tests (`tests/test_fo_spec.py`):** fixture-based per-subcommand coverage; parse a known-good and known-bad fixture tree.
- **One integration test:** `fo-spec validate` exits non-zero on drift (add a bogus `FO-R-999` marker in a temp test file, confirm validate fails).
- **Wire-in check:** `make test-static` invokes `fo-spec validate` and fails the suite on drift.
- **No live LLM tests.** The spec and tooling are structural.

Estimated cost: low. Implementation stage ~$10-20 including the 30+ requirement enumeration, tooling, marker adoption on one test, and anchor adoption on one prose location. Large-scale prose/test refactor is explicitly deferred.

## What's deferred to follow-up tasks

- Marking every existing test with its requirement ID (bulk L2 adoption).
- Anchoring every load-bearing prose block (bulk L3 adoption).
- CI-history coverage views (`fo-spec coverage --model X`).
- Flake-rate queries over `gh run` history.
- Re-evaluating the 13 open flake tasks against the coverage matrix.

These are all unblocked by #202 shipping but are not part of its acceptance. Filing them as separate tasks keeps #202's blast radius contained.

## Stage Report: ideation

- DONE: Disentangled spec design.
  Four-layer star schema: L1 spec (stable reqs only), L2 pytest markers in tests, L3 HTML anchors in prose, L4 tooling-derived coverage. Coupling retained and justified: `known_flaky` on L1 as a slow-changing semantic fact distinct from L4 per-run rates.
- DONE: Format decision with tradeoffs.
  L1 = hybrid aggregate markdown with per-requirement YAML block (rejected per-file for directory churn, pure table for loss of rationale). L2 = `@pytest.mark.requirement("FO-R-NNN")` with `--strict-markers` (rejected docstring headers for refactor fragility). L3 = `<!-- FO-R-NNN -->` HTML comments (rejected inline citations for reader-facing leakage, separate xref file for third-source-of-truth drift). Blast radius on rename analyzed; `fo-spec rename` subcommand flagged as tooling requirement.
- DONE: Acceptance criteria + test plan under disentangled design.
  AC-1 through AC-8 rewritten; v0 AC-4 (per-cell flake stamps) removed; v0 AC-5 (static uncovered list) converted to tooling query; AC-7 (tooling) elevated to load-bearing. Test plan: static format check, unit tests per subcommand, one integration drift test, `make test-static` wire-in. No live LLM tests. Bulk prose/test refactor explicitly deferred to follow-ups to contain #202 blast radius.

### Summary

Redesigned #202 per captain critique: separated stable requirements (L1, owned by spec) from test mapping (L2, owned by test files via pytest markers), prose mapping (L3, owned by prose via HTML comments), and coverage/flake status (L4, tooling-derived, never committed). One coupling retained with justification: `known_flaky` as a slow-changing semantic fact on L1. Tooling is now load-bearing since coverage is no longer stamped. Acceptance criteria tightened to an MVP that ships the plumbing + one-marker/one-anchor proof-of-life; bulk adoption deferred to follow-ups. No code written this stage — design lives in entity body.
