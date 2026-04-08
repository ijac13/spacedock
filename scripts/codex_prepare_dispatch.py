#!/usr/bin/env python3
"""Prepare one bounded Codex worker dispatch for a Spacedock workflow entity."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Stage:
    name: str
    props: dict[str, object]


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


def parse_scalar(value: str) -> object:
    value = value.strip()
    if value == "":
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value.strip("\"'")


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
        key, _, value = line.partition(":")
        key = key.strip()
        if key in updates:
            out.append(f"{key}: {updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}: {value}")
    final_lines = ["---", *out, "---", *body_lines]
    return "\n".join(final_lines) + "\n"


def parse_stages(readme_text: str) -> list[Stage]:
    fm_lines, _ = split_frontmatter(readme_text)
    stages: list[Stage] = []
    in_states = False
    current: Stage | None = None
    for raw in fm_lines:
        line = raw.rstrip()
        stripped = line.strip()
        if stripped == "states:":
            in_states = True
            continue
        if not in_states:
            continue
        if re.match(r"^\s*-\s+name:\s+", line):
            if current is not None:
                stages.append(current)
            name = line.split(":", 1)[1].strip()
            current = Stage(name=name, props={})
            continue
        if current is None:
            continue
        if not line.startswith("      "):
            if stripped:
                stages.append(current)
                current = None
                in_states = False
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        current.props[key.strip()] = parse_scalar(value)
    if current is not None:
        stages.append(current)
    return stages


def extract_stage_definition(readme_text: str, stage_name: str) -> str:
    pattern = re.compile(
        rf"^###\s+{re.escape(stage_name)}\s*$\n(.*?)(?=^###\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(readme_text)
    if not match:
        return stage_name
    return match.group(1).strip()


def derive_checklist(stage_name: str) -> list[str]:
    if stage_name.lower() in {"validation", "review"}:
        return [
            "Run the relevant checks against the acceptance criteria",
            "Record a PASSED or REJECTED verdict with evidence",
            "Update the stage report and return a concise summary",
        ]
    return [
        "Produce the stage outputs for this entity",
        "Update the stage report with evidence for each checklist item",
        "Commit meaningful stage work before finishing",
    ]


def git_output(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def git_run(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def build_worker_prompt(payload: dict[str, object]) -> str:
    checklist = payload["checklist"]
    if payload["role_asset_kind"] == "skill":
        lines = [
            f"You are the packaged worker `{payload['dispatch_agent_id']}`.",
            "Resolve your role definition before doing anything else.",
            f"If your operating contract was not already loaded via skill preloading, invoke the `{payload['dispatch_agent_id']}` skill now to load it.",
            "After the skill is loaded, continue with the assignment below.",
            "",
            "Assignment:",
            f"dispatch_agent_id: {payload['dispatch_agent_id']}",
            f"worker_key: {payload['worker_key']}",
            f"role_asset_kind: {payload['role_asset_kind']}",
            f"role_asset_name: {payload['role_asset_name']}",
            f"workflow_dir: {payload['workflow_dir']}",
            f"entity_path: {payload['entity_path']}",
            f"stage_name: {payload['stage_name']}",
            "stage_definition_text:",
            str(payload["stage_definition_text"]),
            f"worktree_path: {payload['worktree_path']}",
            "checklist:",
        ]
    else:
        lines = [
            "You are a generic worker handling one entity for one stage.",
            "Operate directly from the assignment below.",
            "Do not modify YAML frontmatter in entity files.",
            "Do not take over first-officer responsibilities.",
            "",
            "Assignment:",
            f"dispatch_agent_id: {payload['dispatch_agent_id']}",
            f"worker_key: {payload['worker_key']}",
            f"role_asset_kind: {payload['role_asset_kind']}",
            f"role_asset_name: {payload['role_asset_name']}",
            f"workflow_dir: {payload['workflow_dir']}",
            f"entity_path: {payload['entity_path']}",
            f"stage_name: {payload['stage_name']}",
            "stage_definition_text:",
            str(payload["stage_definition_text"]),
            f"worktree_path: {payload['worktree_path']}",
            "checklist:",
        ]
    lines.extend(f"- {item}" for item in checklist)
    lines.extend(
        [
            "",
            "Completion rule:",
            "After you finish the assignment, write the stage report, commit your work, return one concise final response, and stop immediately.",
            "Do not continue exploring the repo, do not wait for follow-up instructions, and do not start another task after that final response.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-dir", required=True)
    parser.add_argument("--entity-slug", required=True)
    parser.add_argument("--repo-root")
    args = parser.parse_args()

    repo_root = (Path(args.repo_root) if args.repo_root else Path(git_output(Path.cwd(), "rev-parse", "--show-toplevel"))).resolve()
    namespace_root = Path(__file__).resolve().parent.parent
    workflow_dir = Path(args.workflow_dir)
    if not workflow_dir.is_absolute():
        workflow_dir = (repo_root / workflow_dir).resolve()
    else:
        workflow_dir = workflow_dir.resolve()
    readme_path = workflow_dir / "README.md"
    entity_path = workflow_dir / f"{args.entity_slug}.md"
    readme_text = read_text(readme_path)
    entity_text = read_text(entity_path)

    stages = parse_stages(readme_text)
    if not stages:
        raise ValueError("No workflow stages parsed from README frontmatter")

    entity_fm = parse_frontmatter_map(entity_text)
    current_stage = entity_fm.get("status", "")
    current_index = next((i for i, s in enumerate(stages) if s.name == current_stage), None)
    if current_index is None:
        raise ValueError(f"Current stage not found in README: {current_stage}")
    if current_index + 1 >= len(stages):
        raise ValueError(f"No next stage after {current_stage}")
    next_stage = stages[current_index + 1]

    dispatch_agent_id = str(next_stage.props.get("agent") or "spacedock:ensign")
    worker_key = re.sub(r"[^A-Za-z0-9._-]", "-", dispatch_agent_id)
    if dispatch_agent_id.startswith("spacedock:"):
        role_asset_kind = "skill"
        role_asset_name = dispatch_agent_id.split(":", 1)[1]
        expected_asset = namespace_root / "skills" / role_asset_name / "SKILL.md"
        if not expected_asset.is_file():
            raise ValueError(f"Missing packaged skill asset for {dispatch_agent_id}: {expected_asset}")
    else:
        role_asset_kind = "prompt"
        role_asset_name = ""

    stage_name = next_stage.name
    current_stage_def = stages[current_index]
    if current_stage_def.props.get("gate") and next_stage.props.get("terminal"):
        raise ValueError(
            f"Refusing to auto-advance gated entity {args.entity_slug} from {current_stage} to terminal stage {stage_name} before approval"
        )

    branch_name = f"{worker_key}-{args.entity_slug}-{stage_name}"
    worktree_path = repo_root / ".spacedock" / "worktrees" / branch_name
    workflow_rel = workflow_dir.relative_to(repo_root)
    worktree_entity_path = worktree_path / workflow_rel / entity_path.name

    started_value = entity_fm.get("started", "")
    if not started_value:
        started_value = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    updated_entity = update_frontmatter_fields(
        entity_text,
        {
            "status": stage_name,
            "started": started_value,
            "worktree": str(worktree_path),
        },
    )
    entity_path.write_text(updated_entity)

    git_run(repo_root, "add", str(entity_path.relative_to(repo_root)))
    git_run(repo_root, "commit", "-m", f"{stage_name}: dispatch {args.entity_slug}")

    if not worktree_path.exists():
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        git_run(repo_root, "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD")

    payload: dict[str, object] = {
        "dispatch_agent_id": dispatch_agent_id,
        "worker_key": worker_key,
        "role_asset_kind": role_asset_kind,
        "role_asset_name": role_asset_name,
        "workflow_dir": str(workflow_dir),
        "entity_path": str(worktree_entity_path),
        "stage_name": stage_name,
        "stage_definition_text": extract_stage_definition(readme_text, stage_name),
        "worktree_path": str(worktree_path),
        "checklist": derive_checklist(stage_name),
        "branch_name": branch_name,
    }
    payload["spawn_message"] = build_worker_prompt(payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
