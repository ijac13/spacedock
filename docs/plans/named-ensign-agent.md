---
id: 046
title: Named ensign agent to replace prompt-within-a-prompt dispatch
status: ideation
source: adoption feedback
started: 2026-03-26T00:00:00Z
completed:
verdict:
score: 0.80
worktree:
---

The first officer currently copies a ~25-line prompt template verbatim when dispatching ensigns, filling named variables. The template says "copy exactly as written" three times — fighting the LLM's tendency to paraphrase or "improve." In practice, the first officer drifts: rewording instructions, dropping lines, injecting extra context.

Replace with a named ensign agent file that defines the behavior contract once. The first officer's dispatch becomes context injection ("entity X, stage Y, pipeline at Z") rather than template reproduction.

Motivated by adoption feedback: "Simplify the ensign prompt to a reference, not inline text."
