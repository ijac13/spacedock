# Code Project Guardrails

This section holds code-project-specific rules that apply across platforms and runtimes.

## Git and Worktrees

- Keep the main orchestrator anchored at the project root.
- Use `git worktree` for stages marked `worktree: true`.
- Use a filesystem-safe worktree key for `.worktrees/{worker_key}-{slug}` and `{worker_key}/{slug}` branch names.
- Do not leak logical worker ids containing `:` into paths or branch names.
- Remove worktrees with `git worktree remove`, not `rm -rf` — filesystem deletion leaves stale tracking entries in git.
- Remove worktrees only after their changes are merged or deliberately discarded.

## Paths and File Scope

- Prefer absolute paths in dispatch prompts and shell commands.
- Workers must stay inside the assigned worktree when one is provided.
- Entity frontmatter belongs to the first officer on main.
- Entity body edits and stage reports belong to the worker.
- The FO's full write scope on main is in `first-officer-shared-core.md` under **FO Write Scope**. Anything outside that allow-list must go through a dispatched worker.

## Scaffolding

- Treat `skills/`, `agents/`, `references/`, `plugin.json`, and workflow `README.md` scaffolding as protected surfaces.
- Changes to scaffolding should be tied to a tracked task or approved issue.

## Commits and Evidence

- Commit meaningful stage work before reporting completion.
- Preserve stage-specific commit discipline when the workflow defines it.
- Prefer concrete evidence in stage reports: test output, file paths, branch/worktree state, or other directly inspectable artifacts.

