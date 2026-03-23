---
title: Commission Speed — Reduce Time to Value
status: backlog
source: CL feedback
started:
completed:
verdict:
score: 0.80
worktree:
---

The interactive commission flow asks 7 questions one at a time. This is the main bottleneck for time-to-value — a new user waits through a lengthy Q&A before seeing any output.

## Problem

Each question requires a round-trip: agent asks, user answers, agent processes. With 7 questions that's 7+ turns before generation begins. For users who know what they want, this is friction.

## Directions to explore

- **Fewer questions**: Combine related questions or derive answers from context. Do we really need 7?
- **Freeform intake**: Accept a single description and infer the pipeline structure. "I want to track blog posts through draft → review → published" should be enough.
- **Express mode**: 2-3 essential questions (what's the pipeline for, what are the stages), derive the rest with smart defaults.
- **Better batch mode UX**: The batch mode exists but requires knowing the exact format. Could be more forgiving.
- **Progressive disclosure**: Generate with defaults after minimal input, let the user refine afterward via refit.
