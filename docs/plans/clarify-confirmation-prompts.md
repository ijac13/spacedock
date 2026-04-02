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
