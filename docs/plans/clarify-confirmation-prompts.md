---
id: 082
title: Clarify ambiguous confirmation prompts in commission and refit skills
status: backlog
source: code audit
started:
completed:
verdict:
score: 0.3
worktree:
issue: "#25"
pr:
---

The commission skill's design confirmation prompt is confusing:

```
Modify anything above, or confirm to generate. (y/n/changes)
```

Three options crammed into `y/n/changes` — unclear what each does. Should be a simple "accept or tell me what to change."

A secondary instance in the refit skill is also vague:

```
Proceed? (y/n)
```

"Proceed" with what? Doesn't name the action.

## Proposed Changes

1. **`skills/commission/SKILL.md` line 141** — Replace with: `Accept this design, or tell me what to change.`
2. **`skills/refit/SKILL.md` line 218** — Replace with: `Proceed with migration? (y/n)`

The other 7 confirmation prompts in refit are fine — they all name the action explicitly (replace agent?, create agent?, apply migration?, etc.).

## Stage Report: implementation

1. Commission SKILL.md line 141 updated — DONE. Replaced `Modify anything above, or confirm to generate. (y/n/changes)` with `Accept this design, or tell me what to change.`
2. Refit SKILL.md line 67 updated — DONE. Replaced bare `> Proceed?` with `> Proceed with this upgrade plan? (y/n)`
3. Refit SKILL.md line 150 updated — DONE. Replaced generic `> Proceed? (y/n)` with `> Proceed with pr-lieutenant migration? (y/n)`
4. Grep verification passes — DONE. All old strings absent, all new strings present (6/6 assertions passed).
5. Changes committed on ensign/clarify-confirmation-prompts branch — DONE. Commit 7f969e5.

## Stage Report: validation

1. Grep assertions — all 6 pass — DONE. Old strings `y/n/changes`, bare `> Proceed?`, and `> Proceed? (y/n)` are absent from their respective files. New strings `Accept this design, or tell me what to change.`, `Proceed with this upgrade plan? (y/n)`, and `Proceed with pr-lieutenant migration? (y/n)` are present.
2. No collateral damage — other confirmation prompts unchanged — DONE. The diff (commit 7f969e5) shows exactly 3 single-line changes across 2 files. The 5 OK prompts identified in ideation are untouched: `Update this mod? (y/n)` (refit:125), `Install it? (y/n)` (refit:133), `Apply this migration? (y/n)` (refit:189), `confirm or describe changes` (commission:95), `(y/n, default: y)` for pr-merge (commission:379).
3. Context check — surrounding lines of each edit are coherent — DONE. Each replacement fits naturally in its blockquote context and the subsequent instructions (wait for confirmation, handle acceptance) remain consistent with the new prompt wording.
4. Recommendation — PASSED. All acceptance criteria met. The three ambiguous prompts have been replaced with clear, action-specific alternatives. No unintended side effects.

### Round 2: Commission summary template rewrite

1. Commission summary template rewritten — conversational tone, no schema-speak — DONE. Replaced the field-list template (lines 128–141) with natural prose: captain intro, stage walkthrough, rejection flow, custom fields, pilot run items, file location.
2. Old field names removed — no "Entity:", "Item label:", "Seed entities:", "Address:", "Approval gates:" in the template — DONE. Grep confirms zero matches for these field names in SKILL.md.
3. New wording matches target — captain intro, natural stage intro, pilot run, file location sentence — DONE. Template opens with `I'll call you {captain}`, describes stages with lettered list, uses "Our pilot run will be with:", and closes with `All files will be created in {dir} for you to review.`
4. Consistency check — no stale references to old field names elsewhere in SKILL.md — DONE. Searched for "Seed entities", "Item label", "Approval gates:", and "Address:" across the full file — no matches outside the replaced block.
5. Changes committed on ensign/clarify-confirmation-prompts branch — DONE. Commit 5569381.

## Stage Report: validation (round 2)

1. Round 1 grep assertions (3 old absent, 3 new present) — DONE. `y/n/changes` and `Modify anything above, or confirm to generate` absent from commission SKILL.md. Bare `> Proceed?` and `> Proceed? (y/n)` absent from refit SKILL.md. New strings `Accept this design, or tell me what to change.` (commission:144), `Proceed with this upgrade plan? (y/n)` (refit:67), `Proceed with pr-lieutenant migration? (y/n)` (refit:150) all present.
2. Round 2 old field names absent from template — DONE. Grep confirms zero matches for `Entity:`, `Item label:`, `Seed entities:`, `Address:`, `Approval gates:` in commission SKILL.md.
3. Round 2 new conversational template present and correct — DONE. Template at lines 128-144 includes captain intro (`I'll call you {captain}`), stage listing with lettered format, rejection flow conditional, custom fields section, pilot run seed list, file location sentence, and confirmation prompt.
4. Captain default is uppercase "Captain" — DONE. Line 124: `{captain}` — "Captain".
5. Refit edits intact — DONE. `git diff 7f969e5..HEAD -- skills/refit/SKILL.md` produces no output; round 1 edits at lines 67 and 150 are unchanged.
6. No unintended changes — DONE. `git diff --name-only` across all task commits shows only three files: the entity file, commission SKILL.md, and refit SKILL.md.
7. Recommendation — PASSED. All acceptance criteria for both rounds are met.
