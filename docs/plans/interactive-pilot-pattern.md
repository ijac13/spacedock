---
id: 019
title: Design a pattern for pilots that interact directly with the captain
status: implementation
source: testflight-005
started: 2026-03-24T00:00:00Z
completed:
verdict:
score: 0.50
worktree: .worktrees/ensign-interactive-pilot-pattern
---

## Problem Statement

CL can talk directly to team ensigns — they're all teammates in the same team via SendMessage. The first officer has no awareness or internal state for when CL enters direct conversation with an ensign. This creates three problems:

1. **The first officer doesn't know to step back.** It may continue relaying, sending new work, or shutting down an ensign that CL is actively talking to.
2. **No handoff protocol.** CL uses informal signals like "I will discuss with the ensign in the ready room" but the first officer doesn't know what this means operationally.
3. **No resume signal.** When CL finishes direct communication, the first officer doesn't know the ensign is "back" under its coordination, or what (if anything) changed.

## Entry Points

Two scenarios trigger direct communication:

**A. CL-initiated ("ready room").** CL decides to talk to an ensign directly. CL tells the first officer something like "I'll talk to ensign-foo directly" or "taking ensign-foo to the ready room." This is a deliberate handoff — CL knows what they want to discuss.

**B. Escalated clarification.** An ensign sends repeated clarification requests through the relay (ensign -> first officer -> CL -> first officer -> ensign). After a round or two, CL decides the relay is overhead and wants to cut it out. CL tells the first officer "I'll handle this directly with ensign-foo" or simply starts messaging the ensign.

Both cases have the same shape: CL signals that they're taking over direct communication with a specific ensign.

## Proposed Approach

### Signal Protocol

The protocol uses explicit messages between CL and the first officer. No frontmatter changes — this is conversational state, not pipeline state.

**Entering direct communication:**

CL sends a message to the first officer indicating they're taking direct communication with a specific ensign. The first officer should recognize any of these patterns:
- "I'll talk to ensign-{slug} directly"
- "Taking ensign-{slug} to the ready room"
- "I'll handle this with ensign-{slug}"
- Or any clear indication that CL is going to communicate directly with a named ensign

The first officer acknowledges and marks that ensign as "in direct communication with CL" in its internal tracking.

**Exiting direct communication:**

CL sends a message to the first officer when done:
- "Done with ensign-{slug}, back to you"
- "ensign-{slug} is yours again"
- "Ready room complete for ensign-{slug}"

CL may include a summary of what was discussed/changed, or may not. The first officer should ask if it needs context to continue coordination.

### First Officer Behavior During Direct Communication

When an ensign is in direct communication with CL:

1. **Do not send work or instructions to that ensign.** The first officer must not dispatch new stages, send follow-up messages, or issue shutdown to the ensign while CL has it.
2. **Do not relay for that ensign.** If the ensign sends a message to team-lead while in direct communication, the first officer should note it but not act — CL is handling it directly.
3. **Continue other pipeline work.** The rest of the pipeline is unaffected. The first officer should continue dispatching and managing other tasks normally. The ensign in direct communication is temporarily outside the first officer's coordination, but no other work is blocked by this.
4. **Do not prompt CL for status.** Don't nag CL about whether they're done. CL will signal when they're done.

### Resume Protocol

When CL signals that direct communication is over:

1. **First officer asks for context if needed.** "What changed during your conversation with ensign-{slug}? Any updates I should know about?" — but only if the first officer needs the information to continue coordinating. If CL volunteers a summary, use that.
2. **Check ensign state.** The ensign may have done additional work, changed direction, or may need new instructions. The first officer should check the task file and any recent commits to understand the current state before resuming coordination.
3. **Resume normal coordination.** The ensign goes back to being managed by the first officer. The normal dispatch/event loop applies again.

### What Doesn't Change

- **No frontmatter fields.** Direct communication is a transient conversational state, not a pipeline state. Adding a field like `direct-comm: true` to frontmatter would require commits for entering/exiting, pollute git history, and conflate conversational coordination with pipeline state. The first officer tracks this internally.
- **No changes to the ensign prompt.** Ensigns don't need to know about this protocol. They already send messages to team-lead; CL can also message them directly. From the ensign's perspective, they're just getting messages from different teammates.
- **No changes to the stage machine.** Direct communication can happen in any stage. It doesn't create a new stage or modify transitions.

### Edge Cases

**CL messages an ensign without telling the first officer first.** This can happen — CL just starts messaging ensign-foo directly. If the first officer notices CL is talking to an ensign (e.g., CL forwards a message, or the ensign references a conversation with CL), the first officer should ask CL: "Are you in direct communication with ensign-{slug}? Should I hold off on coordinating with them?" This is the fallback — the protocol works best when CL signals explicitly, but it degrades gracefully.

**Ensign completes its stage work while in direct communication.** If the ensign sends its completion message to team-lead while CL has it in direct communication, the first officer notes the completion but does NOT proceed with the normal post-completion flow (gate checks, next dispatch, shutdown). It waits for CL to signal that direct communication is over, then resumes the normal flow.

**CL modifies the task file during direct communication.** CL may edit the task body, acceptance criteria, or scope during direct communication. When the first officer resumes, it should re-read the task file to pick up any changes.

**Multiple ensigns in direct communication.** CL could theoretically take multiple ensigns into direct communication simultaneously. The protocol handles this naturally — each ensign is tracked independently.

**Session crash during direct communication.** If the session crashes while an ensign is in direct communication, the state is lost (since it's conversational, not persisted). On restart, the orphan detection procedure handles the ensign normally. This is acceptable — session crashes are already disruptive, and the orphan procedure is the right recovery mechanism.

## Implementation: First Officer Agent Changes

The implementation requires adding a section to the first officer agent prompt. Specifically:

1. **Add a "Direct Communication" section** after the Clarification section in `first-officer.md`. This section documents:
   - How to recognize CL's signal that they're taking direct communication
   - What to do (and not do) while an ensign is in direct communication
   - How to handle the resume signal
   - The edge cases above

2. **Amend the Event Loop section** to include a check: before acting on an ensign message or dispatching to an ensign, verify the ensign is not currently in direct communication with CL.

3. **Amend the Clarification section** to mention the escalation path: if CL decides to handle clarification directly, the first officer recognizes this as entering direct communication mode.

No code changes. No frontmatter schema changes. No status script changes. This is purely a prompt/protocol addition to the first officer agent.

## Acceptance Criteria

1. The first officer agent prompt includes a Direct Communication section that covers entering, behavior during, and exiting direct communication.
2. The event loop includes a guard against acting on ensigns that are in direct communication with CL.
3. The clarification section references the escalation-to-direct-communication path.
4. No frontmatter schema changes, no new stages, no code changes.
5. The protocol degrades gracefully when CL messages an ensign without signaling the first officer first.

## Implementation Summary

All changes are in `templates/first-officer.md` (the template used by commission to generate first-officer agents for new pipelines).

**Clarification section** (line 174): Added step 3 to "When an ensign asks for clarification" — if CL decides to handle clarification directly, the first officer recognizes this as entering direct communication.

**Direct Communication section** (lines 180-223): Added after Clarification, before Event Loop. Contains four subsections:
- **Entering direct communication** — signal patterns CL uses, acknowledgment behavior, clarification escalation link.
- **Behavior during direct communication** — four rules (no work dispatch, no relay, continue other work, no status nagging) plus the edge case where an ensign completes while in direct communication.
- **Exiting direct communication** — resume signals, context gathering, re-read entity file, process pending completions, resume coordination.
- **Detecting unsignaled direct communication** — graceful degradation when CL messages an ensign without telling the first officer first.

**Event Loop section** (lines 229, 233, 234): Three amendments:
- Step 1: guard on receiving worker messages from ensigns in direct communication.
- Step 5: skip dispatch for ensigns in direct communication.
- Step 6: "in direct communication" added to the list of reasons the pipeline can be idle.

## Validation Report

### Acceptance Criteria Results

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Direct Communication section covers entering, behavior during, and exiting | PASS | Four subsections at lines 184, 196, 207, 221 cover all three phases plus unsignaled detection |
| 2 | Event loop includes guard against acting on ensigns in direct communication | PASS | Guards added at step 1 (line 229: don't act on messages), step 5 (line 233: skip dispatch), step 6 (line 234: idle condition) |
| 3 | Clarification section references escalation-to-direct-communication path | PASS | Step 3 added at line 174 linking clarification escalation to the Direct Communication protocol |
| 4 | No frontmatter schema changes, no new stages, no code changes | PASS | Only two files changed: `templates/first-officer.md` (prompt additions) and this task file (summary). `git diff --stat` confirms no other files touched |
| 5 | Protocol degrades gracefully when CL messages ensign without signaling | PASS | "Detecting unsignaled direct communication" subsection (line 221-223) instructs first officer to ask CL proactively |

### Structural Checks

| Check | Result | Detail |
|-------|--------|--------|
| Section placement | PASS | Direct Communication placed after Clarification (line 153) and before Event Loop (line 225), as specified in design |
| Existing guardrails intact | PASS | All four guardrails verified present: Agent tool required (line 45), subagent_type prohibition (line 47), TeamCreate in startup (line 19), report-once (line 236) |
| Template variable consistency | PASS | New section uses `{slug}` consistently with the rest of the template; no new template variables introduced |
| Edge case coverage | PASS | All five edge cases from the design are addressed: unsignaled communication, completion during direct comm, task file modification during direct comm, multiple ensigns (handled naturally per-ensign), session crash (conversational state, orphan detection handles recovery) |
| Design fidelity | PASS | Implementation matches proposed approach exactly — no deviations, additions, or omissions |

### Notes

- The full commission test script (`scripts/test-commission.sh`) was not run because it requires a live `claude` API call. The template changes are purely additive prompt text — no structural changes to the template's variable substitution, section ordering, or guardrail patterns that the commission test validates.
- No code, no frontmatter schema, no status script changes — this is a prompt-only addition, so the commission test's file-existence, frontmatter, and guardrail checks would all pass unchanged.

### Recommendation: PASSED
