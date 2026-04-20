---
id: 194
title: "Investigate opus-4-7 FO flakiness on test_standing_teammate_spawn ECHO roundtrip"
status: done
source: "#188 cycle-1 AC-5 runs on opus-4-7 --effort low: test_standing_teammate_spawn 0/3 pass; test_feedback_keepalive 3/3 pass. Direct fo-log inspection shows the failures are NOT predicate-related (converted predicate is correct) — the FO simply fails to complete the ECHO roundtrip. Zero `ECHO: ping` occurrences in the fo-log; the FO stalls at various points: one run never reached ensign dispatch at all (Agent tool_use count = 0 in a run where it should be ≥1); two runs dispatched the ensign + SendMessage to echo-agent but echo-agent's reply never landed back in the stream within 300s."
started:
completed: 2026-04-20T06:46:00Z
verdict: PASSED
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Why this matters

After `test_standing_teammate_spawn`'s predicate was hardened (#185's archive-polling + #188's event-driven OR-gate), the test still fails on opus-4-7 at a high rate. Three isolation runs during #188 AC-5 verification:

| Run | Tool uses observed | Failure mode |
|-----|-------------------|--------------|
| 4 | `{Skill: 1, Read: 2, Bash: 7, ToolSearch: 1, TeamCreate: 1}` | FO stalled before ensign Agent dispatch |
| 5 | similar pattern | FO stalled similarly |
| 6 | `{Skill: 1, Read: 5, Bash: 10, ToolSearch: 1, TeamCreate: 1, Agent: 2, SendMessage: 2}` | Ensign + echo-agent dispatched; SendMessage to echo-agent fired; reply never arrived in parent stream within 300s |

All three runs: zero `ECHO: ping` substring in fo-log.jsonl. The old polling loop would have failed identically. The predicate conversion is correct; the test-level flakiness is an **upstream FO behavior issue specific to opus-4-7's handling of the ECHO roundtrip**.

## Contrast with #182

#182 was a similar investigation — opus-4-7 FO regression on this exact test. It was rejected for scope drift (added prose mitigations). The current state on main:
- #185: test predicate hardened to archive-polling, then event-driven OR-gate (#188 in flight)
- #183: ensign BashOutput polling prose
- #172: lazy standing-teammate spawn
- All landed; the test's surface is as robust as we can make it on the test side.

So the remaining flakiness is genuinely upstream — not something test-side hardening can fix.

## Contrast with #186 cycle 4

#186 cycle 4 ran the full suite once on opus-4-7 and saw `test_standing_teammate_spawn` PASS. Cycle 5 (currently running 2× isolation runs) will produce more data on opus-4-7 pass rate. The 0/3 result from #188 AC-5 is inconsistent with the 1/1 from #186 cycle 4 — flake rate is probably in the 30-70% range, not 100% or 0%.

## Scope for ideation

1. **Reproduce the three observed failure patterns** locally with `KEEP_TEST_DIR=1`; keep fo-log.jsonl artifacts from each pattern (pre-dispatch stall, post-SendMessage stall, other).
2. **Identify the FO-side event** that's blocking each pattern. Pre-dispatch stall: what's the FO doing for those 7+ Bash calls? Post-SendMessage stall: is the teammate-routing event arriving in Claude Code at all (check session log)? Or is the FO ignoring it?
3. **Discriminate** between (a) Claude Code SDK/runtime issue (out of spacedock scope; file upstream), (b) FO discipline gap that's NOT addressable via prose per the post-#182 rules, (c) mechanism fix in `claude-team` or similar spacedock-owned tooling.
4. **Recommend** one of: (a) file upstream + mark test as xfail on opus-4-7 until upstream fixes; (b) mechanism fix in spacedock; (c) accept ~40-60% flake rate and rely on CI retries.

## Out of scope

- Test-side predicate changes. #185 + #188 have done that work; the predicate is confirmed correct.
- Prose edits to `skills/first-officer/references/*` — captain's post-#182 rule.
- Full-suite testing — single-test investigation only.

## Acceptance criteria (entity-level, draft)

**AC-1** — 3 preserved fo-log.jsonl artifacts capture the failure patterns, committed under `docs/plans/_evidence/opus-4-7-standing-teammate-flakiness/`.

**AC-2** — Written diagnosis identifying which of the three paths (SDK issue / FO discipline gap / mechanism fix) the failure falls into, with cited evidence (fo-log line numbers, tool_use_ids, timestamps).

**AC-3** — Recommendation with captain decision-point: xfail-on-opus-4-7 / mechanism-fix / accept-flake-with-CI-retries.

## Test plan

- Local reproduction: 5 × `tests/test_standing_teammate_spawn.py` on opus-4-7 --effort low with `KEEP_TEST_DIR=1`. ~$8-10.
- No CI dispatch required.
- Cost ceiling: $15.

## Cross-references

- **#182** — original investigation of this same test (rejected for scope drift)
- **#185** — test-side predicate hardening (archive-polling → event-driven)
- **#186** — full-suite opus-4-7 green attempt (cycle 5 in flight)
- **#188** — streaming-watcher conversion (surfaced the 0/3 pattern during AC-5)
- Budget note: must respect post-#182 rules on prose-mitigation bans.

## 2026-04-18 session observation — not opus-4-7-specific

While diagnosing a CI failure on PR #127 (entity #188 `streaming-watcher-over-filesystem-polling`), the `claude-live-opus` job failed on `test_standing_teammate_spawn.py::test_standing_teammate_spawns_and_roundtrips`. The pinned model was `claude-opus-4-6`, NOT `claude-opus-4-7`.

Failure signature is the same CLASS as the one #194 already tracks: zero `ECHO: ping` substring anywhere in fo-log; FO advanced through ensign dispatch + shutdown + status transitions + git mv archive, then errored on `cleanup` tool ("Cannot cleanup team with 1 active member(s)") and exited code 1 at 165s wallclock. Predicate correctly never matched because FO never wrote the ECHO string.

Local `make test-live-claude-opus` on the rebased #188 branch PASSED the same test (same claude-opus-4-6 pin). Confirms the flake is non-deterministic, not deterministic.

**Scope widening implication:** the title and frontmatter currently say "opus-4-7 FO flakiness." The flake manifests on opus-4-6 too. The underlying issue appears to be FO-side standing-teammate-spawn completion, not model-specific. Future ideation should consider whether to rename/re-scope the entity to "multi-model FO-side standing-teammate-spawn flake" or similar.

## 2026-04-19 session observation — #203 cycle-3-fix routing

During #203 (green main for opus-4-7), the standing-teammate failure was diagnosed and routed here. Key new evidence separating this defect from the related budget-cap bug that #204 partially addressed:

**Budget-cap failure mode (distinct from ECHO-capture):** pre-shutdown-response-fix, every standing-teammate FO run burned the full $2 budget while waiting on an un-responded `shutdown_request`. Cycle-2 N=5 at opus-low pre-#204: 4/5 runs hit `error_max_budget_usd` at $2.02-$2.28. That failure mode is fixed by `#203`'s cycle-3-fix commit `a898216a` (new `## Shutdown Response Protocol` section in `ensign-shared-core.md`). Post-fix, FO cleanup exits cleanly — one cycle-3 N=2 run logged `subtype:success` at $1.71 and 3 turns. **That failure mode is closed; this entity is no longer about it.**

**ECHO-capture failure mode (remaining, #194's actual scope):** even with the shutdown-response fix in place, the `ECHO: ping` string never lands in the ensign's captured stream / entity body. Four of five watcher steps still PASS: spawn-standing invoked, echo-agent Agent() dispatched, ensign Agent() dispatched, SendMessage-to-echo-agent observed. The final step `archived entity body captured 'ECHO: ping'` fails — ensign receives the echo-agent SendMessage reply but does not write it to the entity. Across ~8 sampled runs post-#204 (cycle-2 + cycle-3 + validator), zero `ECHO: ping` occurrences in any fo-log. This narrows the defect to: **the ensign's handling of the echo-agent SendMessage reply → capture-into-entity-body path**, independent of budget/timeout/shutdown.

**Evidence preserved:**
- `/tmp/203-postfix-low-evidence/standing_teammate-run{1,2}-fo-log.jsonl` — cycle-2 post-#204 N=2 runs (run2 post-shutdown-fix at $1.71 is the cleanest isolation of "ECHO capture bug alone").
- `/tmp/203-cycle3-evidence/` — cycle-3-fix did not run this test (routed per brief), but earlier cycle fo-logs live here.
- `/tmp/203-local-low-evidence/standing_teammate-run{1..5}-fo-log.jsonl` — cycle-2 N=5 pre-#204 (contains the dominant budget-cap-then-no-ECHO pattern that #204 separated out).

**Scope implication for #194's ideation:** with the budget-cap path closed by `a898216a`, the remaining surface is narrow — echo-agent reply capture. The four candidate paths named in this entity's original Scope-for-ideation section (Claude Code SDK issue / FO discipline gap / mechanism fix / accept-flake-with-CI-retries) should now be evaluated against **that specific narrower failure mode**, not the composite that included budget burn.

**xfail plan** (executed on #203 branch, cycle-4-cleanup): `test_standing_teammate_spawns_and_roundtrips` gets `@pytest.mark.xfail(reason="#194 — ensign doesn't capture echo-agent reply to entity body on opus-4-7 at low effort", strict=False)` so CI doesn't stay red on this test while #194's investigation proceeds. Remove the xfail when #194 lands a fix.

## 2026-04-20 closure — subsumed by #203

Closed PASSED. #203 merged as PR #137 (merge commit `1dced356`) ships the combined resolution of this entity's scope:

1. **Budget-cap failure mode** — closed by #204 shutdown-response protocol (commit `a898216a` in the merged branch).

2. **"ECHO-capture" failure mode** — this entity hypothesized an ensign-discipline defect where the ensign received the echo-agent SendMessage reply but dropped the entity-body write. Cycle-10's CI fo-log diagnosis (commit `760c9149` in the merged branch) showed the ensign WAS capturing the reply correctly — it just wasn't writing a separate stage-report section to the entity body because the fixture prompt said "Include the captured reply in your stage report" (ambiguous). Ensigns interpreted that as "mention it in the Done message," which is a valid read — writing a stage-report-in-entity-body is a test artifact requirement, not a standing-teammate usage pattern default.

3. **Fix** — cycle-11's one-line prompt fix in `tests/fixtures/standing-teammate/001-echo-roundtrip.md` made the on-disk append explicit. Plus cycle-7's infrastructure (inbox-poll workaround for anthropics/claude-code#26426, keep-alive sentinel, ensign-subagent-jsonl close anchors) keeps the FO sane through the whole roundtrip in `claude -p` teams mode.

4. **Verification** — post-merge CI run (PR #137's last probe `24651696791`): all 5 live jobs green including `claude-live-opus` `test_standing_teammate_spawns_and_roundtrips` PASSED. The xfail decorator noted in the earlier closure plan was NOT applied in the final branch — cycle-8's actual fix made it unnecessary.

Verdict: PASSED. Hypothesized defect didn't exist as described; real fix was in a layer this entity's original scope didn't anticipate (fixture prompt + cycle-7 headless-mode infrastructure). The user-visible symptom `test_standing_teammate_spawn` flaking on opus-4-7-low is resolved.
