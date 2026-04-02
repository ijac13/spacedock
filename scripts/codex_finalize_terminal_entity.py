#!/usr/bin/env python3
"""Finalize one terminal Spacedock entity on Codex by running merge hooks, merging, archiving, and cleanup."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text()


def split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Missing YAML frontmatter")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("Unterminated YAML frontmatter")
    return lines[1:end], lines[end + 1 :]


def parse_frontmatter_map(text: str) -> dict[str, str]:
    fm_lines, _ = split_frontmatter(text)
    out: dict[str, str] = {}
    for line in fm_lines:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def update_frontmatter_fields(text: str, updates: dict[str, str]) -> str:
    fm_lines, body_lines = split_frontmatter(text)
    seen: set[str] = set()
    out: list[str] = []
    for line in fm_lines:
        if ":" not in line:
            out.append(line)
            continue
        key, _, _value = line.partition(":")
        key = key.strip()
        if key in updates:
            out.append(f"{key}: {updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}: {value}")
    return "\n".join(["---", *out, "---", *body_lines]) + "\n"


def git_run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def git_output(repo_root: Path, *args: str) -> str:
    return git_run(repo_root, *args).stdout.strip()


def extract_merge_hook_commands(mod_text: str) -> list[str]:
    section_match = re.search(
        r"^## Hook:\s*merge\s*$\n(.*?)(?=^## Hook:|\Z)",
        mod_text,
        re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        return []
    body = section_match.group(1)
    commands: list[str] = []
    for match in re.finditer(r"```(?:bash|sh)?\n(.*?)```", body, re.DOTALL):
        block = match.group(1).strip()
        if block:
            commands.append(block)
    return commands


def run_merge_hooks(repo_root: Path, workflow_dir: Path, slug: str, branch_name: str, worktree_path: Path) -> list[dict[str, str]]:
    mods_dir = workflow_dir / "_mods"
    results: list[dict[str, str]] = []
    if not mods_dir.is_dir():
        return results
    for mod_path in sorted(mods_dir.glob("*.md")):
        mod_text = read_text(mod_path)
        commands = extract_merge_hook_commands(mod_text)
        if not commands:
            continue
        for command in commands:
            rendered = (
                command
                .replace("{slug}", slug)
                .replace("{workflow_dir}", str(workflow_dir))
                .replace("{branch}", branch_name)
                .replace("{worktree}", str(worktree_path))
            )
            subprocess.run(
                ["/bin/bash", "-lc", rendered],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            results.append({"mod": mod_path.name, "command": rendered})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--workflow-dir", required=True)
    parser.add_argument("--entity-slug", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    workflow_dir = Path(args.workflow_dir).resolve()
    slug = args.entity_slug
    entity_path = workflow_dir / f"{slug}.md"
    if not entity_path.is_file():
        raise ValueError(f"Entity not found on main branch: {entity_path}")

    entity_text = read_text(entity_path)
    frontmatter = parse_frontmatter_map(entity_text)
    worktree_value = frontmatter.get("worktree", "").strip()
    if not worktree_value:
        raise ValueError("Entity has no worktree to merge from")

    worktree_path = Path(worktree_value)
    branch_name = worktree_path.name

    hook_results = run_merge_hooks(repo_root, workflow_dir, slug, branch_name, worktree_path)

    updated_main_fm = parse_frontmatter_map(read_text(entity_path))
    if updated_main_fm.get("pr", "").strip():
        print(json.dumps({
            "handled_by_hook": True,
            "pr_pending": True,
            "hook_count": len(hook_results),
            "slug": slug,
        }, indent=2))
        return 0

    git_run(repo_root, "merge", "--ff-only", branch_name)

    merged_entity_text = read_text(entity_path)
    completed_value = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    archived_text = update_frontmatter_fields(
        merged_entity_text,
        {
            "status": "done",
            "completed": completed_value,
            "verdict": "PASSED",
            "worktree": "",
        },
    )
    entity_path.write_text(archived_text)

    archive_dir = workflow_dir / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / entity_path.name
    git_run(repo_root, "mv", str(entity_path), str(archive_path))

    git_run(repo_root, "add", "-A", str(workflow_dir))
    git_run(repo_root, "commit", "-m", f"done: archive {slug}")
    final_commit = git_output(repo_root, "rev-parse", "HEAD")

    if worktree_path.exists():
        git_run(repo_root, "worktree", "remove", str(worktree_path))
    existing_branches = git_output(repo_root, "branch", "--list", branch_name)
    if existing_branches:
        git_run(repo_root, "branch", "-D", branch_name)

    result = {
        "handled_by_hook": bool(hook_results),
        "pr_pending": False,
        "hook_count": len(hook_results),
        "archive_path": str(archive_path),
        "final_commit": final_commit,
        "branch_name": branch_name,
        "worktree_removed": not worktree_path.exists(),
        "slug": slug,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
