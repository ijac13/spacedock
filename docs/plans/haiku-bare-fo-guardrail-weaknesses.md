---
id: 200
title: "Haiku-bare FO behavioral weaknesses on guardrail suite (test_gate_guardrail + test_feedback_keepalive)"
status: backlog
source: "session 2026-04-18 investigation of PR #132 (#190) bare-mode CI failures — two distinct haiku-bare-FO weakness patterns surfaced after #186 cycle-6 fixed test_gate_guardrail's model-fixture plumbing and #190's two-path observer sharpened test_feedback_keepalive's diagnostic. Neither failure is a regression from #186 or #190; both are pre-existing haiku-bare-FO weaknesses newly made visible by better fixtures."
started:
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

## Why this matters

PR #132 (#190) CI exposed two distinct haiku-bare-FO behavioral failures on tests the `--effort low` + claude-haiku-4-5 + bare mode combination cannot currently reach the protocol-adherence bar the tests validate. Pre-session these failures were masked — test_gate_guardrail was vacuously passing (fixture ignored `--model`); test_feedback_keepalive was carrying a narrow `xfail(team_mode=="bare" AND model=="claude-haiku-4-5")` which #190 removed in favor of a diagnostic that would catch ALL failure modes. After #186 cycle-6 + #190 landed, the bare-mode failures are honest signal the test suite is designed to surface.

The two patterns are independent in their shape:

**Pattern A — `test_gate_guardrail` bootstrap failure.** The haiku-bare FO never reaches the workflow. Evidence (from `fo-log.jsonl` in the CI artifact `spacedock-test-2izdmkjp`):
- Early `Bash` tool_use with literal `{PWD}` brace-bug in the shell command (haiku failed to interpolate the variable, emitted it as a literal).
- `cd /home/runner/work/spacedock/spacedock && ... status --discover` — FO cd'd to the repo root, not the test-project cwd. `status --discover` found no workflows there.
- Final assistant text: "To proceed, I need one of the following: ... What workflow would you like me to process?" — FO gives up asking for clarification.
- Resulting test verdict: `FAIL: first officer presented gate review` (regex `gate review|recommend approve|recommend reject` never matches because FO never reached the gate). 6/7 other checks trivially pass (negative assertions: "did NOT advance", "did NOT self-approve").

**Pattern B — `test_feedback_keepalive` tool-shape discipline failure.** The haiku-bare FO completes the workflow end-to-end but with wrong tool shapes. Evidence (from `spacedock-test-h42ehkks` CI artifact):
- Impl dispatch at line 54 correctly uses `subagent_type="spacedock:ensign"`.
- Validation dispatch at line 98 uses `subagent_type=None` (generic Agent, not spacedock:ensign). Path-A predicate requires `spacedock:ensign`; doesn't match.
- Line 151 attempts a `spacedock:ensign` dispatch but the prompt body is literally `SendMessage(to="afc4...", message="...")` — haiku confused Agent() with SendMessage(), nesting the SendMessage call string inside an Agent prompt.
- Entity archive has `## Stage Report` headers but not the literal `### Feedback Cycles` header Path-B requires (`_inline_process_complete` reads for exactly that anchor).
- `greeting.txt` was written in the worktree but never merged back to the test-project root. Path-B's filesystem check reads the test-project root, misses it.
- FO exits code=0 after archiving (cleanly) → new assertion fires: "FO subprocess exited (code=0) before either Path-A or Path-B signal was observed."

## Proposed approach

**Near-term (ship in #190's PR before #132 merges):** permanent `@pytest.mark.xfail(strict=False)` guarding `team_mode == "bare" and model == "claude-haiku-4-5"` on BOTH test_gate_guardrail and test_feedback_keepalive, with reason strings citing this task (#200). This silences the currently-visible failures without weakening the test assertions themselves — stronger models (haiku-teams, opus-*) still exercise the full protocol.

**Medium-term (this task's scope):** investigate whether FO prose changes (shared-core dispatch contract, runtime adapter, skill prompt) could improve haiku-bare reliability on these two shapes. Concrete candidates:
- For Pattern A: sharpen startup-procedure prose so haiku less readily cd's away from the test project; reinforce that `status --discover` must run in the test-project cwd. Possibly add a `startup-sanity-check` helper that fails loudly if the cwd doesn't contain the workflow dir.
- For Pattern B: add explicit prose "use `subagent_type=spacedock:ensign` when dispatching stage workers"; warn against nesting `SendMessage` calls inside `Agent` prompts; and reinforce the `### Feedback Cycles` heading as the load-bearing audit anchor (not `## Stage Report`).

**Long-term (out of scope for this task):** if FO prose changes don't close the gap, the pragmatic answer is "haiku-bare is not a supported combination for these tests" — retire the bare-haiku variants and let other combos (bare-opus, teams-haiku, teams-opus) carry the coverage.

## Acceptance criteria

**AC-1 — Near-term xfail lands with #190 PR (#132).**
Verified by: `grep -n 'pending #200\|#200 — bare-haiku' tests/test_gate_guardrail.py tests/test_feedback_keepalive.py` returns one match per test. `make test-live-claude-bare` with `--model claude-haiku-4-5 --effort low` reports both tests as XFAIL (not FAILED). PR #132 CI goes green on claude-live-bare.

**AC-2 — Pattern A root cause documented with reproducible evidence.**
Verified by: the entity body's Pattern A section cites specific fo-log line numbers from a named artifact + reproduces the `{PWD}` brace-bug under a minimal haiku-bare invocation.

**AC-3 — Pattern B root cause documented with reproducible evidence.**
Verified by: the entity body's Pattern B section cites specific fo-log lines showing (a) `subagent_type=None` validation dispatch, (b) `SendMessage` string nested inside `Agent` prompt, (c) missing `### Feedback Cycles` header in archived entity, (d) `greeting.txt` in worktree but not in test-project root.

**AC-4 — Medium-term FO prose proposal or explicit defer.**
Verified by: either a concrete before/after diff proposed for `skills/first-officer/SKILL.md` or `references/claude-first-officer-runtime.md` addressing Pattern A + Pattern B, OR a documented decision to defer (e.g., "haiku-bare weaknesses not worth FO prose surgery; retire bare-haiku coverage instead — filed as follow-up").

**AC-5 — Static suite green post-merge.**
Verified by: `make test-static` passes on main after implementation.

## Test plan

- **Static, primary:** AC-1 is static grep + test-marker inspection. AC-5 is `make test-static`.
- **Behavioral, optional:** one haiku-bare run each of test_gate_guardrail + test_feedback_keepalive to confirm XFAIL disposition (not FAILED) after the marker lands. ~$0.50 total, deferrable.
- **Medium-term ACs (AC-4):** no live runs required for the proposal; the decision or draft lives in prose.

## Out of scope

- Fixing haiku-bare FO reliability on other tests. This task scope is strictly test_gate_guardrail + test_feedback_keepalive.
- Retiring bare-haiku coverage across the test suite (long-term option; separate task if the medium-term approach fails).
- FO prose changes that affect runtime behavior across ALL models — this task's prose changes (if any) must target haiku-bare without regressing opus/haiku-teams.

## Cross-references

- **#185** — cycle 3 added the original narrow bare+haiku xfail on test_feedback_keepalive that #190 removed. This task effectively restores it (but framed differently).
- **#186** — fixed test_gate_guardrail model-fixture plumbing, making #200's Pattern A visible.
- **#190** — sharpened test_feedback_keepalive diagnostic, making #200's Pattern B visible.
- **#194** — multi-model FO-side standing-teammate-spawn flake. Adjacent but distinct; do NOT absorb.
- **#160** — haiku FO multi-stage dispatch compression. Related FO-tool-shape weakness on haiku; may share root cause with Pattern B.
- Artifacts: CI run `24610475442`, job `71963876313` (claude-live-bare). Test dirs `spacedock-test-2izdmkjp` (gate_guardrail) + `spacedock-test-h42ehkks` (keepalive).
