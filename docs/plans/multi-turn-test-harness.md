---
id: 102
title: "Spike: multi-turn team test harness"
status: implementation
source: "099 testing gap — no infra for interactive team behavior tests"
started: 2026-04-08T18:49:36Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-multi-turn-test-harness
issue:
pr:
---

We can't test team interaction behavior (idle handling, captain-to-ensign communication, agent routing) because all tests use `claude -p` (single prompt, single response). This spike investigates what's feasible and builds a minimum viable multi-turn test harness.

## Spike questions

1. Can `claude` be driven interactively via PTY (`pexpect` or `pty` module)?
2. Where do agent JSONL logs live in team sessions — one per agent, or merged into the FO's log?
3. If ensign JSONL is captured separately, can we verify ensign behavior (direct text vs SendMessage) purely from log analysis without interactive input?
4. Can the captain switch to talking directly to an ensign mid-session, and how does that appear in logs?
5. What's the minimum code needed to: start a session, wait for agent spawn, inject a user message, collect logs, shut down?

## Success criteria

- Answer all 5 spike questions with evidence (actual test runs, not speculation)
- If PTY driving works: produce a working `test_lib.InteractiveSession` class (~80-100 lines) that can start claude, send messages, wait for JSONL patterns, and collect logs
- If PTY driving doesn't work: document why and propose alternatives
- If JSONL-only analysis suffices for the 099 test cases: document the approach and show it working on a sample log

## Stage Report

### Question 1: Can `claude` be driven interactively via PTY?

**DONE** — Yes, PTY driving works reliably.

**What works:**
- Python's stdlib `pty.fork()` creates a pseudo-terminal that Claude Code's interactive TUI renders into
- Characters typed via `os.write(fd, char)` appear in the TUI input field
- Carriage return (`\r`) submits the message
- The model processes the message and renders the response in the TUI
- Multi-turn works: after the first response, a new prompt (`❯`) appears and accepts the next message
- Verified with two sequential turns: msg1 sent at 8.4s got response at 16.8s, msg2 at 19.9s got response at 22.1s

**What doesn't work:**
- `--input-format stream-json` with `-p` mode: this is for the SDK bridge protocol, not user-driven multi-turn. Messages of type `user_message` are accepted but never processed — the session completes with only hook output and no assistant response. The stream-json input is consumed by the bridge/repl layer which expects `control_response`, `control_request`, and `user` type messages via the SDK transport.
- `--no-session-persistence` cannot be used in interactive mode (only with `--print`)
- `pexpect` is not installed system-wide and cannot be pip-installed due to PEP 668 restrictions. The stdlib `pty` module works as a drop-in replacement.

**Key challenges solved:**
- ANSI escape sequence stripping: Claude Code's TUI uses extensive ANSI codes including `\x1b[>...` private mode sequences that naive regex misses
- Ready detection: the prompt character `❯` (U+276F) is the reliable signal that the TUI accepts input; checking for `>` matches spurious ANSI fragments
- Pattern detection: the TUI echoes typed input, so detecting a response requires seeing the pattern at least twice in ANSI-stripped output (echo + response)

### Question 2: Where do agent JSONL logs live in team sessions?

**DONE** — Logs are per-agent in a `subagents/` subdirectory.

**Log structure:**
```
~/.claude/projects/<project-slug>/
  <session-uuid>.jsonl          # Main session (FO/captain) log
  <session-uuid>/
    subagents/
      agent-<id>.jsonl          # Individual agent conversation log
      agent-<id>.meta.json      # Agent metadata: {"agentType": "...", "description": "..."}
```

**Evidence:**
- Session `0dbb2460` (spacedock project): 11 subagent logs across 2 entities
- Session `0d5fb02e`: 92 subagent logs from a long-running multi-entity session
- Test run sessions (under `~/.claude/projects/-private-var-folders-...`) also produce subagent directories
- Agent meta.json contains `agentType` (matches the agent `name` from the `Agent()` tool call) and `description`

**What each log contains:**
- Main session JSONL: FO perspective — `Agent()` tool calls (dispatch), `SendMessage()` to agents, `TeamCreate`/`TeamDelete`
- Subagent JSONL: agent perspective — all tool calls (`Read`, `Edit`, `Bash`, `SendMessage`), text output blocks, and user messages (the bootstrap prompt)

### Question 3: Can ensign behavior be verified from JSONL alone?

**DONE** — Yes, ensign communication patterns are fully distinguishable in JSONL.

**Concrete example** (from session `0dbb2460`, agent `a33164d6dd8173783` — ensign-071-pr-merge-detection-ideation):
- 11 direct text blocks (type `text` in assistant messages) — visible to captain
- 2 `SendMessage` calls:
  - `SendMessage(to="team-lead", summary="Done: 071 ideation complete")` — completion signal
  - `SendMessage(to="team-lead", ...)` — shutdown response
- 19 other tool calls (Read, Bash, Edit, Glob, ToolSearch)

**Verification approach for 099 tests:**
- Parse `subagents/agent-<id>.jsonl` with existing `LogParser` class
- Check if `tool_calls()` contains `SendMessage` with `to="team-lead"` — this is agent-to-FO communication
- Check if `fo_texts()` returns direct text blocks — this is agent-to-captain visible output
- For the 099 guardrail: verify that during captain-interactive stages, the ensign uses direct text (text blocks) and NOT SendMessage for captain-facing content

### Question 4: Can the captain switch to talking to an ensign?

**DONE** — No, this is not possible in current Claude Code architecture.

**Investigation:**
- Searched Claude Code source (`cli.js` v2.1.96) for: agent targeting, teammate routing, @mention handling, agent selection UI, chat switching — found nothing
- Examined real session logs: all `type: "user"` messages in the FO log come from the captain and are addressed to the main agent only
- There is no slash command, UI control, or protocol mechanism for the user to address a specific team member

**Architecture:**
- User input always goes to the main agent (the FO/captain-level session)
- The FO routes to agents via `SendMessage(to="agent-name")`
- Agents communicate back via `SendMessage(to="team-lead")` or direct text output
- Direct text output from any agent is visible to the captain but cannot be replied to directly

**Implication for testing:** To test captain-to-ensign interaction (the 099 use case), the test must send a message to the FO and rely on the FO routing it to the appropriate agent. There is no way to bypass the FO and talk directly to an ensign.

### Question 5: Minimum harness (PTY works)

**DONE** — Built `scripts/test_lib_interactive.py` with `InteractiveSession` class (~110 lines).

**Deliverables:**
- `scripts/test_lib_interactive.py` — the harness class
- `tests/test_interactive_poc.py` — proof-of-concept test (both turns pass)

**InteractiveSession API:**
- `start(ready_timeout)` — forks PTY, launches claude, waits for `❯` prompt
- `send(message)` — types message character by character and presses Enter
- `wait_for(pattern, timeout, min_matches)` — waits for regex pattern in ANSI-stripped post-send output
- `stop()` — sends `/exit`, then SIGTERM, then waitpid
- `get_clean_output()` — returns full ANSI-stripped session output
- `get_subagent_logs(project_dir)` — finds per-agent JSONL logs under `~/.claude/projects/`

**Budget cap:** `max_budget_usd` parameter passed to claude CLI via `--max-budget-usd`

**POC test result:**
```
Turn 1 (ALPHA_MARKER): PASS
Turn 2 (BETA_MARKER): PASS
Multi-turn: PASS
```

### Implementation finishing work

**Key sequence support** — **DONE**
- Added `send_key(key_name)` method to `InteractiveSession`
- Supports: arrow keys, Shift+arrow (Shift+Up `\x1b[1;2A`, Shift+Down `\x1b[1;2B`), Enter, Escape, Tab, Backspace, Ctrl+C/D/Z
- Key map defined in `_KEY_SEQUENCES` dict for easy extension
- Validates key name and session state before sending

**Subagent log discovery** — **DONE**
- Rewrote `get_subagent_logs()` to return `dict[str, Path]` (agent ID → log path) instead of flat list
- Selects the most recently modified session directory with subagent logs (by `st_mtime`)
- Agent metadata available via `.meta.json` sidecar files

**ANSI stripping** — **DONE**
- Extended `_strip_ansi()` to handle: OSC sequences with ST terminator (`\x1b\\`), keypad/charset mode escapes, two-byte escape sequences, DEC single-char escapes (`\x1b7`, `\x1b8`, etc.), bare BEL, carriage returns
- Added inline comments for each regex branch

**POC test update** — **DONE**
- Split into offline tests (no claude needed) and live tests (`--live` flag)
- Offline tests cover: ANSI stripping, key sequence definitions, `send_key` validation, empty log discovery
- Live tests demonstrate: multi-turn, Shift+Down key send, subagent log collection

### Completion checklist

1. Answer spike question 1: PTY driving feasibility — **DONE**
2. Answer spike question 2: JSONL log locations in team sessions — **DONE**
3. Answer spike question 3: Ensign behavior verification from logs — **DONE**
4. Answer spike question 4: Captain-to-ensign switching — **DONE** (not possible)
5. Build proof of concept (if feasible) — **DONE** (`test_lib_interactive.py` + passing POC test)
6. Commit findings and any code on the worktree branch — **DONE**
7. Add key sequence support (send_key method with Shift+Up/Down) — **DONE**
8. Robust subagent log discovery — **DONE**
9. ANSI stripping improvements — **DONE**
10. Update POC test with team switching demonstration — **DONE**
11. Commit all changes — **DONE**
