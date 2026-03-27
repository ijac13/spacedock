---
id: 063
title: Make agents workflow-agnostic — one agent definition serves multiple workflows
status: done
source: CL
started: 2026-03-27T22:35:00Z
completed: 2026-03-27T23:15:00Z
verdict: PASSED
score: 0.85
worktree:
issue: "#3"
pr: "#6"
---

Currently the commission generates per-workflow agent files (first-officer, ensign, pr-lieutenant) with hardcoded workflow-specific values baked in via sed substitution (`__DIR__`, `__MISSION__`, `__CAPTAIN__`, `__ENTITY_LABEL__`, etc.). This means:

1. A project with two workflows gets naming collisions in `.claude/agents/` (both generate `ensign.md`)
2. Each refit regenerates all agents even though most content is identical
3. The agents carry workflow knowledge they could derive at runtime from the README

## Problem statement

**Concrete collision scenario:** A project has two workflows — `docs/plans/` (the Spacedock self-hosted workflow) and `docs/onboarding/` (a hypothetical employee onboarding workflow). Both call `commission`, which generates `ensign.md`, `first-officer.md`, and `pr-lieutenant.md` into `.claude/agents/`. The second commission overwrites the first's agents. Now `claude --agent first-officer` manages `docs/onboarding/` but the `docs/plans/` workflow is orphaned — its agents point to the wrong directory, wrong mission, wrong entity labels.

Even without collision, the generated agents are 95% identical across workflows. The ensign template has only 3 substitution variables (`__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__`), and the ensign already reads everything it needs from the dispatch prompt — the substituted values are decorative headings. The first-officer has 10 `__DIR__` references plus cosmetic variables, but `__DIR__` is the only variable that affects behavior.

## Current state

The ensign is already nearly workflow-agnostic — it reads everything from the dispatch prompt and has no `__DIR__`. The first-officer has ~10 hardcoded `__DIR__` references and 2 `__PROJECT_NAME__` references. The pr-lieutenant has 1 `__DIR__` reference in its hooks.

### Variable audit (verified counts from templates)

| Variable | Count in FO | Count in ensign | Count in pr-lt | Truly needed at commission time? | Alternative |
|----------|-------------|-----------------|----------------|--------------------------------|-------------|
| `__DIR__` | 5 | 0 | 1 | **FO: yes** (behavioral — tells FO which directory to manage). **pr-lt: yes** (hooks scan entity files in specific dir) | Pass at invocation via `initialPrompt`, or read from a config file |
| `__MISSION__` | 3 | 1 | 1 | No — decorative heading/description | Read from README H1, or use generic heading |
| `__CAPTAIN__` | 9 | 0 | 1 | No — should be literal "the captain" (see #062) | Literal string |
| `__ENTITY_LABEL__` | 7 | 1 | 1 | No — cosmetic, and FO already reads it from README at startup | Read from README frontmatter `entity-label` |
| `__ENTITY_LABEL_PLURAL__` | 1 | 0 | 0 | No — cosmetic | Derive from `entity-label` |
| `__FIRST_STAGE__` / `__LAST_STAGE__` | 1 each | 0 | 0 | No — FO reads stage ordering from README | Read from README frontmatter stages block |
| `__PROJECT_NAME__` | 2 | 0 | 0 | No — used for team naming only | Derive from `git rev-parse --show-toplevel` at runtime |
| `__DIR_BASENAME__` | 2 | 0 | 0 | No — used for team naming only | Derive from workflow directory at runtime |
| `__SPACEDOCK_VERSION__` | 1 | 1 | 1 | No — metadata stamp | Embed in a comment or omit from agent file |

**Key insight:** Only `__DIR__` affects agent behavior (5 uses in FO, 1 in pr-lieutenant). Every other variable is either decorative (headings, descriptions) or derivable at runtime from the README.

## Staff Engineer A — Plugin/SDK Architecture Analysis

### Can Claude Code plugins ship agent definitions?

**Finding: No.** The current plugin schema (`plugin.json`) supports only `name`, `version`, `description`, `author`, `repository`, `license`, and `keywords`. There is no `agents` field or agent discovery mechanism. The `marketplace.json` format lists plugins with `source` paths, but only skills (in `skills/*/SKILL.md`) are loadable from plugin directories. Agent files must live at `.claude/agents/*.md` in the project root to be resolvable by `claude --agent <name>` or `Agent(subagent_type="<name>")`.

**Implication:** Agents cannot be distributed via the plugin today. They must be generated into the target project's `.claude/agents/` directory. If Anthropic adds plugin-shipped agents in the future, the migration path from generated-to-shipped would be straightforward — but we can't depend on it.

### Static vs parameterized agents — patterns from other systems

**VS Code extensions** use a "static definition + runtime configuration" pattern. An extension contributes a task provider (static code), but the task's `cwd`, `args`, and `env` are resolved at runtime from `tasks.json` or workspace settings. The extension itself doesn't get customized per-workspace — it reads workspace configuration.

**Terraform providers** ship as static binaries. Per-project behavior comes from `.tf` configuration files, not from customizing the provider binary. A provider that needs to know which region to manage reads it from `provider "aws" { region = "us-east-1" }`, not from a compiled-in constant.

**Recommendation (from Engineer A):** The "static agent + runtime config" pattern is well-established. The agent file should be a static behavioral contract (like a VS Code extension or Terraform provider), and the workflow-specific context (directory path, mission, labels) should be runtime configuration, not compile-time substitution. The ensign already follows this pattern — it reads everything from its dispatch prompt. The first-officer should too.

### One definition, multiple instances

The key question is: how does a static first-officer know which workflow to manage when there are multiple?

**Engineer A's analysis:** The `initialPrompt` field in agent frontmatter is the natural injection point. Currently it's `"Report workflow status."` — a fixed string. If it instead said `"Manage the workflow at docs/plans/."`, the FO would have its directory at startup without needing it baked into the agent body. But `initialPrompt` is set at generation time, so two workflows would still collide on the same `first-officer.md` filename.

**Three resolution patterns:**

1. **Named agent files** — `first-officer-plans.md`, `first-officer-onboarding.md`. Each has a different `initialPrompt`. Simple but still generates per-workflow files.
2. **Single static agent + CLI argument** — `claude --agent first-officer -- docs/plans/`. The agent reads its workflow directory from the invocation. Zero per-workflow generation. But this requires the `--agent` flag to support passing arguments, which it doesn't today.
3. **Single static agent + discovery** — The FO scans for workflow directories at startup (look for `*/README.md` files with `commissioned-by: spacedock@*` frontmatter). If one found, use it. If multiple, ask the captain. Zero per-workflow generation, zero CLI changes needed.

## Staff Engineer B — Multi-Workflow Orchestration Analysis

### How should a single FO manage workflow directory discovery?

**Engineer B's analysis using Kubernetes operator analogy:** A Kubernetes controller watches for CRDs (Custom Resource Definitions) across the cluster. It doesn't need configuration per-CRD — it discovers them at runtime. The controller's behavior is defined once; instance-specific data comes from the CRD objects themselves.

Similarly, a Spacedock FO should discover workflows at runtime, not have them baked in. The "CRD" equivalent is the workflow README with its `commissioned-by: spacedock@*` frontmatter.

**Discovery algorithm (minimal):**

```
1. Find all README.md files in the project that have `commissioned-by: spacedock@` in YAML frontmatter
2. If exactly one: use it (single-workflow case — identical to today's behavior)
3. If multiple: list them and ask the captain which to manage
4. If zero: report "no Spacedock workflow found"
```

This handles the single-workflow case transparently and the multi-workflow case gracefully.

**Temporal workflow analogy:** Temporal uses "task queues" — a single worker definition can listen on different queues. The worker code is identical; the queue name is a runtime parameter. In Spacedock terms, the workflow directory is the "task queue" — the FO code is identical, and the directory is a runtime parameter.

### Minimal config surface

**Engineer B's recommendation:** Zero config files. The workflow directory is the only per-instance parameter, and it can be discovered or passed at invocation. Adding a config file (e.g., `.spacedock.yml`) creates another artifact to maintain, another thing that can go stale, and another thing the commission/refit skills must manage. The README already serves as the configuration — it has all the schema, stages, and metadata.

**If the `initialPrompt` approach is used:** The initialPrompt becomes the single config surface — `"Manage the workflow at {dir}."` One line, embedded in the agent file's frontmatter, readable by the FO at startup. This is analogous to Kubernetes controller's `--namespace` flag.

### Multi-agent frameworks comparison

| Framework | Agent definition | Per-instance config | Discovery |
|-----------|-----------------|--------------------:|-----------|
| K8s operators | Static controller binary | CRD objects + controller flags | Watches API server |
| Temporal | Static worker code | Task queue name (runtime) | Worker polls task queue |
| VS Code extensions | Static extension package | workspace settings.json | Reads workspace config |
| Terraform providers | Static provider binary | `.tf` files | Reads current directory |
| **Current Spacedock** | **Generated per-workflow** | **Baked into agent file** | **None — hardcoded** |
| **Proposed Spacedock** | **Static agent definition** | **Workflow directory (runtime)** | **Scan for READMEs or use initialPrompt** |

## Proposed approach

### Design: eliminate all commission-time substitutions except `__DIR__`

**Phase 1 — Make ensign and pr-lieutenant fully static** (low risk, high payoff):

The ensign already reads everything from its dispatch prompt. The remaining `__MISSION__`, `__ENTITY_LABEL__`, and `__SPACEDOCK_VERSION__` substitutions are decorative. Replace them with generic text:

- Ensign heading: `# Ensign` (drop mission-specific heading)
- Ensign description: `Executes workflow stage work` (drop mission name)
- `__ENTITY_LABEL__` → `entity` (a valid generic term — the FO already sends the real label in the dispatch prompt)
- `__SPACEDOCK_VERSION__` → remove from agent frontmatter (version stamp belongs on the README and status script, not the agent)

Same treatment for pr-lieutenant, plus replace `__DIR__` (1 occurrence in hooks) with a runtime reference: the pr-lieutenant's hooks already get called by the FO, which knows the directory. The hook instructions can reference `the workflow directory` generically, and the FO passes the directory path when invoking the hook.

After this change: **ensign.md and pr-lieutenant.md become identical across all workflows.** Two workflows in the same project share the same agent files with zero conflicts.

**Phase 2 — Reduce first-officer to one variable: `__DIR__`:**

Replace all cosmetic variables in the FO template:
- `__MISSION__` (3 uses) → read from README H1 at startup, use in headings/descriptions
- `__CAPTAIN__` (9 uses) → literal `the captain` (aligns with #062)
- `__ENTITY_LABEL__` (7 uses) / `__ENTITY_LABEL_PLURAL__` (1 use) → read from README frontmatter `entity-label` / `entity-label-plural` at startup
- `__FIRST_STAGE__` / `__LAST_STAGE__` (1 each) → read from README frontmatter stages block at startup
- `__PROJECT_NAME__` / `__DIR_BASENAME__` (2 each) → derive from `git rev-parse --show-toplevel` and workflow directory path at runtime
- `__SPACEDOCK_VERSION__` (1 use) → remove from agent frontmatter

This leaves `__DIR__` (5 uses) as the sole substitution variable. The FO template becomes a near-static document with one variable.

**Phase 3 — Eliminate `__DIR__` via initialPrompt or discovery:**

Two options (trade-offs analyzed below):

**Option A — initialPrompt injection:** Keep one sed substitution: `__DIR__` in both the agent body and `initialPrompt`. The commission still generates per-workflow FO files, but they're nearly identical — only the directory path differs. Multi-workflow projects get `first-officer-plans.md` and `first-officer-onboarding.md` (named by directory basename).

**Option B — Runtime discovery:** Make `__DIR__` a runtime parameter. The FO's startup procedure changes:

1. Check if a workflow directory was passed in the initial prompt
2. If not, scan for `README.md` files with `commissioned-by: spacedock@*` frontmatter
3. If exactly one: use it. If multiple: ask the captain. If zero: report no workflow found.

The FO template uses a placeholder like `{workflow_dir}` (a runtime variable, not a `__VAR__` template marker) that gets resolved at startup.

### Trade-off analysis

| Criterion | Option A (initialPrompt) | Option B (discovery) |
|-----------|-------------------------|---------------------|
| Agent files generated | 1 per workflow (FO only) + 2 shared (ensign, pr-lt) | 0 per workflow + 3 shared |
| Naming collisions | Solved — FO files get unique names | Solved — no per-workflow files |
| Commission changes | Minimal — still generates FO but with 1 variable | Larger — stops generating agents entirely |
| Refit changes | Only regenerates FO | Only updates shared agents (simpler) |
| Single-workflow UX | Identical to today: `claude --agent first-officer` | Identical to today: `claude --agent first-officer` (auto-discovers the one workflow) |
| Multi-workflow UX | `claude --agent first-officer-plans` | `claude --agent first-officer` then interactive prompt |
| Complexity | Low — minimal change from current approach | Medium — new discovery logic, but eliminates all generation |
| Future plugin-shipped agents | Ready — shared agents are static, FO still generated | Fully ready — all agents are static |

**Recommendation:** Start with Option A for the FO (minimal risk, solves the collision problem, preserves simplicity). Implement Phases 1-2 immediately: make ensign and pr-lieutenant fully static, reduce FO to one variable. Phase 3 Option B (discovery) can be a follow-up if/when the plugin system supports agent distribution.

### Impact on commission and refit

**Commission changes:**
- Phase 1-2: Stop running sed for ensign and pr-lieutenant. Instead, copy them verbatim from `templates/` to `.claude/agents/` (or skip if they already exist and are identical). FO generation uses only `__DIR__` substitution.
- Phase 3A: FO gets a workflow-specific name (e.g., `first-officer-{dir_basename}.md`).
- Phase 3B: FO copied verbatim too. Commission adds an `initialPrompt` or the FO discovers the workflow.

**Refit changes:**
- Phase 1-2: Ensign and pr-lieutenant refit becomes "copy template if changed." No extraction of workflow-specific values needed. FO refit only extracts `__DIR__`.
- Phase 3: All agents are copy-if-changed. Refit simplifies dramatically.

## Acceptance criteria (updated)

1. Design document covers: how the FO learns which workflow directory to manage at runtime, how agents are distributed (plugin-shipped vs generated), and what changes in commission/refit.
2. The design handles the multi-workflow case: two workflows in the same project both work without agent file collisions.
3. The design preserves the current behavioral contract — agents behave identically to today for single-workflow projects.
4. Trade-offs between static agents (simpler, plugin-shippable) vs minimal-config agents (one sed variable) are analyzed.
5. Ideation consults two staff software engineers on the design pattern for workflow-agnostic agent dispatch.
6. Implementation is phased: ensign/pr-lieutenant first (low risk), then FO reduction, then full discovery (optional).
7. The FO's startup procedure is updated to read mission, entity labels, stage names, and captain address from the README at runtime instead of from baked-in template variables.

## Stage Report: ideation

- [x] Problem statement refined — multi-workflow collision scenario documented with concrete example
  Two-workflow scenario (docs/plans/ + docs/onboarding/) showing how second commission overwrites first's agents, orphaning the first workflow.
- [x] Staff Engineer A consultation — plugin/SDK agent distribution research, static vs parameterized pattern analysis
  Confirmed plugin.json has no agents field; agents must live in .claude/agents/. Analyzed VS Code extension and Terraform provider patterns for static-definition-plus-runtime-config. Recommended eliminating compile-time substitution in favor of runtime config.
- [x] Staff Engineer B consultation — multi-workflow orchestration patterns, minimal config surface analysis
  Analyzed Kubernetes operator (controller discovers CRDs) and Temporal (worker polls task queues) patterns. Recommended zero-config-file approach with README-based discovery. Produced comparison table across five frameworks.
- [x] Proposed approach — concrete design for how agents become workflow-agnostic, with trade-offs
  Three-phase plan: (1) make ensign/pr-lieutenant fully static, (2) reduce FO to one variable (__DIR__), (3) eliminate __DIR__ via initialPrompt or discovery. Trade-off table comparing Option A (initialPrompt) vs Option B (discovery) across 8 criteria.
- [x] Acceptance criteria updated based on design findings
  Added criteria 6 (phased implementation) and 7 (FO reads config from README at runtime). Original 5 criteria preserved.

### Summary

Completed ideation for workflow-agnostic agents. The core insight is that only `__DIR__` (5 uses in FO, 1 in pr-lieutenant) affects agent behavior — all other template variables are decorative or derivable from the README at runtime. The proposed three-phase approach starts with the lowest-risk change (making ensign and pr-lieutenant fully static) and progressively reduces the first-officer's dependency on commission-time substitution. Staff engineer consultations confirmed that the "static definition + runtime config" pattern is well-established across VS Code, Terraform, Kubernetes, and Temporal, and that Claude Code's plugin system does not currently support shipping agent definitions.

## Stage Report: implementation

- [x] Ensign template is fully static — zero `__VAR__` markers, generic headings
  Removed `__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__` from `templates/ensign.md`. Commit: 9e01c05.
- [x] PR-lieutenant template is fully static — zero `__VAR__` markers, hooks use generic directory references
  Removed `__MISSION__`, `__ENTITY_LABEL__`, `__SPACEDOCK_VERSION__`, `__DIR__`, `__CAPTAIN__` from `templates/pr-lieutenant.md`. Hook references "the workflow directory" generically. Commit: 9e01c05.
- [x] First-officer template is fully static — zero `__VAR__` markers, all runtime-derived
  All 10 distinct `__VAR__` types replaced: `__MISSION__`, `__CAPTAIN__`, `__ENTITY_LABEL__`, `__ENTITY_LABEL_PLURAL__`, `__FIRST_STAGE__`, `__LAST_STAGE__`, `__PROJECT_NAME__`, `__DIR_BASENAME__`, `__DIR__`, `__SPACEDOCK_VERSION__`. FO reads all values from README at runtime. Commit: 2797ad5.
- [x] FO has workflow discovery at startup — searches for `^commissioned-by` README files
  Discovery is startup step 1: `grep -rl '^commissioned-by: spacedock@' --include='README.md' .`. Single result auto-selects; multiple prompts captain. Verified against `docs/plans/` workflow. Commit: 2797ad5.
- [x] Commission skill updated — copies static agents instead of sed substitution
  Sections 2d/2e/2f changed from sed to `cp`. Removed `{project_name}` and `{dir_basename}` from design phase derivation. Commit: 080ba55.
- [x] Refit skill updated — copy-if-changed for all agents
  Strategy changed from "Regenerate" to "Copy if changed" for all agents. Agent staleness detected by content comparison instead of version stamps. Degraded mode simplified. Commit: 56e4762.
- [x] All changes committed with descriptive messages
  Four incremental commits: templates (2), commission skill (1), refit skill (1).

### Summary

Implemented workflow-agnostic agents using Option B (runtime discovery). All three agent templates (ensign, pr-lieutenant, first-officer) are now fully static with zero `__VAR__` markers. The first officer discovers its workflow directory at startup by grepping for README.md files with `commissioned-by: spacedock@` frontmatter, then reads mission, entity labels, stage names, and all other workflow-specific values from the README. The commission skill now copies templates verbatim instead of running sed substitution. The refit skill uses content comparison instead of version stamps to detect agent staleness.
