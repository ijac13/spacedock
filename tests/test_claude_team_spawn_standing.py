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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
