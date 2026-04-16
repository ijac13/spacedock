---
id: 170
title: "First-boot measurement harness — wallclock, turns, and token cost across project archetypes"
status: backlog
source: "CL direction during 2026-04-16 session — first concrete measurement target for the experiment workflow (#169)"
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Problem Statement

There is no repeatable way to measure spacedock's first-boot cost — the wallclock time, turn count, and token consumption from session start to first idle-at-dispatch-ready. This cost is the first thing a captain experiences and the most direct proxy for whether spacedock is getting heavier or lighter. Today the only way to measure it is to manually parse a session JSONL with ad-hoc `jq` pipelines (#168 addresses the tooling gap).

A measurement harness would let us:

- Baseline first-boot cost across project archetypes
- Detect regressions when contract prose, helper code, or scaffolding changes
- Validate that operating-contract trims (#169 experiment workflow) actually reduce cost
- Compare model tiers (opus vs sonnet) on the same boot workload

## Project archetypes (subjects)

1. **Empty repo** — `git init`, no `CLAUDE.md`, no workflow directory. Measures the pure discovery + "no workflow found" path.
2. **Empty repo + CLAUDE.md** — same as (1) but with a `CLAUDE.md` containing project-specific instructions. Measures whether `CLAUDE.md` length affects boot token budget.
3. **Scaffold project** — an existing workflow directory with entities, mods, standing teammates, and a `README.md`. This is the typical "captain opens a session" case. Measures the full `status --boot` → `TeamCreate` → standing-teammate spawn → dispatch-ready path.
4. **Messy-boot project** — scaffold project plus stale worktrees, orphan entities with dangling worktree fields, a PR-pending entity, and a mod-blocked entity. Measures worst-case boot: orphan reporting, PR-state checks, mod-block resumption. This is today's session (2026-04-16) in miniature.

## Metrics per run

- **Wallclock** — session start to first idle-at-dispatch-ready (or first gate presentation, whichever comes first).
- **Turns** — assistant-turn count from the session JSONL.
- **Tokens** — `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens` summed across all assistant turns.
- **Tool calls by type** — Read, Bash, Grep, ToolSearch, Skill, TeamCreate, Agent, SendMessage.
- **Error count** — `tool_result` entries with `is_error: true`.

## Control variables

- Pinned release commit (experiment runs against a frozen subject, per #169 direction).
- Model (opus, sonnet — measure both, or fix one for the baseline?).
- Cache state (first run = cold; second run in the same project = warm). Warm-cache measurement captures the cache-read benefit of stable system prompts.

## Open questions for ideation

- Where does the harness live? A test file (`tests/test_first_boot_cost.py`) in the E2E tier? A standalone script under `scripts/`? A bin tool under the experiment workflow?
- How is the session spawned? `CLAUDECODE` with a canned prompt? Through the existing `make test-e2e` pattern?
- How are project fixtures created? Temp dirs with `git init` plus seeded files? Symlinked from a fixtures directory?
- How is wallclock measured? Wrapper script timing, or extracted from JSONL timestamps?
- How are results stored? CSV, JSONL, or fed into the session-self-diagnosis tooling (#168)?
- Is this a one-shot baseline run or a regression-detection harness that runs in CI (or per-release)?

## Relationship to other tasks

- **#168 (session self-diagnosis)** — the diagnostic tooling would serve as the JSONL parser for extracting metrics. If #168 ships first, this harness consumes it. If not, the harness must include its own extraction logic, duplicating work #168 should canonicalize.
- **#169 (experiment workflow direction)** — the first-boot measurement is the first concrete experiment. Its design should be compatible with whatever placement option #169's ideation picks, even if #170 ships before #169 resolves.

## Out of Scope

- Automated regression detection (CI integration, alerting on cost increases). This task establishes a baseline; regression detection is follow-up.
- Multi-session behavioral measurement (FO correctness over N dispatches). That is a different experiment, one level up from boot cost.
- Changes to the boot path itself. This task measures; it does not optimize.
