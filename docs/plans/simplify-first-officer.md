---
id: 048
title: Simplify first officer prompt — judgment over mechanics
status: ideation
source: adoption feedback
depends: 045, 046
started: 2026-03-27T00:00:00Z
completed:
verdict:
score: 0.70
worktree:
---

Once the status --next option (045) and named ensign agent (046) exist, the first officer can shed most of its mechanical orchestration and focus on LLM-appropriate work: understanding, judgment, communication.

Key simplifications:
- Drop ensign reuse — always dispatch fresh. Worktree persists, work isn't lost. Eliminates a branching path.
- Trim direct communication protocol from 40 lines to a few — "if the captain tells you to back off an ensign, stop coordinating it until told to resume." Or move to a separate doc read on demand.
- Replace manual state scanning with `status --next` calls.
- Replace prompt template copying with named ensign agent dispatch.

Target: ~80 lines, down from ~285.

Motivated by adoption feedback: "Let the first officer be an LLM doing LLM-appropriate work, and let code do the deterministic orchestration."
