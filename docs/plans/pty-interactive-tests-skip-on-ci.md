---
id: 155
title: "PTY interactive tests skip on CI — ubuntu-latest has no real TTY"
status: backlog
source: "PR #94 (#148 pytest migration) cycle-6 CI — test_interactive_poc_live fails deterministically across all 3 claude live jobs: 'turn 1 did not echo ALPHA_MARKER'"
started:
completed:
verdict:
score: 0.45
worktree:
issue:
pr:
---

`tests/test_interactive_poc.py::test_interactive_poc_live` fails deterministically on GitHub Actions `ubuntu-latest` runners across claude-live, claude-live-bare, and claude-live-opus. Identical failure shape on all three: the PTY-wrapped `claude` session opens ("Session ready"), receives `"Say exactly ALPHA_MARKER"`, but neither the ALPHA nor BETA marker ever comes back in the session output. 0 subagents spawned.

Root cause: GitHub Actions runners do not attach a real TTY by default. The `InteractiveSession` harness at `scripts/test_lib_interactive.py` uses `pty.openpty()` to wrap `claude` interactively, which works locally in a terminal but behaves degradedly in CI — `claude -p` expects line-edited stdin and flushed-on-newline output, and some combination of non-TTY stdin buffering + headless output + the `Shift+Down` key-sequence semantics doesn't actually run through.

Pre-#148 this test was a `main()`-style `uv run` script. It was loosely collected by pytest when the suite was invoked (because `def test_interactive_poc_live` was defined), but the old Makefile `&&` short-circuit on live tests meant an earlier failing test short-circuited the chain before this ever fired. #148's two-tier pytest shape (serial + parallel, no short-circuit) runs this test on every CI, exposing the pre-existing CI-environment gap.

## Problem Statement

`test_interactive_poc_live` verifies real-TTY-dependent behavior (Shift+Down peer-messaging, inline ensign chat affordance). Those affordances exist for operators using Claude Code interactively on their own terminal; they don't exist when the user is `claude -p` running non-interactively on a headless runner. CI has no signal to provide for this test's invariant.

Options:

1. **Unconditional skip** — mark the test `@pytest.mark.skip(reason="requires real TTY; CI runners are headless — see #155")`. Cheapest, most honest. Test remains runnable locally for developers on a real terminal. This is the path cycle 7 on #148 will take as a band-aid.

2. **CI-detection skip** — detect `os.isatty(sys.stdin.fileno())` or an env var like `GITHUB_ACTIONS=true` and skip only in those environments. More clever, but `claude -p` is launched *by* the test, not inherited from the test's stdin, so the actual PTY test happens against a subprocess that the test controls. Detection would be "is this running under GITHUB_ACTIONS?" which is pragmatic but couples the test to a specific CI provider.

3. **Split the test** — extract the non-PTY assertions (fixture setup, config loading, library-level unit-ish checks) into a companion test that runs everywhere; keep the PTY-behavior assertions in a separate test that skips on CI.

4. **Fix the harness** — run `claude` under `expect`-style PTY forwarding that actually presents a TTY to the subprocess inside the CI runner. Non-trivial; possibly still flaky.

## Desired Outcome

`make test-live-claude` (and `-bare` and `-opus`) pass on CI when the only otherwise-failing test is `test_interactive_poc_live`. The PTY affordances the test covers remain verified during local development.

## Out of Scope

- Fixing `claude -p` itself to behave correctly under non-TTY stdin (not our code)
- Rewriting the PTY harness as a core infrastructure change (spin into its own task if option 4 becomes load-bearing)
- The content-drift test family tracked in #154 — different root cause, different fix shape

## Acceptance Criteria (provisional)

- `test_interactive_poc_live` does not fail any claude-live CI job
- The test still runs when invoked locally from a real terminal (option 1 or 3 — option 2 explicitly allows local runs)
- If option 3 is chosen, the non-PTY assertions run in CI and guard against regressions in the non-interactive parts of the harness
- The reason string on the skip (if option 1 or 2) references `#155` so `grep '#155'` locates every touchpoint

## Prior Art

- Task #148 — the pytest migration that exposed this
- Task #154 — sibling follow-up for content-drift test failures (different root cause)
- The test body itself has a `Shift+Down` key sequence — its scope is specifically the Claude Code team-chat peer-messaging affordance. That affordance is already a local-only user-facing feature.

## Forward Plan

Cycle 7 on #148 takes option 1 (unconditional skip) as a band-aid to unblock the PR. Once #148 merges, this task is worked to either:
- Confirm option 1 is acceptable long-term (formalize the skip reason, add `reason` links here) and close
- OR pick option 3 (split the test) if there's appetite for more CI coverage of the non-PTY parts

Score 0.45 reflects that the failure is CI-environment noise, not a code regression — the priority is "do not block PR merges" rather than "restore full coverage."
