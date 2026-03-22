# Spacedock

Spacedock is a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin for creating **PTP (Plain Text Pipeline)** pipelines. A PTP pipeline is a directory of markdown files where each file is a work entity that moves through defined stages. No database, no external service, no web UI -- just markdown files with YAML frontmatter, tracked in git.

## Why Plain Text Pipelines?

- **Git-native** -- every state change is a diff, every transition has history
- **Agent-readable** -- Claude Code agents can read, write, and reason about markdown natively
- **Human-auditable** -- open any file in any editor to see exactly what's happening
- **No dependencies** -- no server, no API keys, no accounts, works offline
- **Composable** -- standard unix tools work out of the box (`grep`, `sort`, `bash`)

## PTP Concepts

| Concept | What it is |
|---------|------------|
| **Entity** | A markdown file with YAML frontmatter -- one work item |
| **Pipeline** | A directory of entity files |
| **Schema** | The pipeline's `README.md` -- defines frontmatter fields and stage definitions |
| **Stages** | Ordered statuses an entity moves through (e.g., `ideation -> implementation -> done`) |
| **Views** | Self-describing bash scripts that query pipeline state (e.g., the `status` script) |

## Quick Start

Spacedock is installed as a local Claude Code plugin. There is no registry yet -- point `--plugin-dir` at your local clone:

```bash
git clone <repo-url> /path/to/spacedock
claude --plugin-dir /path/to/spacedock
```

Then run the commission skill:

```
/spacedock commission
```

The commission walks you through six questions to design your pipeline:

1. **Mission** -- what's this pipeline for?
2. **Entity** -- what does each work item represent?
3. **Stages** -- what stages does an entity go through?
4. **Approval gates** -- which transitions need human approval?
5. **Seed entities** -- 2-3 starting items
6. **Location** -- where to create the pipeline directory

You can also provide all inputs in one message for batch mode (no interactive prompts).

After you confirm, Spacedock generates the pipeline directory, a status script, seed entity files, and a first-officer agent, then runs a pilot to prove the pipeline is executable.

## Project Structure

```
spacedock/
├── .claude-plugin/
│   └── plugin.json            # Plugin manifest
├── skills/
│   └── commission/
│       └── SKILL.md           # /spacedock commission skill prompt
├── agents/
│   └── first-officer.md       # Reference doc for the generated orchestrator agent
├── v0/
│   └── spec.md                # v0 specification
└── docs/
    └── plans/                 # Dogfood pipeline (Spacedock manages its own development)
        ├── README.md          # Pipeline schema and stage definitions
        ├── status             # Pipeline status viewer
        └── *.md               # Entity files
```

## Generated Pipeline Structure

When you commission a pipeline, Spacedock creates:

- **`{dir}/README.md`** -- schema, stage definitions, scoring rubric, entity template
- **`{dir}/status`** -- executable bash script showing one-line-per-entity overview
- **`{dir}/*.md`** -- seed entity files with valid YAML frontmatter
- **`.claude/agents/first-officer.md`** -- a pipeline orchestrator agent (generated per-pipeline at the target project root)

The first-officer agent is a dispatcher: it reads pipeline state, identifies what needs work, and dispatches pilot agents for each stage. It never does stage work itself.

## Current Status: v0 (Shuttle Mode)

v0 is **shuttle mode** -- a single general-purpose pilot agent handles all stages. The first officer dispatches pilots one at a time.

What works:
- Interactive and batch pipeline commissioning
- Pipeline file generation (README, status script, entities, first-officer agent)
- Pilot run to prove the pipeline is executable

What's deferred to v1 (starship mode):
- Specialized crew agents per stage
- `/spacedock refit` for examining and upgrading existing pipelines
- Multi-pipeline orchestration
- Pipeline templates library

See [`v0/spec.md`](v0/spec.md) for the full specification.

## Dogfood

Spacedock manages its own development with a PTP pipeline at [`docs/plans/`](docs/plans/). Entity files track features, bugs, and improvements through `ideation -> implementation -> validation -> done`. Run `bash docs/plans/status` to see the current state.
