---
id: 047
title: Checklist as scannable gate artifact
status: implementation
source: adoption feedback, CL
started: 2026-03-27T00:00:00Z
completed:
verdict:
score: 0.75
worktree: .worktrees/ensign-checklist-artifact
---

The current checklist review has the first officer doing 2-3 rounds of SendMessage back-and-forth per ensign per stage: check completeness, challenge skip rationales, triage failures. Each round eats tokens and risks the first officer losing track of overall pipeline state while deep in one entity's checklist negotiation.

Instead: the ensign writes the structured completion report into the entity file body. The first officer reads it once and presents it to the captain at the gate. Skip rationale judgment moves to the gate review with the captain, rather than the first officer playing arbiter alone.

One read, no negotiation rounds.

Motivated by adoption feedback: "Make the checklist a gate artifact, not a conversation."

Also incorporates task 044 (checklist report format): the format should be tight and scannable — not prose-heavy. Status markers (DONE/SKIPPED/FAILED) at a glance, not buried in paragraphs. Domain-agnostic — a legal review pipeline and a software dev pipeline use the same report structure. Reference: superpowers plugin patterns (status enums, emoji markers, bullet lists with specific references).

## Problem Statement

Two distinct problems with the current checklist protocol:

**1. Conversation, not artifact.** The ensign reports via SendMessage. The first officer parses the message, does 2-3 rounds of back-and-forth (completeness check, skip rationale challenge, failure triage), then summarizes for the captain at the gate. Each round burns tokens. The first officer risks losing track of overall pipeline state while deep in one entity's negotiation. The report is ephemeral — it lives in agent message history, not on disk.

**2. Prose-heavy format.** Status words (DONE/SKIPPED/FAILED) are inline in the message text. Evidence is freeform. A captain reviewing a gate has to read paragraphs to extract the status of each item. This doesn't scale to pipelines with many checklist items.

## Proposed Approach

### Core change: ensign writes report into entity file

The ensign writes a `## Stage Report: {stage_name}` section at the end of the entity file body. This is the artifact. The ensign still sends a SendMessage to signal completion, but the message is a pointer ("Done, report written to file") — the substance is in the file.

The first officer reads the entity file once after receiving the completion signal. No back-and-forth negotiation. If the report section is structurally incomplete (missing items), the first officer sends the ensign back once to fix the file — but this is a structural completeness check, not a judgment call on rationales.

### Report format

The format must be:
- **Scannable** — status visible at a glance without reading prose
- **Domain-agnostic** — works for legal review, software dev, research, anything
- **Flat** — no nested structures; one line per item plus optional evidence line

```
## Stage Report: {stage_name}

- [x] {item text}
  {one-line evidence or reference}
- [ ] SKIP: {item text}
  {one-line rationale}
- [ ] FAIL: {item text}
  {one-line details}

### Summary

{2-3 sentences: what was done, key decisions, anything notable}
```

Design rationale for this format:

**Markdown checkboxes (`- [x]` / `- [ ]`).** Universally recognized. Renders as checkboxes in GitHub, editors, and most markdown viewers. `[x]` = done, `[ ]` = not done (with SKIP/FAIL prefix to distinguish). Scannable: just look at the checkmarks.

**Status prefix on incomplete items.** `SKIP:` and `FAIL:` appear right after `[ ]` so a reader scanning the unchecked boxes immediately knows which are intentional skips vs. failures. Done items need no prefix — the `[x]` says it all.

**One-line evidence, indented.** Each item gets at most one indented follow-up line for evidence/rationale/details. Keeps the report compact. If an ensign needs more space, they can reference a file or section ("see validation report below"). The constraint forces concision.

**No separate "stage requirements" vs "acceptance criteria" grouping.** The current protocol groups items by source. This adds structure without value — the reviewer cares about status, not provenance. Items are listed flat in the order they were given.

### Where in the entity file

Appended to the end of the entity body, after any existing content (implementation summary, acceptance criteria, etc.). Each stage that completes adds its own `## Stage Report: {stage_name}` section. Multiple stages accumulate — the entity file becomes a running record.

This means:
- The ideation stage report follows the acceptance criteria
- The implementation stage report follows the implementation summary
- The validation stage report follows the validation findings
- The entity file tells the full story when read top to bottom

### Ensign completion message (SendMessage)

The ensign still sends a SendMessage to signal completion. But the message becomes minimal:

```
Done: {entity title} completed {stage}. Report written to {entity_file_path}.
```

No checklist in the message. No summary in the message. The file is the artifact.

### First officer review (replaces step 7)

The current step 7 has three sub-steps with potential back-and-forth. The replacement:

1. **Read the entity file** — Parse the `## Stage Report: {stage_name}` section.
2. **Structural completeness** — Verify every dispatched checklist item appears in the report. If items are missing, send the ensign back once to update the file. (This is rare — the ensign has the checklist in its prompt and writes directly to the file.)
3. **Proceed** — No skip rationale judgment. No failure triage negotiation. The report is what it is.

Skip rationale judgment and failure triage move to the gate review with the captain. For non-gate stages, the first officer proceeds without judgment — if the ensign skipped or failed items in a non-gate stage, the next stage's ensign (or the validation stage) will catch it.

### Gate reporting

At gate stages, the first officer reads the entity file and presents the stage report section to the captain verbatim. The first officer adds its own one-line assessment:

```
Gate review: {entity title} — {stage}

{paste the ## Stage Report section from the entity file}

Assessment: {N} items done, {N} skipped, {N} failed. [Recommend approve / Recommend reject: {reason}]
```

The captain sees the raw report and the first officer's summary. The captain makes the judgment call on skip rationales and failure impact. This is better than the current protocol where the first officer pre-filters and the captain gets a second-hand account.

### Interaction with ensign lifecycle

- **Initial dispatch (Agent)**: Ensign prompt gets the checklist items as before. New instruction: "Write your stage report into the entity file as a `## Stage Report: {stage_name}` section at the end of the body." Completion message format changes to the minimal pointer.
- **Reuse dispatch (SendMessage)**: Same change — ensign writes report to file, sends minimal completion message.
- **Redo after rejection**: Ensign overwrites the `## Stage Report` section (same stage name, so it replaces the previous one). The old report is gone — the redo result is what matters.

## Acceptance Criteria

1. Ensign prompt template instructs ensigns to write a `## Stage Report: {stage_name}` section into the entity file body using the markdown checkbox format.
2. Ensign completion SendMessage is a minimal pointer to the file, not a full report.
3. First officer step 7 (checklist review) is replaced with: read file, check structural completeness, proceed. No back-and-forth rounds for rationale review.
4. First officer gate reporting pastes the stage report section from the entity file and adds a one-line assessment.
5. The format uses `- [x]` / `- [ ] SKIP:` / `- [ ] FAIL:` with one-line evidence/rationale per item.
6. The reuse dispatch path (SendMessage to existing ensign) uses the same file-based report pattern.
7. Redo after rejection overwrites the previous stage report section.

## Open Questions

**Q: Should the first officer still judge skip rationales at non-gate stages?**
Proposed answer: No. At non-gate stages, the first officer checks structural completeness only. Substantive judgment happens at gates with the captain. Rationale: the first officer's back-and-forth was the token-burning problem this task solves. If a skip matters, it surfaces at the gate. If there's no gate, the downstream stage will encounter the gap.

**Q: What if the entity file gets long with accumulated stage reports?**
Proposed answer: This is acceptable. Entity files are the record of what happened. A file with 3-4 stage reports (ideation, implementation, validation) is 20-40 lines of report content — not a problem. If it becomes an issue, a future task can archive old stage reports.

**Q: Does this change the entity file schema in README?**
Proposed answer: No. The `## Stage Report` section is an operational convention in the entity body, not a schema field. The README doesn't need to document it — the first-officer template handles it. However, the README's stage definitions should note that ensigns write reports to the entity file (this is an "Outputs" convention).
