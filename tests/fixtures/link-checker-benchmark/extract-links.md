---
id: "001"
title: Extract markdown links with line numbers
status: backlog
score: 0.50
source: benchmark
started:
completed:
verdict:
worktree:
---

Implement a function that parses a Markdown file and extracts all `[text](url)` links, returning each link with its line number, link text, and URL.

## Requirements

- Parse standard Markdown link syntax: `[text](url)`
- Handle multiple links on a single line
- Ignore image links (`![alt](url)`) — only extract regular links
- Ignore links inside code blocks (fenced with triple backticks)
- Return results as a list of structured objects with fields: line_number, text, url
- Handle empty files and files with no links gracefully

## Acceptance Criteria

1. Correctly extracts links from a sample markdown file
2. Reports accurate line numbers for each link
3. Ignores image links
4. Ignores links inside fenced code blocks
5. Handles edge cases: empty file, no links, malformed links
