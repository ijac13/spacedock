---
id: 066
title: Fix workflow discovery — FO greps home directory instead of project root
status: ideation
source: 058 terminology experiment validation
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
---

The first-officer template's startup step 1 tells the FO to discover workflow directories by running `grep -rl '^commissioned-by: spacedock@' --include='README.md' .` from the project root. In practice, agents expand `.` to absolute paths or search from `~` instead of the project root, finding workflow READMEs outside the current project.

## Problem

Discovered during terminology experiment (058) validation. All 28 benchmark runs across 4 variants searched `/Users/clkao` (home directory) instead of `.` (project root). When multiple `commissioned-by:` READMEs exist on the machine, the FO may latch onto the wrong project's workflow — in this case, the real spacedock project instead of the test fixture.

Recovery is inconsistent: some runs notice the pwd mismatch and re-search locally, others proceed with the wrong project. This inconsistency caused kitchen variant runs to score lower on pipeline completion and role adherence — not because of terminology differences, but because of how each run handled the discovery failure.

## Impact

- **Test harness reliability**: Benchmark results are contaminated by discovery failures. The 058 experiment cannot produce clean results until this is fixed.
- **Production workflows**: Any machine with multiple spacedock-commissioned workflows risks cross-contamination.
- **Scoring validity**: Protocol compliance and role adherence scores are conflated with discovery success/failure.

## Scope

Fix the FO template's workflow discovery to be robust against path expansion. The fix should ensure the FO searches only within the project root, not the home directory or broader filesystem.
