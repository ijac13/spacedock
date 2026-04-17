---
id: 182
title: "Diagnose opus-4-7 FO regression via local diff against opus-4-6 baseline"
status: implementation
source: "from #177 cluster — knowing what was factual vs inferred, run the actual diagnostic that #178 should have been preceded by: local FO=opus-4-7 vs FO=opus-4-6 diff on the standing-teammate-roundtrip test."
started: 2026-04-17T05:03:08Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-diagnose-opus-4-7-fo-regression
issue:
pr:
mod-block:
---

## Why this matters

#177's experiments went wrong because we built mitigations on top of an inferred diagnosis ("ensign hallucinates SendMessage at low/medium effort") that was actually a parent-fo-log misread. The ensign was sending the message all along; the parent fo-log structurally doesn't contain subagent-emitted SendMessages. Direct evidence: pre-#178 high-effort opus run (CI run 24539317900, headSha 1a561bfb) — entity body shows `Captured reply: ECHO: ping` + `verdict: passed`, while the parent fo-log has zero ensign-emitted SendMessage tool_use events.

What we DO know factually: opus-4-7 FO at low/medium effort fails this test in some way that opus-4-6 FO doesn't. We don't know HOW — could be budget exhaustion, autonomous-loop hang (`ScheduleWakeup` events in the artifact suggest this surface), missed teammate-message processing, or something else.

## The diagnostic

Run `tests/test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips` locally with FO=`claude-opus-4-7` + `--effort low`, capture EVERYTHING, then repeat with FO=`claude-opus-4-6` + `--effort low`, then DIFF the two preserved test directories. The diff reveals what opus-4-7 FO does that opus-4-6 FO doesn't.

This bypasses CI artifact filtering — local runs have direct filesystem access to everything Claude Code writes.

## Acceptance criteria

**AC-1 — Two clean local runs captured.**

- Run A: FO=`claude-opus-4-7` + `--effort low` (expected to FAIL per the regression we're investigating)
- Run B: FO=`claude-opus-4-6` + `--effort low` (expected to PASS — known-good baseline pre-2.1.111)
- Both with `KEEP_TEST_DIR=1` to preserve the test directory
- For each: capture `claude --version`, the full preserved test-dir tree (parent `fo-log.jsonl`, `stats-fo.txt`, test-project entity body), and any subagent session storage Claude Code writes locally (check `~/.claude/sessions/` or equivalent paths if they exist)

**AC-2 — Per-event timeline for the failing run.**

When does each parent tool_use happen? When does the streaming watcher's M4 fire (or fail to)? When does the FO subprocess hang/exit/exhaust budget? Build a timeline with timestamps. Identify the exact event where opus-4-7 diverges from opus-4-6 baseline.

**AC-3 — Structured diff between the two test dirs.**

Compare the two preserved test directories: parent fo-log content, tool_use inventories (which tools called, in what order, with what inputs), timing per phase, budget consumption. Pinpoint the structural divergence. Produce a side-by-side or sequential narrative of where the runs differ.

**AC-4 — Specific failure-mode attribution.**

Name what opus-4-7 FO does at the moment the test diverges from the opus-4-6 baseline. Examples (illustrative, not prescriptive):
- "FO opus-4-7 enters a `ScheduleWakeup` loop after the ensign Agent() dispatch and never processes the teammate-routing event for echo-agent's reply"
- "FO opus-4-7 burns through $1.50 on system-prompt processing before reaching the SendMessage step, leaving insufficient budget for the wait-for-reply step"
- "FO opus-4-7 emits a malformed teammate-message acknowledgment that Claude Code rejects, causing the reply event to never land in the parent stream"

The attribution must be specific enough to inform a targeted fix.

**AC-5 — Recommendation.**

Based on AC-4's attribution, propose ONE of:
- A targeted local fix (e.g., raise budget, modify FO prompt, change orchestration loop) that the implementer can validate by re-running AC-1's failing run and seeing it pass
- An upstream escalation with a minimal repro (e.g., file an Anthropic issue with the exact stream artifact + reproduction steps) if the failure is in Claude Code itself

## Investigation discipline

**Apply `superpowers:systematic-debugging` skill.** This is a debugging task; the skill is designed for exactly this. Specifically:

- **Phase 1 (Root Cause Investigation):** reproduce both runs, capture all artifacts, identify the exact event where opus-4-7 diverges from opus-4-6. Read error messages carefully; reproduce consistently before investigating.
- **Phase 2 (Pattern Analysis):** compare opus-4-7 vs opus-4-6 stream contents — what's structurally different? Is it specific tool calls, ordering, timing, content? Find the working example (opus-4-6) and the broken example (opus-4-7), identify differences.
- **Phase 3 (Hypothesis and Testing):** form ONE hypothesis at a time, test minimally, verify. If hypothesis fails, form new one — do not stack fixes. State each hypothesis explicitly before testing.
- **Phase 4 (Implementation Rules):** minimum viable repro test case; no multiple fixes at once; verify after each change.

**Do NOT:**
- Propose prose mitigations (that's what #178 was; falsified).
- Try multiple hypotheses at once.
- Skip the comparison run (opus-4-6 baseline is essential for the diff).
- Inflate scope to broader "FO architecture" investigation.

## Out of Scope

- Fixing the streaming-watcher M4 milestone-source issue (separate concern; doesn't block this diagnosis).
- Fixing CI artifact preservation (separate concern; local diagnosis doesn't need it).
- Prose mitigations of any kind.
- Filing follow-up entities for whatever the diagnosis turns up — that's a captain triage decision after this completes.

## Cross-references

- **#177** — the original investigation that landed on the wrong diagnosis (parent-fo-log misread)
- **#178** — the falsified mitigation (recommended for rejection)
- **#181** — operational unblocker (CI pin to opus-4-6) — independent of this diagnostic
- **#183** (planned) — separate plumbing fix for `tests/test_gate_guardrail.py` (analogue of #179)
- **#184** (planned) — sonnet pin proposal (downstream of this diagnostic if it confirms FO-model swap is the right long-term answer)

## Test plan

- Local execution; no CI dispatch needed.
- ~30-60 minutes wallclock total: two pytest runs (~5-10 min each at low effort, +/- depending on hang behavior) + comparative analysis time.
- Cost: 2 live local Claude runs at `--max-budget-usd 2.00` each = ~$4 worst case.
- No new infrastructure needed; uses existing pytest invocation + `KEEP_TEST_DIR=1` mechanism.
- The investigation is fully reproducible: anyone with a local Claude Code 2.1.111+ install can re-run.
