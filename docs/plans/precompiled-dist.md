---
title: Dist building and release process
status: backlog
source: refit testflight
started:
completed:
verdict:
score:
worktree:
---

Commission currently LLM-generates all artifacts (status script, first-officer agent) from template descriptions on every run. This is slow, non-deterministic, and untested. A dist-based release process would ship pre-built, tested artifacts and use them during commission instead of regenerating.

## Two channels

| Channel | Dist artifacts | Commission behavior | Audience |
|---------|---------------|-------------------|----------|
| **release** | Pre-built in `dist/` | Copy and patch dist artifacts with pipeline-specific values | Users |
| **dev** | No dist | LLM-generates from template descriptions | Contributors |

The commission skill checks: if `dist/` exists with matching artifacts, use them (fast, deterministic). If not, fall back to LLM generation (slow, variable).

## Dist directory

```
dist/
  status              # Pre-built, tested status script template
  first-officer.md    # Pre-built first-officer skeleton with {variables}
```

The status script needs pipeline-specific stage names patched in. The first-officer needs all `{variables}` filled. Both are copy-and-patch, not LLM-generate.

## Marketplace

The Spacedock repo is its own marketplace. Needs a `.claude-plugin/marketplace.json`:

```json
{
  "name": "spacedock",
  "description": "Build and launch PTP pipelines for Claude Code",
  "owner": { "name": "CL Kao" },
  "plugins": [{
    "name": "spacedock",
    "description": "Build and launch PTP pipelines",
    "version": "0.2.0",
    "source": "./"
  }]
}
```

## Release skill

A `/spacedock release` skill that:

1. Run test harness (`bash v0/test-commission.sh`) — must pass
2. Build dist: materialize templates into `dist/`, verify they match test output
3. Bump version in `plugin.json` and `marketplace.json`
4. Commit and tag (`git tag v0.2.0`)
5. Show post-release checklist

## Considerations

- Dist artifacts need to be portable (bash 3.2+ for macOS default)
- The self-describing template header remains the source of truth; dist is the tested materialization
- Fallback to LLM generation when no dist matches (user-customized pipelines)
- Version in `plugin.json` and `marketplace.json` must stay in sync
- The test harness validates both the template (dev channel) and the dist output (release channel)
