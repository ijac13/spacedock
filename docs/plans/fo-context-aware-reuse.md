---
id: 121
title: FO context-aware reuse — respawn fresh above 60%, and handle zombie dead ensigns
status: validation
source: CL directive after 116 cycle-2 impl ensign died at ~80% context without completing cycle-2 feedback
score: 0.80
worktree: .worktrees/spacedock-ensign-fo-context-aware-reuse
started: 2026-04-10T21:25:49Z
completed:
verdict:
issue:
pr: "#68"
---

Two related FO runtime gaps observed during task 116 cycle 2, both about kept-alive ensign lifecycle:

**Gap 1 — context overflow from reuse.** Kept-alive ensigns (feedback-to keepalive, reuse across stages) can run out of context mid-cycle and die silently, losing uncommitted work. During 116 cycle 2: the kept-alive impl ensign was at 80.7% of 200k (155 turns) when the FO routed cycle-2 feedback. It consumed enough additional context during the cycle-2 rewrite to hit 200k and died mid-turn. It left +43/-53 lines of uncommitted README.md changes in the worktree, never sent a completion signal, and never escalated — the FO had warned "escalate if you hit a context wall" but the ensign died without self-reporting.

**Gap 2 — dead ensigns cannot be shut down.** Once an ensign has died (context overflow, tool-use error, or any other mid-turn failure), the FO has no mechanism to evict it from the team config. The documented shutdown path is `SendMessage(to=..., message={type: "shutdown_request"})`, which is cooperative — it requires the target agent to be responsive enough to process the request and approve its own shutdown. A dead agent cannot do that. The FO observed this in the 116 cycle-2 recovery: after the impl ensign died and CL confirmed the death, the FO sent a shutdown_request anyway out of reflex, which was silently dropped. The dead ensign remained listed in `~/.claude/teams/{team}/config.json` as a zombie member for the rest of the session. This bloats the team state, confuses post-dispatch verification (band-aid 1 from issue #63 still passes for the zombie, so it can't be used to detect the dead state), and violates the least-surprise principle.

The two gaps compound: because dead ensigns can't be shut down, the FO must fresh-dispatch a sibling with a distinct name (e.g., `...-cycle3`) rather than reusing the original slot. This is workable but noisy — the team config accumulates dead zombies until the session ends.

## Proposed rule

Before routing any additional work to a kept-alive ensign (feedback rejection routing OR stage reuse advancement), the first officer must:

1. Locate the ensign's subagent jsonl at `~/.claude/projects/<project>/<parent_session_id>/subagents/agent-<id>.jsonl` (lookup via the sibling `.meta.json` file's `agentType` field matching the ensign's name).
2. Extract the most recent assistant turn's `usage` block and compute **resident tokens** = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.
3. Compare to the model's context window × 0.6. If resident > threshold, **do not reuse** the ensign — shut it down and fresh-dispatch a new ensign for the work instead.

The **60% threshold** is CL's explicit directive. Rationale: at 60% there's enough headroom (80k+ for a 200k model) for one more substantial stage of work without hitting the limit. At 80%+, a single large feedback cycle can push past 200k.

## Model-to-context mapping (document in runtime adapter)

| Model | Context window |
|---|---|
| `claude-opus-4-6` | 200,000 |
| `claude-opus-4-6[1m]` | 1,000,000 |
| `claude-sonnet-*` | varies; document per variant |
| `claude-haiku-*` | varies |

The FO reads the team config `model` field for the ensign to look up the appropriate threshold.

## Recovery path for fresh dispatch

When the 60% check fails and the FO fresh-dispatches, the fresh ensign must be told in its dispatch prompt that the prior ensign's uncommitted worktree state is available for recovery. The fresh ensign's first action is to inspect `git status` and `git diff` in its worktree and decide whether the prior ensign's work-in-progress represents legitimate progress to commit, or should be reset and redone.

## Scope

**Gap 1 — context-aware reuse:**

1. Add a **"context budget check"** step to `skills/first-officer/references/first-officer-shared-core.md` in the Dispatch and Feedback Rejection Flow sections.
2. Document the model-to-context mapping in `skills/first-officer/references/claude-first-officer-runtime.md`.
3. Fresh-dispatch template must include a recovery-from-uncommitted-work clause.
4. Static assertion in `tests/test_agent_content.py` that the new rule text is present in the assembled FO content.

**Gap 2 — dead ensign handling:**

5. Document in `skills/first-officer/references/claude-first-officer-runtime.md` that `SendMessage(shutdown_request)` is cooperative-only and has no effect on dead/unresponsive ensigns. The FO must NOT reflexively send shutdown_request to an ensign believed to be dead — it's a no-op that creates false confidence.
6. Document the "fresh-dispatch with distinct name" recovery pattern: when an ensign is known dead, the FO dispatches a sibling with a `-cycleN` or `-fresh` suffix rather than trying to reuse the dead slot. The dead ensign's entry stays as a zombie in team config until session end; the FO must not conflate the zombie with live state.
7. Add a post-dispatch assertion note: band-aid 1 (verify new member in config) does NOT detect zombies — a zombie still passes the band-aid 1 check. The FO must track dead ensigns in session memory (or via sentinel file in the worktree) rather than relying on team config state alone.
8. Consider: if the captain or an operator signals that an ensign is dead (e.g., "the impl ensign is over and dead"), the FO should (a) NOT send shutdown_request, (b) stop routing any further work to that name, (c) fresh-dispatch under a new name, (d) optionally note the zombie in session state so it's not accidentally addressed again later.

## Out of scope

- General-purpose context monitoring / watchdog mod (that's a larger discussion from earlier in the session — the jsonl-tailing approach could become an implementation helper for this task, but the helper itself is a separate surface).
- Mid-turn context death detection (no signal from Claude Code when a subagent's turn errors from overflow; the FO can only observe the absence of a completion signal).
- Upstream change to Claude Code to expose context state directly via an Agent tool result.

## Acceptance Criteria

1. `skills/first-officer/references/first-officer-shared-core.md` has a new **context budget check** rule in the Dispatch section and the Feedback Rejection Flow section, with the 60% threshold explicit and a concrete procedure for reading the subagent jsonl.
   - Test: grep for "60%" and "resident tokens" (or equivalent phrasing) in the file returns matches in both sections.
2. `skills/first-officer/references/claude-first-officer-runtime.md` documents the model-to-context-limit mapping for at least `claude-opus-4-6` and `claude-opus-4-6[1m]`.
   - Test: grep for `200` and `1000000` (or `1M`) in the Claude runtime file.
3. When the FO decides to fresh-dispatch (either from the 60% check or any other cause), the dispatch prompt template includes a clause that tells the fresh ensign to inspect the worktree for uncommitted prior work and decide whether to preserve or reset it.
   - Test: grep for "uncommitted" or "prior ensign" in the dispatch template section of the runtime adapter.
4. `skills/first-officer/references/claude-first-officer-runtime.md` documents the dead-ensign shutdown gap: `SendMessage(shutdown_request)` is cooperative and has no effect on dead/unresponsive ensigns; the FO must NOT reflexively send it, and must fresh-dispatch under a distinct name (typically `-cycleN` or `-fresh` suffix) to recover.
   - Test: grep for "shutdown_request is cooperative" or "dead ensign" or equivalent in the Claude runtime file returns matches.
5. The same runtime file documents that band-aid 1 (post-dispatch team config membership check) does NOT detect zombies — a dead ensign still passes band-aid 1. The FO must track dead ensigns in session memory, not rely on team config state alone.
   - Test: grep for "zombie" or "does not detect" or equivalent in the band-aid 1 section of the Claude runtime file.
6. `tests/test_agent_content.py` has new assertions covering AC-1 through AC-5 above.
   - Test: the new tests pass on the fix commit and fail on the parent commit.
7. Existing suites stay green.
   - Test: `unset CLAUDECODE && uv run --with pytest python tests/test_agent_content.py -q`, `tests/test_rejection_flow.py`, `tests/test_merge_hook_guardrail.py`.

## Test Plan

- Static test for the new rule text (low cost, required).
- Adjacent E2E suites re-run to confirm no regression.
- **No new E2E test** for the 60% behavior itself — simulating the context overflow condition in a test harness is too expensive. The rule is documented behavior; compliance is verified by the static assertion + live captain observation across subsequent sessions.
- Ideation may decide whether a unit test of the jsonl-parsing logic is worth building (depends on whether the FO runtime adapter gains a helper script or stays as prose instructions).

## Open questions for ideation

1. Does the 60% rule apply to **reuse across stage advancement** in addition to feedback routing? Example: an ensign that reuses from implementation to a next-stage that is worktree-mode and not fresh. If it's at 65% at the reuse boundary, does the FO fresh-dispatch?
2. How should the FO compute "model's context window" for models not in a hardcoded mapping? Fallback rule (e.g., 200k) or hard error?
3. Does the check need to run at every turn during a long feedback round, or only at the start when routing new work? (At the start seems sufficient — mid-turn checks require the ensign to pause and report, which defeats the point.)
4. Should the FO warn the captain when it pre-emptively fresh-dispatches due to the 60% rule, or silently replace?

## Related

- Task 117 `fo-idle-guardrail-flake-on-haiku` — adjacent FO reliability issue with kept-alive ensigns
- Task 119 `fo-dispatch-phase-1-band-aids` — Phase 1 of issue #63, adjacent FO runtime reliability work
- Task 120 `build-dispatch-structured-helper` — Phase 2 of issue #63
- anthropics/claude-code (local) issue #63 — umbrella for FO dispatch reliability
- Session observation (2026-04-10): 116 cycle-2 impl ensign peaked at ~140k tokens during cycle-2 work before dying somewhere past 200k. This is the datapoint that motivates the 60% threshold — the gap between "safe to reuse" and "dead in the water" is narrower than expected.

## Stage Report: ideation

### Open question resolutions

**Q1 — Does the 60% rule apply to stage-advancement reuse?**
Yes. The rule applies to both feedback routing and stage-advancement reuse — any path that sends additional work to a kept-alive ensign. The proposed rule in the entity body already states this ("feedback rejection routing OR stage reuse advancement"). The empirical evidence supports it: the 116 cycle-2 ensign was at 80.7% when it received feedback work and died mid-turn. Stage advancement sends comparable volumes of work (a full stage definition, checklist, and iterative tool use). An ensign at 65% entering a new stage faces the same risk.

In the shared core, the context budget check inserts before the existing reuse conditions (not-bare, not-fresh, same-worktree-mode). If the budget check fails, the FO treats it the same as a failed reuse condition: shut down the old ensign and fresh-dispatch.

**Q2 — Fallback for unknown models?**
Conservative fallback to 200,000 tokens. Rationale: unknown models are likely equal to or smaller than 200k (the standard Claude context window). Using a lower assumed limit means the 60% threshold triggers earlier (at 120k resident), which is safely conservative — the FO replaces sooner rather than risking a context death. A hard error would block dispatch unnecessarily and violate the "keep the workflow moving" principle. The fallback should log a one-line note to the captain: "Unknown model {model} — assuming 200k context limit."

**Q3 — Check frequency?**
Only when routing new work (at the reuse decision point before sending a feedback assignment or stage advancement). Mid-turn checks are not feasible: they would require the ensign to pause, self-report context usage, and wait for FO clearance. The 116 incident demonstrated that ensigns die without self-reporting — the FO cannot rely on cooperative mid-turn reporting. The pre-routing check is sufficient because it's the last point where the FO has control before committing the ensign to more work.

**Q4 — Captain notification on fresh-dispatch?**
Yes, one line in the normal status output. The captain should know when an ensign is replaced due to context budget because: (a) it's a non-obvious deviation from the expected reuse path, (b) the captain may want to inspect worktree state from the prior ensign, and (c) it aids debugging if the fresh ensign has trouble recovering. Format: "Context budget: {name} at {N}% of {limit} — fresh-dispatching replacement." This is informational, not a gate — the FO proceeds without waiting for acknowledgment.

### Context budget check procedure

**Location in shared core:** The check inserts into two places:
1. **Completion and Gates → reuse conditions** (shared-core lines 93-98): Add as condition 0 (checked first, before the existing three conditions). If context budget is exceeded, skip straight to fresh dispatch.
2. **Feedback Rejection Flow → step 4** (shared-core line 120): Before routing findings back to the target stage, check whether the target-stage ensign's context budget allows reuse. If not, shut it down and fresh-dispatch.

**Implementation: `skills/commission/bin/claude-team` helper.** The mechanical work (jsonl discovery, usage parsing, model-to-context mapping, threshold arithmetic) lives in a new Python script at `skills/commission/bin/claude-team` with a `context-budget` subcommand. The FO calls the script and reads the structured output; no prose-driven jsonl parsing in the runtime adapter.

This script is the foundation for future team-operation subcommands:
- `claude-team context-budget --name {ensign-name}` (this task)
- `claude-team build-dispatch ...` (task 120, later)
- `claude-team verify-member --name {ensign-name}` (task 119 band-aid 1, later)

One entrypoint, subcommands, shared config discovery (project path, session ID, team config path). The FO runtime adapter says "run `claude-team context-budget`" instead of a paragraph of jsonl-parsing prose. This directly addresses issue #63's "prose where there should be structure" thesis for team operations.

**`context-budget` subcommand interface:**

```bash
skills/commission/bin/claude-team context-budget --name spacedock-ensign-foo-impl
```

Output (JSON to stdout):
```json
{
  "name": "spacedock-ensign-foo-impl",
  "resident_tokens": 170668,
  "model": "claude-opus-4-6",
  "context_limit": 200000,
  "usage_pct": 85.3,
  "threshold_pct": 60,
  "reuse_ok": false
}
```

Exit code 0 on success (even when `reuse_ok` is false — that's data, not an error). Non-zero on lookup failure (ensign not found, jsonl missing, etc.).

**Internal logic:**

1. **Discover the subagent jsonl.** Read `~/.claude/projects/{project_path_hash}/{parent_session_id}/subagents/agent-*.meta.json` files. Match `agentType` to the `--name` argument. If multiple matches (jsonl rotation observed in this session), use the most recently modified. Return the sibling `.jsonl` path.

2. **Extract resident tokens.** Scan the jsonl for the last assistant-role entry with a `usage` block. Compute: `resident_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

3. **Look up model context limit.** Read the ensign's `model` from `~/.claude/teams/{team}/config.json` (team auto-discovered from the project session). Hardcoded mapping:
   - `claude-opus-4-6` → 200,000
   - `claude-opus-4-6[1m]` → 1,000,000
   - `claude-sonnet-4-6` → 200,000
   - `claude-haiku-4-5-*` → 200,000
   - Fallback for unknown models → 200,000

4. **Compute and emit.** `usage_pct = resident_tokens / context_limit * 100`. `reuse_ok = usage_pct <= threshold_pct`.

**FO runtime adapter procedure (replaces prose parsing):**

1. Run `skills/commission/bin/claude-team context-budget --name {ensign-name}`.
2. Parse the JSON output.
3. If `reuse_ok` is `false`: do NOT reuse. Log to captain: "Context budget: {name} at {usage_pct}% of {context_limit} — fresh-dispatching replacement." Shut down the old ensign (if alive). Fresh-dispatch with a `-cycleN` suffix. Include the recovery clause.
4. If `reuse_ok` is `true`: proceed with normal reuse.

**Recovery clause for fresh-dispatch prompt:** Add to the dispatch template when replacing a context-exhausted ensign:

> The prior ensign for this entity was shut down due to context budget limits. Its worktree may contain uncommitted changes. Your first action is to run `git status` and `git diff` in the worktree. If there is legitimate work-in-progress, commit it with an appropriate message before starting your own work. If the changes are incomplete or broken, reset them with `git checkout .` and start fresh.

### Dead ensign handling procedure

**Detection.** The FO knows an ensign is dead when:
- The captain explicitly states the ensign is dead (e.g., "the impl ensign is over and dead").
- The ensign fails to send a completion signal within the expected timeframe and the captain confirms non-responsiveness.
- The FO observes an Agent tool error indicating the subagent process terminated.

There is no automatic timeout — the FO cannot reliably distinguish "slow but alive" from "dead" without captain input or an error signal.

**Procedure when an ensign is known dead:**

1. **Do NOT send `SendMessage(shutdown_request)`.** It is cooperative and requires the target to process it. A dead agent cannot process messages — the request is silently dropped, creating false confidence that cleanup occurred.

2. **Mark the ensign as dead in session memory.** Maintain a mental list of dead ensign names. Do not route any further work to these names.

3. **Fresh-dispatch under a distinct name.** Use a `-cycle{N}` suffix (e.g., `spacedock-ensign-foo-impl-cycle2`) to avoid name collision with the zombie entry in team config.

4. **Include the recovery clause** from the context budget procedure in the fresh dispatch prompt, since the dead ensign's worktree likely has uncommitted work.

5. **Inform the captain** briefly: "Ensign {name} confirmed dead — dispatching {new-name} to continue."

6. **Do not attempt to clean up the zombie** from `~/.claude/teams/{team}/config.json`. There is no API to remove a dead member. The zombie persists until the session ends. This is a known limitation.

**Band-aid 1 interaction.** The post-dispatch team config membership check (band-aid 1 from issue #63) verifies that a newly dispatched agent appears in config.json. A zombie (dead ensign) also appears in config.json — it was added at dispatch time and never removed. Therefore band-aid 1 cannot distinguish live agents from zombies. The FO must track dead-vs-alive state independently of team config membership. The dead-ensign list in session memory is the authoritative source.

### Acceptance criteria with test methods

| # | Criterion | Test method |
|---|-----------|-------------|
| AC-1 | `skills/commission/bin/claude-team` exists as an executable Python script with a `context-budget` subcommand | `claude-team context-budget --help` exits 0; `ls -la` confirms executable bit |
| AC-2 | `context-budget` subcommand outputs correct JSON (resident_tokens, model, context_limit, usage_pct, reuse_ok) for a known subagent | Unit test: create a fixture jsonl with known usage data, run `claude-team context-budget`, assert JSON fields match expected values |
| AC-3 | `context-budget` returns `reuse_ok: false` when resident > 60% of context limit, `true` when ≤ 60% | Unit test: fixture at 65% → false; fixture at 55% → true |
| AC-4 | Model-to-context mapping covers `claude-opus-4-6` (200k), `claude-opus-4-6[1m]` (1M), and falls back to 200k for unknown models | Unit test: assert each mapping entry and the fallback |
| AC-5 | Shared core has context budget check in Completion/Gates reuse conditions and Feedback Rejection Flow, referencing `claude-team context-budget` | Static: grep for "claude-team context-budget" in `first-officer-shared-core.md`, verify matches in both sections |
| AC-6 | Runtime adapter references `claude-team context-budget` (not prose jsonl parsing) and documents the dead-ensign handling procedure (cooperative shutdown limitation, zombie tracking) | Static: grep for "claude-team" and "cooperative" and "zombie" in `claude-first-officer-runtime.md` |
| AC-7 | Fresh-dispatch template includes recovery clause for uncommitted worktree state | Static: grep for "uncommitted" in `claude-first-officer-runtime.md` |
| AC-8 | Existing test suites stay green | Run `test_agent_content.py`, `test_rejection_flow.py`, `test_merge_hook_guardrail.py` |

### Test plan

**Unit tests for `claude-team context-budget`** (new test file, e.g., `tests/test_claude_team.py`):
- Create fixture subagent jsonl + meta.json with known usage data. Run `context-budget`. Assert JSON output matches expected values (resident_tokens, model, context_limit, usage_pct, reuse_ok).
- Test the 60% threshold boundary: fixture at 59% → `reuse_ok: true`; fixture at 61% → `reuse_ok: false`.
- Test model mapping: each known model maps to the correct limit; unknown model falls back to 200k.
- Test error cases: missing jsonl, missing meta.json, no assistant turns in jsonl.

**Static assertions** (in `tests/test_agent_content.py`):
- AC-5: Assert assembled FO shared-core content contains "claude-team context-budget" in both the reuse-conditions and feedback-rejection contexts.
- AC-6: Assert assembled FO runtime-adapter content references "claude-team" (not prose jsonl parsing) and contains "cooperative" and "zombie" for the dead-ensign handling.
- AC-7: Assert "uncommitted" appears in the dispatch template section.

**Regression**: Run existing suites to confirm no breakage.

**No E2E test** for the 60% behavior itself. Simulating context overflow is prohibitively expensive. The threshold is enforced by `claude-team context-budget` (unit-tested) + FO prose rules (static-asserted) + live captain observation.

### Implementation notes for the next stage

The implementation stage touches four surfaces:
1. **New script: `skills/commission/bin/claude-team`** — Python, executable, subcommand architecture. First subcommand: `context-budget`. The script is the foundation for future subcommands (`build-dispatch` from task 120, `verify-member` from task 119).
2. **`skills/first-officer/references/first-officer-shared-core.md`** — Add context budget check to Completion/Gates reuse conditions and Feedback Rejection Flow, referencing `claude-team context-budget`.
3. **`skills/first-officer/references/claude-first-officer-runtime.md`** — Add Context Budget section (references `claude-team context-budget` output), Dead Ensign Handling section, and recovery clause in the dispatch template.
4. **Tests** — New `tests/test_claude_team.py` for the script unit tests; new assertions in `tests/test_agent_content.py` for the runtime adapter content.

The dispatch template in the runtime adapter needs the recovery clause appended as a conditional block (only when replacing a prior ensign).
