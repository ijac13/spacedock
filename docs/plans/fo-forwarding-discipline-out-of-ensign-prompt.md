---
id: 206
title: "Relocate FO-forwarding discipline out of ensign prompts (into FO shared-core or helper output)"
status: backlog
source: "2026-04-19 session captain observation: the ensign dispatch prompt assembled by `claude-team build` ends with a fineprint block addressed to the FO (not the ensign): `**If you are the first officer forwarding this prompt to Agent():** copy the entire block above into Agent(prompt=...) character-for-character. Do NOT paraphrase SendMessage(to=\"team-lead\", ...) ...` — this is an FO-directed forwarding-discipline instruction embedded inside the ENSIGN's prompt body, which wastes ensign context and creates mild confusion risk about who the instruction is for. #204 just established the principle that discipline should live where the agent who needs it lives (ensign shared-core reaches ensigns via Skill-invoke; FO shared-core is where FO reads its own discipline). This task applies that principle to the forwarding-guidance fineprint."
started:
completed:
verdict:
score: 0.5
worktree:
issue:
pr:
mod-block:
---

The `claude-team build` emitted prompt currently ends with a fineprint block addressed to the first officer, instructing the FO to forward the prompt verbatim and specifically not to paraphrase the `SendMessage(to="team-lead", ...)` completion-signal literal into English prose. The fineprint is load-bearing — without it, a naive FO can paraphrase the completion-signal literal and the ensign then narrates sending a message rather than calling the SendMessage tool, breaking the completion-signal loop. But the fineprint lives in the ENSIGN's prompt body, which is the wrong audience.

## Why the current location is wrong

- **Ensigns waste context** reading FO-directed instructions. On opus-low at 15s soft budget this matters.
- **Confusion risk:** an ensign might read "forward this prompt to Agent()" as a reflexive instruction about its own behavior. Has not been observed, but is a real failure mode.
- **Principle violation:** #204 established that discipline belongs where the consumer lives. FO-forwarding discipline belongs in FO shared-core or in helper output, not smuggled through the ensign's payload.

## Proposed approaches (ideation to decide)

1. **Move to FO shared-core.** Add a `## Dispatch Forwarding` section to `skills/first-officer/references/first-officer-shared-core.md` that contains the "forward verbatim, do not paraphrase the completion-signal literal" discipline. Remove the fineprint from `claude-team build`'s output. FO reads its own shared-core at boot; the discipline applies to every dispatch without per-prompt reminder.

2. **Emit as a sibling field in helper JSON.** Extend `claude-team build` output to include a `forwarding_notes` field (or similar) that the FO reads before calling Agent(). Keeps the discipline attached to the dispatch but out of the prompt body.

3. **Hybrid.** Shared-core carries the general discipline; helper emits per-dispatch specifics only when non-default (e.g., if a dispatch has an unusual completion-signal shape).

Ideation selects one.

## Acceptance criteria (draft; ideation to refine)

- **AC-1:** `claude-team build` emitted prompt no longer contains the `**If you are the first officer forwarding this prompt to Agent():**` fineprint or any FO-directed meta-instruction. Verified by substring absence test in `tests/test_claude_team.py`.
- **AC-2:** FO-forwarding discipline documented in its new location (shared-core section, helper output field, or both) with wording at least as specific as the current fineprint about the parenthesis-equals syntax.
- **AC-3:** Existing FO behavior unchanged — `SendMessage(to="team-lead", ...)` literal continues to reach ensigns as a tool-call directive, not English narration. Verified by smoke-dispatching a throwaway ensign and inspecting its jsonl for the literal `SendMessage` tool call (same check as #204's AC-2).
- **AC-4:** `make test-static` green post-merge.

## Out of scope

- Broader refactor of `claude-team build`'s prompt-assembly layering. This task is the narrow relocation only.
- Changes to the completion-signal protocol itself. Signal remains `SendMessage(to="team-lead", message="Done: ...")`.

## Cross-references

- #204 — established the "discipline lives with its consumer" principle (Skill-invoke directive ships in cmd_build output so ensigns get it; shared-core is the single source of truth)
- #202 — FO behavior spec + RTM; when it lands, this relocation's outcome should surface as a requirement in the FO-R-NNN taxonomy so it can't drift back into the ensign prompt
- Historical context: the fineprint was likely added after an incident where an FO paraphrased the completion signal; the artifact has been load-bearing but placed imprecisely.
