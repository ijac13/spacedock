# Spacedock

Spacedock turns directories of markdown files into structured workflows operated by AI agents. Each file is a work item that moves through defined stages, with human approval gates where they matter and stage reports that give you concise, high-signal evidence at each gate.

**You want Spacedock if:**

- **You are a human tired of context-switching** between agent sessions to make approval decisions. Spacedock batches the decisions an AI wants to hand back to you, and presents each one with structured evidence so you can approve or redirect without re-loading context.
- **You are an agent delegating repeatable work** and you want a structured place to queue up approval-worthy decisions for your human without interrupting them for every tiny step.

## What's Different

- **Approval gates with structured evidence.** Every gate comes with a stage report (test outputs, before/after diffs, checklist verdicts, commit SHAs, anomalies) so you can approve, redirect, or bounce back faster than hunting through a sprawling PR.
- **Isolation.** Stages that need it run in their own git worktree and branch; lightweight stages run inline on main. You declare which is which, and the first officer enforces it.
- **Declarative and flexible.** Mission shape, stages, work item schema, and gates all live in plain markdown. The whole workflow is a few files in your repo that you can read, edit, fork, and commit like any other code.
- **Composable.** A single repo can host several workflows side by side, and work items in one workflow can reference items in another when your work spans more than one mission shape.

## Quick Start

**Prerequisites:** Claude Code or Codex CLI.

### Claude Code

1. `claude plugin marketplace add clkao/spacedock`
2. `claude plugin install spacedock`
3. Start a first-officer session and commission your workflow in one command:

   ```bash
   claude --agent spacedock:first-officer "/spacedock:commission <your mission prompt>"
   ```

### Codex CLI

1. Clone Spacedock and expose its skills under the Codex skills namespace:

   ```bash
   git clone https://github.com/clkao/spacedock.git /path/to/spacedock
   mkdir -p ~/.agents/skills
   ln -s /path/to/spacedock/skills ~/.agents/skills/spacedock
   ```

   This makes `~/.agents/skills/spacedock/first-officer/SKILL.md` and `~/.agents/skills/spacedock/ensign/SKILL.md` resolve to the cloned repo: the layout the Codex runtime adapters expect.

2. Start Codex interactively with multi-agent enabled, then prompt it to use the first-officer skill and commission your workflow:

   ```bash
   codex --enable multi_agent
   ```

   At the prompt: `Use the spacedock:first-officer skill to run /spacedock:commission <your mission prompt> in this directory.`

> Codex multi-agent is experimental. The Claude Code path is the primary supported surface.

### Example workflows

**Email triage:** `claude --agent spacedock:first-officer "/spacedock:commission Email triage: fetch, categorize, and act on Gmail inbox. Entity: a batch of up to 50 emails. Stages: intake (use gws-cli, triage in:inbox and read email body if necessary, categorize, propose action per email, output as table) → approval (Captain reviews proposal) -> execute (carry out approved actions, do not mark as read). Use gws-cli (https://github.com/googleworkspace/cli/tree/main/skills/gws-gmail), GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws/<account> for different accounts. Walk me through gws-cli setup if not already done."`

**[Superpowers](https://github.com/obra/superpowers)-style dev task workflow:** `claude --agent spacedock:first-officer "/spacedock:commission Dev task workflow: superpowers-style design → plan → implement → review with ## Design and ## Implementation Plan inlined in the entity body (no separate spec/plan files), implement on isolated worktrees with strict TDD, design and review gated for approval."`

## What a Work Item Looks Like

```yaml
---
id: 054
title: Session debrief command
status: done
---

Problem statement, design notes, acceptance criteria, and stage reports
all live in the body of this file as the work moves through stages.
```

See [a completed example](https://github.com/clkao/spacedock/blob/main/docs/plans/_archive/session-debrief.md) from Spacedock's own workflow.

## Concepts

| Concept | What it is |
|---------|------------|
| **Mission** | The purpose of the workflow: what it processes and what it delivers. |
| **Work item** | A single markdown file describing one thing being worked on: an email batch, a dev task, a draft. |
| **Workflow** | A directory of work items plus the README that defines stages, schema, and gates. |
| **Stage** | A named step a work item passes through (e.g. design, implement, review). |
| **Gate** | A pause point at a stage boundary where the captain approves, redirects, or bounces the work back. |

*"I am the master of my fate, I am the captain of my soul."* -- William Ernest Henley, *Invictus*

| Role | Who |
|---------|------------|
| **Captain** | You. You define the mission and make the calls at approval gates. |
| **First Officer** | The orchestrator agent that manages the workflow and reports to you at gates. |
| **Ensign** | The worker agent that moves a single item forward through one stage. |

## How It Works

The first officer reads the workflow README, checks work item statuses, and dispatches ensigns for items ready to advance. Stages that need isolation (typically implementation work with commits) run inside their own git worktree; lightweight stages (design, review, triage) run inline. At approval gates the first officer pauses and presents the ensign's stage report for your review: approve, redo with feedback, or reject. Rejected work automatically bounces back for revision in a fresh round of the earlier stage, with a hard cap so you never get stuck in an infinite loop. When you end a session, `/spacedock:debrief` captures what happened (commits, task state changes, decisions, open issues) into a record the next session picks up automatically (see [an example debrief](https://github.com/clkao/spacedock/blob/main/docs/plans/_debriefs/2026-04-09-01.md) from a real session).

## What Gets Generated

When you run `/spacedock:commission`, the following files are added to your workflow directory:

- **`{dir}/README.md`**: workflow schema, stage definitions, and work item template
- **`{dir}/*.md`**: seed work item files
- **`{dir}/_mods/`**: local modifications carried across refits

**Shipped by the Spacedock plugin:**

- **`spacedock:first-officer`**: the orchestrator agent that reads workflow state and dispatches ensigns
- **`spacedock:ensign`**: the worker agent dispatched to do stage work
- **`skills/commission/bin/status`**: read and advance workflow state without switching to a separate tracking tool

The generated workflow README is the single source of truth. The first officer reads it to know what stages exist, what quality criteria to enforce, and when to pause for your review.

Workflows can extend their own behavior via markdown mod files (`_mods/*.md`) that declare hook handlers for lifecycle events like startup, idle, or merge. For example, the [`pr-merge` mod](docs/plans/_mods/pr-merge.md) opens a pull request automatically when a completed worktree branch is ready to land.

When a new Spacedock release is available, use `/spacedock:refit` to upgrade your workflow scaffolding while keeping local modifications.

## Tips

- **Run Spacedock inside a sandbox.** Recommended: [agent-safehouse](https://github.com/eugene1g/agent-safehouse) (macOS), [packnplay](https://github.com/obra/packnplay), a devcontainer, or a VM.
- **Talk directly to an ensign.** Claude Code supports agent team chat: while a dispatched ensign is running, you can `Shift+Up` / `Shift+Down` to switch panes and give the ensign feedback directly instead of routing everything through the first officer.

## Use Cases

- **Email triage**: classify and route incoming messages with AI agents, escalate to a human at review gates
- **Dev task workflow**: [superpowers](https://github.com/obra/superpowers)-style design -> plan -> implement -> review with approval gates
- **Content publishing**: manage drafts through editing, review, and publication stages
- **Research workflows**: process papers or data through analysis, synthesis, and validation
- **Dogfooding Spacedock's own development.** Spacedock is self-hosted. Its own development runs on a plain text workflow at [`docs/plans/`](docs/plans/). Run `skills/commission/bin/status --workflow-dir docs/plans` to see the current state.

## License

Spacedock is released under the [Apache License 2.0](LICENSE).
