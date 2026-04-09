---
id: 104
title: Workflow discovery — analyze conversation history to recommend workflows
status: ideation
source: CL brainstorm during 057 ideation
started: 2026-04-09T02:08:14Z
completed:
verdict:
score:
worktree:
issue:
pr:
---

What if the user doesn't know they need a workflow? Analyze a user's agent conversation history to discover recurring multi-step patterns and recommend structuring them as spacedock workflows.

## Data sources

- **AgentsView SQLite** (`~/.claude/agentsview/sessions.db`): Normalized database with sessions, messages, tool_calls (with skill names, subagent relationships), and insights. 1018 sessions across 19 projects in CL's data.
- **Raw Claude logs** (`~/.claude/projects/`): Session-level JSONL files.

## Pilot goal

Classify CL's own usage across projects to identify:
1. Recurring multi-step task patterns (same sequence of actions across sessions)
2. Manual orchestration patterns (user directing agent through steps)
3. Ad-hoc state tracking (TODO files, task lists, status checks)
4. Multi-agent coordination patterns (subagent spawning, team usage)
5. Review/approval gates the user imposes

From the classification, determine what approach a "workflow discovery" skill should take and what signals are most reliable.

## Pilot Analysis: Methodology and Findings

### Dataset Overview

- 1018 sessions across 19 projects
- 146 top-level sessions, 872 child sessions (622 subagent, 246 fork, 4 continuation)
- 36,834 messages, 22,018 tool calls
- Average top-level session duration: ~7 hours (heavily skewed; includes long-running orchestrators)

### Pattern Taxonomy

Analysis identified six recurring meta-patterns across the session history:

#### 1. Plan-Execute-Test Orchestration (most common structured pattern)

A structured template where the user provides a plan document and instructs the agent to
execute via subagent-driven development. Characterized by:
- First message references a `.md` plan file (25% of top-level sessions)
- Explicit instruction to use worktrees and subagents
- High subagent spawn count (10-37 per session)
- Low user interaction ratio (user messages <10% of total messages)
- Sessions average 150-300 messages total

This pattern appeared across 4+ projects and accounts for ~14% of top-level sessions
in a nearly identical template form.

#### 2. Context-File E2E Testing Loop

A distinctive repeated workflow for comprehensive testing:
- First message follows template: "Context file: <path> Objective: e2e test every corner case..."
- Bootstrap pattern: creates test plan if file doesn't exist, then executes
- Often re-run multiple times against the same context file (2-5 runs per phase)
- Moderate subagent usage (1-7 per session)
- Found across 3 projects, 15 identified sessions

#### 3. Brainstorm-Plan-Implement Pipeline

Multi-session progression where brainstorming leads to plan writing, then execution:
- Skills activated in sequence: brainstorming -> writing-plans -> subagent-driven-development
- Often spans multiple top-level sessions (not a single session workflow)
- Skill activations: brainstorming (15), writing-plans (13), subagent-driven-development (20)
- User interaction higher during brainstorm phase, drops during execution

#### 4. Investigation-Fix-PR Cycle

Ad-hoc but recurring: investigate an issue, fix it, create a PR:
- First messages contain "check", "look at", "why", "fix" keywords
- Tool sequence: Read/Grep -> Edit -> Bash (test) -> Bash (git)
- Often ends with "create pr" or "open pr" user message
- Lower subagent usage; more interactive, conversational sessions

#### 5. Cross-Session State Continuity

Evidence of users maintaining state across session boundaries:
- ~26% of top-level sessions contain continuity signals (continue, remaining, finish, worktree, branch references)
- Worktree tool used in 11 sessions as isolation mechanism
- Task management tools used in 184 sessions (18% of all)
- Journal tool used in 109 sessions for memory persistence

#### 6. Approval-Gated Progression

User acts as gatekeeper, giving approval between steps:
- AskUserQuestion tool called 145 times across projects
- One project had 93 approval-gate interactions across 12 sessions
- Short user messages ("approved", "pass", "continue") advance the workflow
- Suggests explicit review/approval gates in multi-step processes

### Session Structure Analysis

**Session length distribution (all sessions):**
- 37.4% have 1-5 messages (mostly subagent workers)
- 22.9% have 21-50 messages (moderate complexity)
- 13.2% have 51-100 messages (significant work sessions)
- 8% have 100+ messages (heavy orchestration sessions)

**Top-level session user interaction:**
- 52.7% have 1-3 user messages (fire-and-forget orchestration)
- 17.8% have 6-10 user messages (moderate steering)
- 15.1% have 11-20 user messages (heavy interaction)
- 8.2% have 20+ user messages (conversational/collaborative)

**Multi-agent depth:**
- 146 root sessions, 621 depth-1 children, 251 depth-2 children
- Confirms 2-level nesting is common in orchestrated sessions

**Subagent-to-toplevel ratio by project (active projects only):**
- Range: 3.3x to 20x subagents per top-level session
- Projects with ratio >8x show heavy automated orchestration
- Projects with ratio <5x show more interactive usage

### Tool Usage Patterns

**Top tools:** Bash (39.6%), Read (30.1%), Edit (7.3%), Grep (4.9%), Task management (7.7% combined), Write (2.5%)

**Key tool transitions (most common sequential pairs):**
- Bash -> Read (1358): command execution followed by file inspection
- Read -> Edit (572): read-then-modify pattern
- Bash -> TaskUpdate (227): test/build followed by progress tracking
- TaskCreate -> TaskUpdate (75): plan then execute pattern

**Top-level vs subagent tool profile differs:**
- Top-level: heavier on TaskUpdate/Task/TaskCreate, Skill, AskUserQuestion, Agent
- Subagent: heavier on Bash, Read, Edit, Grep, Glob, Write (execution-oriented)
- This confirms orchestrator-worker separation

### Reliable Discovery Signals

Based on this analysis, a workflow discovery skill should key on:

1. **Repeated first-message templates** — Same or near-identical first messages across sessions indicate a codified workflow the user runs manually. Fuzzy-match first_messages within a project; clusters of >2 similar starts are strong signals.

2. **High subagent-to-interaction ratio** — Sessions with many subagent spawns but few user messages indicate automated orchestration that could be formalized.

3. **Plan-file references** — First messages referencing `.md` files suggest the user is already structuring work as plans. These are prime candidates for workflow formalization.

4. **Recurring tool sequences** — Stable tool-call patterns (e.g., Read->Edit->Bash->TaskUpdate) repeated across sessions suggest codifiable workflows.

5. **Cross-session continuity signals** — References to previous work, worktrees, or task state suggest multi-session workflows that could benefit from persistent state management.

6. **Approval gates** — Frequent AskUserQuestion calls in structured sessions indicate review gates that could be formalized as workflow stages.

7. **Context-file bootstrapping** — The "Context file: ... Bootstrap if doesn't exist" pattern is essentially a declarative workflow definition the user invented organically.

### Proposed Approach for Workflow Discovery Skill

**Design decisions:**
- **Recommend specific workflows.** Discovery should map detected patterns to concrete workflow recommendations (e.g., "plan-execute-test pipeline", "iterative E2E testing loop") rather than just describing raw patterns. The recommendation includes suggested stages, interaction mode, and a direct path to `/commission`.
- **Minimum cluster size: 3.** A pattern must appear in at least 3 sessions to trigger a recommendation (avoids noise from one-off similarities).
- **Subagent goals, not subagent trees.** Read subagent `first_message` to understand what tasks were delegated — sufficient to infer workflow stages without expensive deep tree analysis.
- **On-demand, project-scoped first.** Invoked via `/discover-workflows` (current project) or `/discover-workflows --all` (cross-project). Not proactive on session start.

**How it would work:**

1. **Scan phase**: Query AgentsView database for sessions in the target project. Cluster first_messages by prefix similarity (first 60 chars as initial heuristic, with fuzzy matching for refinement). Filter clusters with count >= 3. Also detect: framework-based dispatch (structured XML in subagent first_messages), skill chains (Skill tool invocations), and approval gates (AskUserQuestion patterns).

2. **Classify phase**: For each cluster, determine:
   - **Orchestration era**: framework-based, skill-based, or ad-hoc (see "Three orchestration eras" below)
   - **Interaction mode**: fire-and-forget delegation (<2% user msgs), gated delegation (2-10%), or co-creation (>10%)
   - **Confidence score**: based on cluster size, structural consistency, and user effort
   - **Subagent goals**: read subagent `first_message` content to understand what work was delegated

3. **Recommend phase**: For each high-confidence pattern, recommend a specific workflow:
   - **Workflow name** — a descriptive name for the pattern (e.g., "Plan-Execute-Test Pipeline", "Iterative E2E Testing")
   - **Stages** — concrete stage list derived from subagent goals and skill chain order
   - **Interaction mode** — delegation, gated delegation, or co-creation
   - **Approval gates** — where they should fall (derived from observed AskUserQuestion patterns)
   - **Evidence** — how many times used, across which projects, confidence score
   - **Action** — "Run `/commission` to create this workflow" with the recommendation as seed context

4. **Handoff to commission**: Discovery output feeds directly into `/commission` as structured input. The recommended workflow name, stages, and interaction mode become the starting point for commissioning — the user refines from there rather than starting from scratch.

**Minimum viable implementation:**
- Query first_messages for a project, cluster by prefix(60), filter count >= 3
- For each cluster: compute subagent ratio, user interaction ratio, detect skill names
- Read subagent first_messages for top sessions in each cluster to infer stage goals
- Present top-3 pattern candidates ranked by frequency x confidence
- For each, show: frequency, interaction mode, inferred stages, suggested action

## Refined Learnings (from pilot discussion)

### Three orchestration eras to detect

The pilot revealed three distinct orchestration mechanisms users may have adopted over time:

| Era | Mechanism | Detection method |
|---|---|---|
| Framework-based | Custom frameworks in project dirs dispatching via Task tool with structured XML prompts (`<objective>`, `<execution_context>`, `<verification_context>`) | Task tool calls with `subagent_session_id` + XML tags in subagent `first_message` |
| Skill-based | Skill chains (brainstorming -> writing-plans -> subagent-driven-development) invoked via Skill tool | `tool_calls.skill_name IS NOT NULL` |
| Workflow-based | Spacedock workflows with entity files and first-officer orchestration | Entity files, workflow scaffolding dirs |

**Detection gap:** `tool_calls.skill_name` only captures Skill tool invocations. Framework-based orchestration (which may represent significant usage) is invisible unless the discovery skill also inspects subagent `first_message` content for structured dispatch patterns like XML tags or templated prompts.

The discovery skill should recommend:
- Framework-based patterns -> commission a spacedock workflow that replaces the custom framework
- Skill-based patterns -> commission a spacedock workflow that codifies the skill chain
- Already-workflow patterns -> no action needed (or suggest refinements)

### Interaction axis: co-creating vs delegating

Sessions fall on a spectrum that determines what kind of workflow (if any) to recommend:

| Mode | Signal | User msg ratio | Recommendation |
|---|---|---|---|
| Fire-and-forget delegation | 1-2 user messages, high subagent count | <2% | Full workflow automation |
| Gated delegation | Approval gates (AskUserQuestion), short user responses | 2-10% | Workflow with explicit approval stages |
| Co-creation | High user interaction, brainstorming, collaborative design | >10% | Structured template with checkpoints, not full automation |

Discovery should present this axis to users: "This pattern looks like delegation — want a hands-off workflow? This other pattern looks collaborative — want a structured template with checkpoints instead?"

### Shell history as workflow source

Users often develop repeatable protocols that live in their shell history (recalled via ctrl-r and edited). The repeated first-message templates found in the pilot data are exactly this: a protocol the user has codified in muscle memory but not in tooling. This is the strongest signal for workflow discovery — if a user has typed nearly the same prompt 16 times across 4 projects, they already have a workflow; it just needs to be formalized.

### Context-file bootstrapping is iterative test design

The "Context file: ... Objective: e2e test every corner case" pattern is not simple test re-runs. It's iterative test design: define user-first interaction paths, see what errors they expose, refine, re-run. This means a workflow for this pattern should support iteration (run -> review results -> refine test plan -> re-run) rather than a one-shot pipeline.

### UX: on-demand, project-scoped first

Discovery should be invoked explicitly (e.g., `/discover-workflows`), not proactively on session start. Start project-scoped (analyze current project's history), then expand to cross-project pattern detection. Cross-project analysis surfaces shared templates that could become general-purpose workflows.

```
/discover-workflows              # current project
/discover-workflows --all        # cross-project patterns
```

## Stage Report

1. Query AgentsView database for session structure patterns: **DONE** — 1018 sessions analyzed; 85.7% are child sessions (subagent/fork); session length distribution spans 1-900+ messages; heavy orchestration projects identified.

2. Analyze tool usage patterns: **DONE** — Bash/Read dominate (70%); task management tools at 7.7%; key transitions identified (Read->Edit, Bash->TaskUpdate); clear orchestrator vs worker tool profiles.

3. Analyze multi-agent patterns: **DONE** — 2-level nesting common; subagent-to-toplevel ratios range 3x-20x; fork sessions have zero user messages (fully automated); orchestration patterns consistent across projects.

4. Identify recurring task patterns from message content: **DONE** — Six abstract pattern categories identified: plan-execute-test orchestration, context-file E2E loops, brainstorm-plan-implement pipelines, investigation-fix-PR cycles, cross-session continuity, approval-gated progression.

5. Identify state management signals across sessions: **DONE** — 26% of top-level sessions show cross-session continuity; worktrees used as isolation; task tools in 18% of sessions; journal in 11% of sessions.

6. Synthesize discovery signals: **DONE** — Seven reliable signals identified: repeated first-message templates, high subagent-to-interaction ratio, plan-file references, recurring tool sequences, cross-session continuity, approval gates, context-file bootstrapping.

7. Propose approach for workflow discovery skill: **DONE** — Four-phase approach (scan, classify, recommend, generate) with pattern-to-workflow mapping table and minimum viable implementation outlined.
