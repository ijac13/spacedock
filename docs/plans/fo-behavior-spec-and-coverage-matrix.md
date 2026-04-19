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
