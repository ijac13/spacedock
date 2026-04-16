#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ""
# ///
# ABOUTME: Unit tests for `claude-team spawn-standing` subcommand and member_exists helper.
# ABOUTME: Covers spawn-absent, spawn-present, enum validation, missing-prompt, and pilot-mod parse.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "commission" / "bin" / "claude-team"
PILOT_MOD = REPO_ROOT / "docs" / "plans" / "_mods" / "comm-officer.md"


PILOT_MOD_FIXTURE = """---
name: comm-officer
description: Standing prose-polishing teammate for this workflow
version: 0.1.0
standing: true
---

# Comm Officer

## Hook: startup

- `subagent_type: general-purpose`
- `name: comm-officer`
- `team_name: {current team}`
- `model: sonnet`

## Agent Prompt

You are the comm officer. Reply with polished prose.
"""


def write_team_config(home: Path, team: str, members: list[dict]) -> Path:
    teams_dir = home / ".claude" / "teams" / team
    teams_dir.mkdir(parents=True, exist_ok=True)
    config_path = teams_dir / "config.json"
    config_path.write_text(json.dumps({"name": team, "members": members}))
    return config_path


def run_spawn_standing(
    tmp_path: Path, mod_path: Path, team: str
) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "spawn-standing", "--mod", str(mod_path), "--team", team],
        capture_output=True,
        text=True,
        env=env,
    )


class TestSpawnAbsent:
    """AC-3: helper emits Agent() spec JSON when member absent from team."""

    def test_emits_spec_when_absent(self, tmp_path):
        mod = tmp_path / "mod.md"
        mod.write_text(PILOT_MOD_FIXTURE)
        write_team_config(tmp_path, "test-team", [{"name": "team-lead"}])

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        spec = json.loads(result.stdout)
        assert set(spec.keys()) == {"subagent_type", "name", "team_name", "model", "prompt"}
        assert spec["subagent_type"] == "general-purpose"
        assert spec["name"] == "comm-officer"
        assert spec["team_name"] == "test-team"
        assert spec["model"] == "sonnet"
        assert "You are the comm officer" in spec["prompt"]

    def test_emits_spec_when_team_config_missing(self, tmp_path):
        """A non-existent team config counts as `member absent` — spawn normally."""
        mod = tmp_path / "mod.md"
        mod.write_text(PILOT_MOD_FIXTURE)

        result = run_spawn_standing(tmp_path, mod, "brand-new-team")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        spec = json.loads(result.stdout)
        assert spec["name"] == "comm-officer"


class TestSpawnPresent:
    """AC-4: helper emits already-alive JSON when member exists in team config."""

    def test_emits_already_alive_when_present(self, tmp_path):
        mod = tmp_path / "mod.md"
        mod.write_text(PILOT_MOD_FIXTURE)
        write_team_config(
            tmp_path,
            "test-team",
            [
                {"name": "team-lead"},
                {"name": "comm-officer", "agentType": "general-purpose", "model": "sonnet"},
            ],
        )

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        payload = json.loads(result.stdout)
        assert payload == {"status": "already-alive", "name": "comm-officer"}


class TestEnumValidation:
    """AC-5: helper rejects invalid model with stderr naming field + enum list."""

    def test_enum_validation_rejects_bad_model(self, tmp_path):
        mod = tmp_path / "mod.md"
        mod.write_text(PILOT_MOD_FIXTURE.replace("model: sonnet", "model: gpt-5"))
        write_team_config(tmp_path, "test-team", [])

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode != 0
        # stderr MUST contain BOTH the offending field name AND the enum list literal.
        assert "model" in result.stderr
        assert "must be one of: sonnet, opus, haiku" in result.stderr


class TestErrorPaths:
    """AC-6 and AC-7: helper errors loudly on missing pieces and convention violations."""

    def test_errors_on_missing_agent_prompt(self, tmp_path):
        mod = tmp_path / "mod.md"
        mod.write_text(
            """---
name: foo
standing: true
---

## Hook: startup

- `subagent_type: general-purpose`
- `name: foo`
- `model: sonnet`
"""
        )
        write_team_config(tmp_path, "test-team", [])

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode != 0
        assert "Agent Prompt" in result.stderr

    def test_errors_on_missing_standing_flag(self, tmp_path):
        mod = tmp_path / "mod.md"
        mod.write_text(PILOT_MOD_FIXTURE.replace("standing: true", "standing: false"))
        write_team_config(tmp_path, "test-team", [])

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode != 0
        assert "standing" in result.stderr

    def test_errors_on_trailing_section_after_agent_prompt(self, tmp_path):
        """AC-7: convention violation — trailing `## ` heading after the prompt section."""
        mod = tmp_path / "mod.md"
        mod.write_text(
            PILOT_MOD_FIXTURE
            + "\n## Notes\n\nTrailing content after the prompt section.\n"
        )
        write_team_config(tmp_path, "test-team", [])

        result = run_spawn_standing(tmp_path, mod, "test-team")
        assert result.returncode != 0
        assert "## Notes" in result.stderr

    def test_errors_on_missing_mod_file(self, tmp_path):
        write_team_config(tmp_path, "test-team", [])
        result = run_spawn_standing(tmp_path, tmp_path / "does-not-exist.md", "test-team")
        assert result.returncode != 0
        assert "not found" in result.stderr


class TestPilotMod:
    """AC-11: pilot docs/plans/_mods/comm-officer.md parses cleanly through the helper."""

    def test_pilot_mod_parses_cleanly_absent(self, tmp_path):
        """Fresh team (no comm-officer member) — emit a well-shaped spec JSON."""
        assert PILOT_MOD.exists(), f"pilot mod not found at {PILOT_MOD}"
        write_team_config(tmp_path, "fresh-team", [{"name": "team-lead"}])

        result = run_spawn_standing(tmp_path, PILOT_MOD, "fresh-team")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        spec = json.loads(result.stdout)
        assert set(spec.keys()) == {"subagent_type", "name", "team_name", "model", "prompt"}
        assert spec["name"] == "comm-officer"
        assert spec["model"] == "sonnet"
        assert spec["subagent_type"] == "general-purpose"
        # All four findings (A/B/C/D) from the mod's prompt must be preserved verbatim.
        assert "elements-of-style:writing-clearly-and-concisely" in spec["prompt"]
        assert "your reply body IS the deliverable" in spec["prompt"].lower() or \
               "your reply body is the deliverable" in spec["prompt"].lower() or \
               "Your reply body IS the deliverable" in spec["prompt"]
        assert "discrete standalone message" in spec["prompt"]
        assert "disambiguating" in spec["prompt"].lower() or \
               "parenthetical" in spec["prompt"].lower()

    def test_pilot_mod_reports_already_alive_when_member_present(self, tmp_path):
        """Populated team (comm-officer already live) — emit already-alive payload."""
        assert PILOT_MOD.exists(), f"pilot mod not found at {PILOT_MOD}"
        write_team_config(
            tmp_path,
            "populated-team",
            [
                {"name": "team-lead"},
                {"name": "comm-officer", "agentType": "general-purpose", "model": "sonnet"},
            ],
        )

        result = run_spawn_standing(tmp_path, PILOT_MOD, "populated-team")
        assert result.returncode == 0, f"stderr: {result.stderr}"

        payload = json.loads(result.stdout)
        assert payload == {"status": "already-alive", "name": "comm-officer"}


_BUILD_WORKFLOW_README = """---
commissioned-by: spacedock@test
entity-label: task
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: backlog
      initial: true
    - name: ideation
    - name: done
      terminal: true
---

# Test Workflow

## Stages

### `backlog`

The initial holding stage.

### `ideation`

Flesh out the idea.

### `done`

Terminal.
"""


_BUILD_ENTITY_BODY = """---
id: 001
title: My test task
status: ideation
score: 0.50
worktree:
---

Description of the task.
"""


def _standing_mod_with_usage(usage_body: str) -> str:
    """Return a standing-teammate mod body with the given `## Routing Usage` content.

    An empty string for usage_body produces an empty section (heading +
    blank lines). Pass None via a different helper to omit the section.
    """
    return (
        "---\n"
        "name: comm-officer\n"
        "description: Standing prose-polishing teammate for this workflow\n"
        "version: 0.1.0\n"
        "standing: true\n"
        "---\n"
        "\n"
        "# Comm Officer\n"
        "\n"
        "## Hook: startup\n"
        "\n"
        "- `subagent_type: general-purpose`\n"
        "- `name: comm-officer`\n"
        "- `team_name: {current team}`\n"
        "- `model: sonnet`\n"
        "\n"
        f"## Routing Usage\n\n{usage_body}\n\n"
        "## Agent Prompt\n"
        "\n"
        "You are the comm officer. Reply with polished prose.\n"
    )


_STANDING_MOD_NO_USAGE = """---
name: comm-officer
description: Standing prose-polishing teammate for this workflow
version: 0.1.0
standing: true
---

# Comm Officer

## Hook: startup

- `subagent_type: general-purpose`
- `name: comm-officer`
- `team_name: {current team}`
- `model: sonnet`

## Agent Prompt

You are the comm officer. Reply with polished prose.
"""


_NON_STANDING_MOD = """---
name: pr-merge
description: PR merge helper (not standing)
version: 0.1.0
---

# PR merge

## Hook: merge

- runs on validation PASSED

## Agent Prompt

Trivial.
"""


def _write_build_workflow(tmp_path: Path) -> tuple[Path, Path]:
    wf = tmp_path / "workflow"
    wf.mkdir()
    (wf / "README.md").write_text(_BUILD_WORKFLOW_README)
    entity = wf / "my-task.md"
    entity.write_text(_BUILD_ENTITY_BODY)
    return wf, entity


def _run_build_with_home(
    wf_dir: Path, stdin_data: dict, home: Path
) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "build", "--workflow-dir", str(wf_dir)],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        cwd=wf_dir.parent,
        env=env,
    )


def _write_team_config_local(home: Path, team: str, members: list) -> Path:
    teams_dir = home / ".claude" / "teams" / team
    teams_dir.mkdir(parents=True, exist_ok=True)
    config_path = teams_dir / "config.json"
    config_path.write_text(json.dumps({"name": team, "members": members}))
    return config_path


class TestRoutingUsagePayload:
    """AC-1..AC-5: `claude-team build` splices `## Routing Usage` under each teammate."""

    _SECTION_HEADING = "### Standing teammates available in your team"
    _FALLBACK_LINE = (
        "SendMessage with the relevant input shape; reply format per the mod."
    )

    def _build(self, tmp_path, mods: dict[str, str], team: str, members: list) -> dict:
        wf, entity = _write_build_workflow(tmp_path)
        mods_dir = wf / "_mods"
        mods_dir.mkdir()
        for name, body in mods.items():
            (mods_dir / name).write_text(body)
        _write_team_config_local(tmp_path, team, members)
        inp = {
            "schema_version": 1,
            "entity_path": str(entity),
            "workflow_dir": str(wf),
            "stage": "ideation",
            "checklist": ["1. Item"],
            "team_name": team,
            "bare_mode": False,
        }
        result = _run_build_with_home(wf, inp, home=tmp_path)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        return json.loads(result.stdout)

    def test_routing_usage_body_rendered_with_bullets_preserved(self, tmp_path):
        """AC-1: body spliced under teammate header; bullets survive reindent."""
        usage = (
            "Two patterns:\n"
            "\n"
            "- pattern X: trigger Y\n"
            "- pattern Z: trigger W\n"
        )
        out = self._build(
            tmp_path,
            {"comm-officer.md": _standing_mod_with_usage(usage)},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        prompt = out["prompt"]
        assert self._SECTION_HEADING in prompt
        assert "- pattern X: trigger Y" in prompt
        assert "- pattern Z: trigger W" in prompt
        assert "Two patterns:" in prompt

        lines = prompt.splitlines()
        header_idx = next(
            i for i, ln in enumerate(lines) if ln.startswith("- **comm-officer**")
        )
        following = lines[header_idx + 1:header_idx + 6]
        assert any(ln.startswith("  ") and "pattern X" in ln for ln in following), (
            f"Expected indented bullet body after header, got: {following}"
        )

    def test_routing_usage_heading_excluded(self, tmp_path):
        """AC-2: the literal `## Routing Usage` heading does NOT appear in prompt."""
        usage = "- pattern X: trigger Y\n"
        out = self._build(
            tmp_path,
            {"comm-officer.md": _standing_mod_with_usage(usage)},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        assert "## Routing Usage" not in out["prompt"]

    def test_routing_usage_terminates_at_next_heading(self, tmp_path):
        """AC-3: body does not leak into the following `## Agent Prompt` section."""
        usage = "- pattern X: trigger Y\n"
        out = self._build(
            tmp_path,
            {"comm-officer.md": _standing_mod_with_usage(usage)},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        prompt = out["prompt"]
        section_start = prompt.index(self._SECTION_HEADING)
        section_end = prompt.index(
            "Full routing contract", section_start
        )
        section_body = prompt[section_start:section_end]
        assert "You are the comm officer" not in section_body
        assert "Reply with polished prose" not in section_body

    def test_missing_routing_usage_falls_back(self, tmp_path):
        """AC-4: mod without `## Routing Usage` gets the one-liner fallback."""
        out = self._build(
            tmp_path,
            {"comm-officer.md": _STANDING_MOD_NO_USAGE},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        prompt = out["prompt"]
        assert self._SECTION_HEADING in prompt
        assert self._FALLBACK_LINE in prompt

    def test_empty_routing_usage_falls_back(self, tmp_path):
        """AC-4 + staff-review note 3: empty body → fallback one-liner."""
        out = self._build(
            tmp_path,
            {"comm-officer.md": _standing_mod_with_usage("")},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        prompt = out["prompt"]
        assert self._SECTION_HEADING in prompt
        assert self._FALLBACK_LINE in prompt

    def test_whitespace_only_routing_usage_falls_back(self, tmp_path):
        """AC-4 + staff-review note 3: whitespace-only body → fallback."""
        out = self._build(
            tmp_path,
            {"comm-officer.md": _standing_mod_with_usage("   \n\t\n  ")},
            "active-team",
            [{"name": "team-lead"}, {"name": "comm-officer"}],
        )
        prompt = out["prompt"]
        assert self._SECTION_HEADING in prompt
        assert self._FALLBACK_LINE in prompt

    def test_non_standing_mod_ignored(self, tmp_path):
        """AC-5: non-standing mods do not appear in the enumeration."""
        usage = "- pattern X: trigger Y\n"
        out = self._build(
            tmp_path,
            {
                "comm-officer.md": _standing_mod_with_usage(usage),
                "pr-merge.md": _NON_STANDING_MOD,
            },
            "active-team",
            [
                {"name": "team-lead"},
                {"name": "comm-officer"},
                {"name": "pr-merge"},
            ],
        )
        prompt = out["prompt"]
        assert "comm-officer" in prompt
        assert "pr-merge" not in prompt


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
