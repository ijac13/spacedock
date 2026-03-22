<!-- ABOUTME: Reference for the first-officer agent pattern used in Spacedock pipelines. -->
<!-- ABOUTME: The actual agent is generated per-pipeline by /spacedock commission. -->

# First Officer Agent

The first-officer agent is generated per-pipeline by `/spacedock commission` and placed at
`.claude/agents/first-officer.md` in the target project (standard Claude Code agent location).

Each generated instance is configured for a specific pipeline: it knows the pipeline directory,
mission, and stage definitions for that pipeline.

## Role

The first officer is a dispatcher. It reads pipeline state and dispatches pilot agents to do
stage work. It never performs stage work itself.

On startup it reads the pipeline README, runs the status script, and dispatches pilots for
entities ready to advance. After each pilot completes, it updates frontmatter, re-runs status,
and dispatches the next worker.

## Full Template Specification

See `v0/spec.md` — the "`.claude/agents/first-officer.md`" section contains the complete
frontmatter and prompt body template used during generation.
