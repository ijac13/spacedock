# Spacedock

Spacedock turns directories of markdown files into structured workflows operated by AI agents. Each file is a work item that moves through defined stages. An AI first officer manages the workflow: dispatching subagents, isolating work in git worktrees, and pausing at approval gates for human review.

Install it as a Claude Code plugin. Run `/spacedock commission` to design a workflow, and `claude --agent first-officer` to run it. Experimental support for other coding agents.

## Why Plain Text Workflows?

- **Agent-native** -- AI agents can read, write, and run markdown workflows without adapters or APIs
- **Flexible yet enforceable** -- define stages, transitions, and quality criteria declaratively; the first officer enforces them at runtime
- **Declarative human-in-the-loop** -- approval gates pause the workflow for human review at defined stage boundaries
- **Self-contained** -- Spacedock is not required for running the provisioned workflow; the generated files and agent are standalone
- **Composable** -- support multiple interconnected workflows (experimental)

*"I am the master of my fate, I am the captain of my soul."* -- William Ernest Henley, *Invictus*

## Concepts

You are the **captain**. You define the mission, commission the ship, and make the calls at critical moments.

| Concept | What it is |
|---------|------------|
| **Mission** | What the workflow is designed to achieve |
| **Work item** | A markdown file with YAML frontmatter, tracked as an entity in the schema |
| **Workflow** | A directory of work items with a README defining stages and schema |
| **Stages** | Ordered statuses a work item moves through, with optional approval gates for human review |
| **First officer** | A generated AI agent that reads workflow state, dispatches ensigns, and reports to you at gates |
| **Ensign** | A worker agent dispatched by the first officer to do the actual stage work |

## Quick Start

Install from the Claude Code plugin marketplace:

```
/install github.com/clkao/spacedock
```

Then commission a workflow:

```
/spacedock commission
```

You can provide context in the command itself:

```
/spacedock:commission email triage workflow using gws-cli
/spacedock:commission track design ideas through review and implementation
/spacedock:commission content publishing with editorial approval gates
```

The commission skill helps you design the workflow interactively: defining your mission, entity type, stages, and seed items. You review everything before generation.

To run the workflow:

```
claude --agent first-officer
```

### Local Development

To work on Spacedock itself, install from a local clone:

```bash
git clone git@github.com:clkao/spacedock.git /path/to/spacedock
claude --plugin-dir /path/to/spacedock
```

## How It Works

The first officer reads the workflow README, checks work item statuses, and dispatches ensigns for items ready to advance. Each ensign works in an isolated git worktree so multiple items can be processed in parallel without interfering with each other.

At approval gates, the first officer pauses and presents the ensign's work for your review. You can approve, request a redo with feedback, or reject.

## What Gets Generated

- **`{dir}/README.md`** -- workflow schema, stage definitions, and entity template
- **`{dir}/status`** -- bash script showing a one-line-per-work-item overview
- **`{dir}/*.md`** -- seed work item files
- **`.claude/agents/first-officer.md`** -- AI agent that orchestrates the workflow

The README is the single source of truth. The first officer reads it to know what stages exist, what quality criteria to enforce, and when to pause for your review.

When a new Spacedock release is available, use `/spacedock refit` to upgrade your workflow scaffolding while keeping local modifications.

## Use Cases

- **Feature tracking** -- track ideas through ideation, implementation, validation, and approval
- **Email triage** -- classify and route incoming messages with AI agents, escalate to human at review gates
- **Content publishing** -- manage drafts through editing, review, and publication stages
- **Research pipelines** -- process papers or data through analysis, synthesis, and validation

Spacedock is self-hosted and bootstrapped: it manages its own development with a plain text workflow at [`docs/plans/`](docs/plans/). Run `docs/plans/status` to see the current state.
