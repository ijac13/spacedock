---
id: 105
title: Add idle hallucination guardrail to FO runtime
status: validation
source: CL — observed twice in production sessions
started: 2026-04-09T05:11:48Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-idle-hallucination-guardrail
issue:
pr:
---

After repeated idle notifications with no human input, the FO can hallucinate a user instruction (e.g., "Human: let's do a debrief and wrap up") and act on it. This has happened twice, causing destructive actions (unauthorized agent shutdowns, fabricated debrief invocations).

## Root cause

Idle notifications arrive as `user`-role messages. After enough consecutive ones with no real human content, the model fills the silence by generating text that looks like a user turn and then acts on it.

## Proposed fix

Add to `references/claude-first-officer-runtime.md` in the Agent Back-off section:

**IDLE HALLUCINATION GUARDRAIL:** After acknowledging idle notifications once (e.g., "Ensign still available, standing by"), produce ZERO output for all subsequent idle notifications until a real human message arrives. Do not generate text, invoke tools, or take any action in response to repeated idle notifications.

## Acceptance criteria

1. The guardrail text is present in `references/claude-first-officer-runtime.md`
2. Existing guardrails in the Agent Back-off section are preserved
3. No other files are modified

## Stage Report — implementation

1. Add IDLE HALLUCINATION GUARDRAIL paragraph to references/claude-first-officer-runtime.md — DONE
2. Verify existing DISPATCH IDLE GUARDRAIL is preserved unchanged — DONE (line 113, text identical to original)
3. Verify no other files are modified — DONE (`git diff --stat` shows only `references/claude-first-officer-runtime.md`, 2 insertions)
4. Commit the change — DONE

### Summary

Added the IDLE HALLUCINATION GUARDRAIL paragraph to `references/claude-first-officer-runtime.md` in the Agent Back-off section, immediately after the existing DISPATCH IDLE GUARDRAIL. The new paragraph instructs the FO to produce zero output after the first idle acknowledgment, preventing the known failure mode where the model hallucinates user instructions after long sequences of idle notifications.

## Stage Report — validation

1. Verify IDLE HALLUCINATION GUARDRAIL text is present in references/claude-first-officer-runtime.md — DONE (line 115, text matches proposed fix)
2. Verify DISPATCH IDLE GUARDRAIL is preserved unchanged — DONE (line 113, byte-identical to pre-implementation version)
3. Verify no other files were modified by the implementation commit — DONE (commit f9f99c6 modifies `references/claude-first-officer-runtime.md` with 2 insertions, plus the entity file stage report which is expected workflow bookkeeping)
4. Recommendation: **PASSED**

### Summary

All three acceptance criteria are met. The IDLE HALLUCINATION GUARDRAIL paragraph was correctly added to the Agent Back-off section of `references/claude-first-officer-runtime.md` immediately after the existing DISPATCH IDLE GUARDRAIL. The existing guardrail text is unchanged. No unexpected files were modified.
