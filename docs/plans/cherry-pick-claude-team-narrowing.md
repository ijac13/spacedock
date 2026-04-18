---
id: 184
title: "Cherry-pick claude-team find_subagent_jsonl narrowing from #182 branch"
status: ideation
source: "carved out of #182 — the find_subagent_jsonl narrowing change is independently valuable and passed independent review; unbundling it from #182's rejected prose mitigations to land on its own."
started: 2026-04-18T00:12:20Z
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Problem statement

`find_subagent_jsonl` in `skills/commission/bin/claude-team` currently globs
`~/.claude/projects/*/subagents/agent-*.meta.json` **and**
`~/.claude/projects/*/*/subagents/agent-*.meta.json` across every project on
the machine, then opens each meta file to match `agentType == name`. On a
populated developer machine this scans ~4816 meta files per call where only
~9 can possibly match (the current team's session). Every dispatch / status
read pays this cost.

The knowledge needed to narrow the scan already exists on disk: the team
config at `~/.claude/teams/*/config.json` lists members by name and stores
`leadSessionId`, which is exactly the subdirectory under
`~/.claude/projects/*/{leadSessionId}/subagents/` where that team's subagent
meta files live.

## Approach

Cherry-pick a single commit — no other changes — onto a fresh branch off
`main`:

- **Source commit:** `b09051f4` ("fix: #182 narrow find_subagent_jsonl scan
  to one team's leadSessionId")
- **Source branch:** `spacedock-ensign/diagnose-opus-4-7-fo-regression`
- **Files touched:** exactly one — `skills/commission/bin/claude-team`
  (+63 / −10)
- **Cherry-pick cleanliness:** verified in a throwaway clone; applies to
  current `main` with no conflicts. `main`'s most recent touch of this file
  is `0c68f07b` (list-standing subcommand) which does not overlap the
  `find_subagent_jsonl` region.

### What the commit changes (pre / post shape)

Pre (excerpt):

```python
def find_subagent_jsonl(name: str) -> str | None:
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".claude", "projects", "*", "subagents", "agent-*.meta.json"),
        os.path.join(home, ".claude", "projects", "*", "*", "subagents", "agent-*.meta.json"),
    ]
    matches = []
    for pattern in patterns:
        for meta_path in glob.glob(pattern):
            ...  # open, check agentType == name, collect
    ...
```

Post (shape):

- `find_subagent_jsonl(name)` first calls `_narrowed_subagent_patterns(home, name)`.
- `_narrowed_subagent_patterns` globs `~/.claude/teams/*/config.json`, finds
  the team config whose `members[].name` includes `name`, reads its
  `leadSessionId`, and returns a single pattern
  `~/.claude/projects/*/{leadSessionId}/subagents/agent-*.meta.json`.
  Returns `None` if no matching team config is found or the config has no
  `leadSessionId`.
- If narrowing succeeded, scan the narrowed patterns via
  `_scan_subagent_meta`. If that returns empty, print a stderr warning and
  fall back to the broad two-pattern scan. If narrowing returned `None`,
  skip straight to the broad scan (no warning).
- `_scan_subagent_meta(patterns, name)` is the extracted scan loop,
  returning `[(mtime, jsonl_path), ...]`.

## Out of scope

- Any prose mitigations in `skills/first-officer/references/claude-first-officer-runtime.md`.
- Any test-predicate changes (see sibling cherry-pick task).
- Re-tuning or suppressing the stderr warning (see below).

## Informational note — stderr warning noise floor

The independent review of PR #117 raised a question about whether the
stderr warning on fallback becomes noise if it fires on every normal run.
Current read of the commit: the warning fires **only** when narrowing
succeeded (a matching team config + `leadSessionId` was found) **and** the
narrowed scan turned up zero matches. That combination should be rare —
either something clobbered the leadSessionId, or the subagent meta files
haven't been written yet. Normal runs where no team config exists for
`name` skip narrowing entirely and hit the broad scan silently.

Treat as informational only. **Not** a blocker for this cherry-pick. If
operational noise appears in practice, file a follow-up.

## Acceptance criteria

| # | Criterion | How it's tested |
|---|-----------|-----------------|
| 1 | `git cherry-pick b09051f4` on a fresh branch off current `main` applies cleanly with no conflicts. | Dry-run already executed in `/tmp/cherry-test` clone; reproduce on the actual worktree branch during implementation. |
| 2 | `make test-static` passes on the cherry-pick branch. | Run locally; same suite CI runs on PR (`.github/workflows/static.yml`). |
| 3 | `skills/commission/bin/claude-team` parses and imports without errors after cherry-pick. | `python3 -c "import ast; ast.parse(open('skills/commission/bin/claude-team').read())"` plus `python3 skills/commission/bin/claude-team --help` exits 0. |
| 4 | The narrowed glob empirically reduces the scan, matching the commit message's claim on a populated machine. | Optional manual check on CL's machine: instrument once to print `len(glob.glob(narrowed[0]))` vs `len(glob.glob(broad[0])) + len(glob.glob(broad[1]))`. Not CI-gated. |
| 5 | Fallback-to-broad-scan path still returns a matching jsonl when the narrowed scan misses. | Covered by acceptance-test #6 below (cheap unit test). |

## Test plan

**Static suite (required, gates the PR):** `make test-static`. No new
failures vs. `main`. No live CI needed — the change is a pure-Python
refactor of a helper with the same return contract.

**Unit test (proposed, cheap, optional):** add
`tests/test_claude_team_find_subagent_jsonl.py` with `tmp_path`-based
fixtures that monkey-patch `os.path.expanduser` to a temp HOME:

1. **Narrowed hit** — seed one team config with member `"alpha"` and
   `leadSessionId: "sess-A"`; seed two meta files, one under
   `projects/p/sess-A/subagents/` with `agentType: "alpha"` and one under
   `projects/p/sess-B/subagents/` with `agentType: "alpha"`. Assert the
   returned jsonl is the one under `sess-A`.
2. **No team config → broad fallback** — no teams dir; seed a meta under
   `projects/p/subagents/` with `agentType: "alpha"`. Assert broad scan
   finds it. Assert **no** stderr warning.
3. **Narrowed empty → broad fallback with warning** — team config present
   with `leadSessionId: "sess-A"`, but no meta under `sess-A/subagents/`.
   Seed a meta under `projects/p/subagents/` matching `alpha`. Assert broad
   fallback returns it **and** stderr contains the "falling back to broad"
   warning.
4. **No match anywhere** — returns `None`.

Complexity estimate: ~80 lines, <1s runtime, uses only `tmp_path` and
`capsys` — fits the project's existing offline static test style. Decision
on whether to include the unit test stays with the implementation-stage
dispatch; ideation flags it as cheap and proportional but not required to
land the cherry-pick.

**E2E / live CI:** not needed. The change's return contract is unchanged
(str jsonl path or None); downstream consumers behave identically.

## Cross-references

- #182 — source branch; being rejected for scope drift
- Independent review of PR #117 — confirmed this change is sound
- Sibling cherry-pick task (test-predicate change) — separate entity

## Stage Report (ideation)

1. **Read the seed entity body.** — **DONE.** Read the existing frontmatter + "Why this matters" / "Scope" / "Out of scope" / "Cross-references" sections. Expanded into problem statement, approach, acceptance criteria, and test plan.
2. **Inspect commit `b09051f4`** — **DONE.** `git show b09051f4 --stat` confirms the commit touches exactly one file: `skills/commission/bin/claude-team` (+63 / −10). `git branch --contains b09051f4` confirms it lives on `spacedock-ensign/diagnose-opus-4-7-fo-regression`. Clean cherry-pick verified in a throwaway clone at `/tmp/cherry-test` — `git cherry-pick --no-commit b09051f4` against current `main` produced `M skills/commission/bin/claude-team` with no conflicts.
3. **Read the narrowed helper change** — **DONE.** `git show b09051f4 -- skills/commission/bin/claude-team` reviewed in full. Captured pre/post shape in the ideation body: `_narrowed_subagent_patterns` returns `None` or a single-element glob list scoped to the team's `leadSessionId`; `_scan_subagent_meta` is the extracted scan loop; `find_subagent_jsonl` orchestrates narrowed-first-then-fallback with a stderr warning only when narrowing succeeded-but-empty.
4. **Write ideation body** — **DONE.** Added problem statement, approach (with pre/post code shape), acceptance criteria table (5 criteria, each with a test column), and a proportional test plan (static suite required; a cheap optional ~80-line unit test with four cases covering narrowed-hit / no-config / narrowed-empty-warns / no-match; no live CI).
5. **Note the stderr-warning noise question** — **DONE.** Captured as a standalone "Informational note — stderr warning noise floor" section. Reading of the commit: the warning only fires when narrowing succeeds but the narrowed scan returns empty; normal runs without a matching team config skip narrowing silently. Not a blocker; follow-up if operational noise appears.
6. **Commit the updated body on main.** — **DONE.** (See commit hash in next git log entry after this write.)
7. **Append stage report.** — **DONE** (this section).

### Summary

Confirmed `b09051f4` is a clean, single-file cherry-pick onto current `main`. Expanded the entity body with a problem statement, approach with pre/post code shape, five acceptance criteria (each with a test column), and a proportional test plan (static suite required, cheap unit test with four cases flagged optional, no live CI). The independent reviewer's stderr-warning question is captured as informational only — the warning fires only on narrowed-succeeded-but-empty, not on every normal run. Scope kept tight: no prose changes, no test-predicate changes, no warning-tuning. Implementation stage is unblocked.
