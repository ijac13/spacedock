# Code Project Guardrails

This section holds code-project-specific rules that apply across platforms and runtimes.

## Git and Worktrees

- Keep the main orchestrator anchored at the project root.
- Use `git worktree` for stages marked `worktree: true`.
- Use a filesystem-safe worktree key for `.worktrees/{worker_key}-{slug}` and `{worker_key}/{slug}` branch names.
- Do not leak logical worker ids containing `:` into paths or branch names.
- Remove worktrees only after their changes are merged or deliberately discarded.

## Paths and File Scope

- Prefer absolute paths in dispatch prompts and shell commands.
- Workers must stay inside the assigned worktree when one is provided.
- Entity frontmatter belongs to the first officer on main.
- Entity body edits and stage reports belong to the worker.

## Scaffolding

- Do not directly edit `.claude/agents/`.
- Treat `templates/`, `skills/`, `plugin.json`, and workflow `README.md` scaffolding as protected surfaces.
- Changes to scaffolding should be tied to a tracked task or approved issue.

## Commits and Evidence

- Commit meaningful stage work before reporting completion.
- Preserve stage-specific commit discipline when the workflow defines it.
- Prefer concrete evidence in stage reports: test output, file paths, branch/worktree state, or other directly inspectable artifacts.

