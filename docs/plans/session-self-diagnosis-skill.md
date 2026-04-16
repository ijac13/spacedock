---
id: 168
title: "Session self-diagnosis tooling as a skill"
status: backlog
source: "CL observation during 2026-04-16 session after the FO was asked to diagnose its own JSONL (tool errors, token usage, why comm-officer spawned eagerly). The ad-hoc jq pipeline approach burned 3+ turns per diagnostic run and cache-read the full session JSONL for each question."
started:
completed:
verdict:
score:
worktree:
issue:
pr:
---

## Problem Statement

Session self-diagnosis — enumerating tool-use errors, counting tool calls by type, measuring token consumption by turn, auditing which references were read — currently requires the FO (or the captain) to write ad-hoc `jq` pipelines against the session JSONL. The diagnostic work itself consumes session context:

- Each `jq` invocation reads the full session JSONL (hundreds of KB) and produces cache-read pressure.
- Tool-call enumeration, error extraction, and token tallies are composable but have no canonical entry point.
- When CL asks for diagnosis, the FO burns 3+ turns rederiving one-off queries.

A purpose-built diagnostic surface (skill, bin tool, or standing specialist) would expose stable queries and return compact summaries without re-reading the whole JSONL for each question.

## Context

This surfaced during the 2026-04-16 boot when CL asked for self-diagnosis covering:

- tool-use errors and their root causes
- why comm-officer was spawned eagerly (contract-driven, not a bug)
- token inefficiencies in `Bash` usage and file reads
- whether `@reference` inlining made certain `Read` calls duplicative (it did not in this session)

Answering required three separate `jq` pipelines and one Python script. The JSONL parsing logic was rederived for each call.

## Options (for ideation)

(a) **Claude Code skill** — `session-diagnose` that loads on demand and emits a structured report (errors, top-N expensive turns, tool-use distribution, `Read`/`Bash` hot paths). Skill body documents the canonical queries and their expected outputs.

(b) **Bin tool** — `skills/first-officer/bin/session-diagnose` with subcommands (`--errors`, `--tokens`, `--tool-calls`, `--read-audit`). Invoked by the FO during debrief or on explicit captain request. Pipelined `jq` queries hidden behind a stable CLI.

(c) **Standing specialist** — a `diagnostics-officer` teammate (same pattern as comm-officer) spawned on demand, reads the JSONL once per session, caches summary, answers follow-up questions without re-reading.

(d) **Debrief integration** — fold session self-diagnosis into the existing debrief skill rather than standing up a separate surface. Debrief already iterates over session state; adding diagnostic output is a natural extension.

All four share the same core: precomputed answers to a stable set of diagnostic questions against the session JSONL, avoiding ad-hoc `jq` rederivation.

## Open questions for ideation

- Which surface is right — skill, bin tool, standing specialist, or debrief-integrated?
- Which diagnostic views are load-bearing versus nice-to-have? (errors, tool-call counts, token totals by turn, `Read`/`Bash` hot paths, dispatch-latency breakdown, duplicate-`Read` detection)
- Does the tool need to correlate the main-session JSONL with subagent JSONLs under `~/.claude/projects/.../{session_id}/subagents/agent-*.jsonl`? How is the session path itself discovered — env var, argument, or auto-detect?
- Scope: human-triggered only, or FO-initiated (automatic end-of-session summary, pre-debrief snapshot)?
- Does this generalize beyond spacedock — useful to any Claude Code captain — or stay spacedock-specific?

## Out of Scope

- Real-time diagnostic dashboards or live JSONL tailing.
- Changes to Claude Code's native telemetry surface.
- Cross-session aggregation (multi-session drift analysis) — single-session focus for v1.
- Automated fix suggestions — this is a reporting tool, not a remediation tool.
