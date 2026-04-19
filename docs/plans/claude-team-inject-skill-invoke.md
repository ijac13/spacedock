---
id: 204
title: "Inject Skill(skill='spacedock:ensign') first-action directive in claude-team build prompt output"
status: backlog
source: "2026-04-19 session — discovered during #203 implementation stage. Ensign committed timeout/budget knob-turns with no fo-log evidence of budget exhaustion; jsonl census of current session's subagents showed zero Skill tool invocations across 133 tool calls (ideation ensign 44, implementation ensign 74, staff-reviewer-203 15). Smoke test agent `ensign-skill-smoketest` dispatched with explicit user-message `Skill(skill=\"spacedock:ensign\")` directive → Skill call fires as `caller: direct`, content loads, ## Operating contract + ## Runtime adapter headings enter context, @references/ files load transitively."
started:
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

Ensign subagents dispatched via `Agent(subagent_type="spacedock:ensign", team_name=...)` never load their operating contract. The agent-definition skill preload in `agents/ensign.md` frontmatter does not fire under Claude Code team mode, and the fallback prose ("If your operating contract was not already loaded via skill preloading, invoke the `spacedock:ensign` skill now to load it") is not being executed either. Every dispatched ensign runs without the shared-core discipline in context: no BashOutput polling discipline (#183), no stage-report format spec, no scaffolding-change guards, no completion-signal protocol, no evidence-before-knob-turn convention.

## Evidence

| Subagent (session `spacedock-plans-20260419-0345-a7x2k9m4`) | Type | First-turn tool uses | Skill invocations |
|---|---|---:|---:|
| `abce3a80…` | `spacedock-ensign-opus-4-7-green-main-ideation` | 44 | **0** |
| `a76dfaf9…` | `spacedock-ensign-opus-4-7-green-main-implementation` | 74 | **0** |
| `a4491003…` | `staff-reviewer-203` (general-purpose) | 15 | **0** |

Smoke test with explicit Skill directive (`ensign-skill-smoketest` subagent, file `agent-acb2c679…`, 11 jsonl lines):

```
1. Skill(skill="spacedock:ensign")   ← caller: direct, succeeded
2. ToolSearch                         ← looking up SendMessage
3. SendMessage(to="team-lead")        ← confirmation
```

The smoke test proves: ensign subagents CAN invoke Skill, DO invoke it when told explicitly via user-message prompt, and the skill content (including transitive `@references/ensign-shared-core.md` load) enters context successfully. This mirrors the working standing-teammate pattern (comm-officer's spawn prompt already does explicit skill-availability checks via ToolSearch).

## Scope of the fix

Modify `skills/commission/bin/claude-team` (the `build` subcommand) to prepend a first-action directive to the emitted prompt body. Estimated 5-10 line change. The directive should:

- Be the FIRST content the ensign sees in its user-message prompt
- Instruct an explicit `Skill(skill="spacedock:ensign")` call
- Note that if preload ever starts working, the call is idempotent
- NOT depend on the broken agent-definition preload path

Similar discipline applies to the standing-teammate build path if any standing teammate currently lacks explicit skill-invoke prose. Audit during ideation.

## Why this likely blocks (or collapses) #203

The three failing tests under investigation in #203 (`test_feedback_keepalive`, `test_merge_hook_guardrail`, `test_standing_teammate_spawn`) watch an FO subprocess's tool-use stream for specific ensign behaviors — completion signals, stage-report writes, data-flow edits. Without the operating contract loaded, ensigns:

1. Improvise completion signals (sometimes SendMessage, sometimes plain text, sometimes JSON) → FO step-timeout fires
2. Write stage reports in arbitrary format → test watcher regex misses
3. Burn wallclock on blocking `sleep` instead of `BashOutput` polling → 120s/300s walls exceeded

The **CI-vs-local divergence** observed in #203's ideation (local 3/3 PASS vs CI 3/3 FAIL on the same HEAD) fits this hypothesis: fast local hardware absorbs the no-contract floundering under the step-timeouts; slow CI runners don't. After #204 ships, re-running the three failing tests on CI with zero test-code changes should clarify how much of #203 is really #204 in disguise.

Acceptance criteria and a test plan will be defined during ideation per the workflow README.
