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
