---
id: "002"
title: Check URL reachability
status: backlog
score: 0.50
source: benchmark
started:
completed:
verdict:
worktree:
---

Implement a function that takes a list of URLs and checks each one for HTTP reachability, returning the status of each URL.

## Requirements

- Use HTTP HEAD requests first, falling back to GET if HEAD returns 405
- Set a configurable timeout (default 10 seconds)
- Handle common failure modes: connection refused, DNS resolution failure, SSL errors, timeouts
- Return a structured result for each URL: url, status_code (or None), reachable (bool), error (string or None)
- Support concurrent checking for performance (optional but preferred)

## Acceptance Criteria

1. Correctly identifies reachable URLs (HTTP 200)
2. Correctly identifies unreachable URLs (connection errors, 404, etc.)
3. Handles timeouts without crashing
4. Handles invalid/malformed URLs gracefully
5. Uses HEAD with GET fallback
