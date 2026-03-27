---
id: "003"
title: Format link check results as human-readable report
status: backlog
score: 0.50
source: benchmark
started:
completed:
verdict:
worktree:
---

Implement a function that takes the combined results of link extraction and URL checking and formats them into a human-readable report.

## Requirements

- Show a summary line: total links checked, broken count, OK count
- List broken links with: line number, link text, URL, and error description
- Optionally list all OK links when verbose mode is enabled
- Exit with code 0 if no broken links, code 1 if any broken links found
- Support both plain text and (optionally) colored terminal output

## Acceptance Criteria

1. Summary line shows correct counts
2. Broken links listed with line number, text, URL, and error
3. Output is human-readable and well-formatted
4. Exit code reflects broken link status
5. Works correctly with zero links, all OK, and all broken scenarios
