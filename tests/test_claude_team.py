#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit tests for the claude-team script's context-budget subcommand.
# ABOUTME: Tests token extraction, model mapping, threshold logic, and error cases.

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "skills" / "commission" / "bin" / "claude-team"


def make_jsonl_fixture(
    tmp_path: Path,
    agent_name: str,
    usage: dict | None = None,
) -> tuple[Path, Path]:
    """Create a fake subagent jsonl + meta.json pair.

    Returns (meta_path, jsonl_path).
    """
    projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
    projects_dir.mkdir(parents=True, exist_ok=True)

    meta_path = projects_dir / "agent-abc123.meta.json"
    jsonl_path = projects_dir / "agent-abc123.jsonl"

    meta_path.write_text(json.dumps({"agentType": agent_name}))

    lines = []
    # A user entry
    lines.append(json.dumps({"type": "human", "message": {"role": "user", "content": "hello"}}))
    # An assistant entry with usage
    if usage is not None:
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "usage": usage},
        }))
    jsonl_path.write_text("\n".join(lines) + "\n")

    return meta_path, jsonl_path


def make_team_config(
    tmp_path: Path,
    team_name: str,
    member_name: str,
    model: str,
) -> Path:
    """Create a fake team config with one member."""
    teams_dir = tmp_path / ".claude" / "teams" / team_name
    teams_dir.mkdir(parents=True, exist_ok=True)

    config_path = teams_dir / "config.json"
    config_path.write_text(json.dumps({
        "name": team_name,
        "members": [
            {
                "name": "team-lead",
                "agentType": "team-lead",
                "model": "claude-opus-4-6[1m]",
            },
            {
                "name": member_name,
                "agentType": "spacedock:ensign",
                "model": model,
            },
        ],
    }))
    return config_path


def run_context_budget(tmp_path: Path, name: str) -> subprocess.CompletedProcess:
    """Run the claude-team context-budget subcommand with HOME overridden."""
    env = {**os.environ, "HOME": str(tmp_path)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "context-budget", "--name", name],
        capture_output=True,
        text=True,
        env=env,
    )


class TestContextBudgetBasic:
    """Basic context-budget functionality."""

    def test_outputs_valid_json(self, tmp_path):
        usage = {
            "input_tokens": 5000,
            "cache_creation_input_tokens": 3000,
            "cache_read_input_tokens": 2000,
        }
        make_jsonl_fixture(tmp_path, "spacedock-ensign-foo-impl", usage)
        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["name"] == "spacedock-ensign-foo-impl"
        assert data["resident_tokens"] == 10000
        assert data["model"] == "claude-opus-4-6"
        assert data["context_limit"] == 200000
        assert data["usage_pct"] == pytest.approx(5.0)
        assert data["threshold_pct"] == 60
        assert data["reuse_ok"] is True

    def test_uses_last_assistant_entry(self, tmp_path):
        """When multiple assistant entries exist, use the last one's usage."""
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        meta_path = projects_dir / "agent-abc123.meta.json"
        jsonl_path = projects_dir / "agent-abc123.jsonl"

        meta_path.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))

        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 1000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            }}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 50000, "cache_creation_input_tokens": 30000, "cache_read_input_tokens": 40000,
            }}}),
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["resident_tokens"] == 120000


class TestThresholdBoundary:
    """60% threshold boundary tests."""

    def _make_at_percentage(self, tmp_path, pct: float, model: str = "claude-opus-4-6"):
        """Create fixtures that produce a specific usage percentage."""
        context_limit = 200000
        resident_tokens = int(context_limit * pct / 100)
        usage = {
            "input_tokens": resident_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        make_jsonl_fixture(tmp_path, "spacedock-ensign-foo-impl", usage)
        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", model)

    def test_59_percent_reuse_ok(self, tmp_path):
        self._make_at_percentage(tmp_path, 59.0)
        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["reuse_ok"] is True

    def test_60_percent_reuse_ok(self, tmp_path):
        self._make_at_percentage(tmp_path, 60.0)
        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["reuse_ok"] is True

    def test_61_percent_reuse_not_ok(self, tmp_path):
        self._make_at_percentage(tmp_path, 61.0)
        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["reuse_ok"] is False


class TestModelMapping:
    """Model-to-context-limit mapping tests."""

    @pytest.mark.parametrize("model,expected_limit", [
        ("claude-opus-4-6", 200000),
        ("claude-opus-4-6[1m]", 1000000),
        ("claude-sonnet-4-6", 200000),
        ("claude-haiku-4-5-20251001", 200000),
        ("unknown-model-xyz", 200000),
    ])
    def test_model_context_limits(self, tmp_path, model, expected_limit):
        usage = {
            "input_tokens": 100000,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        make_jsonl_fixture(tmp_path, "spacedock-ensign-foo-impl", usage)
        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", model)

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["context_limit"] == expected_limit
        assert data["model"] == model


class TestErrorCases:
    """Error handling tests."""

    def test_missing_jsonl(self, tmp_path):
        """No matching subagent jsonl found."""
        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")
        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode != 0

    def test_no_assistant_turns(self, tmp_path):
        """Jsonl exists but has no assistant entries with usage."""
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        meta_path = projects_dir / "agent-abc123.meta.json"
        jsonl_path = projects_dir / "agent-abc123.jsonl"

        meta_path.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))
        jsonl_path.write_text(json.dumps({"type": "human", "message": {"role": "user"}}) + "\n")

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode != 0

    def test_no_subcommand(self, tmp_path):
        """Running without a subcommand should fail."""
        env = {**os.environ, "HOME": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0

    def test_missing_name_flag(self, tmp_path):
        """Running context-budget without --name should fail."""
        env = {**os.environ, "HOME": str(tmp_path)}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "context-budget"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0


class TestPeakTokens:
    """Peak-token extraction: scan backward past zero-usage final turns."""

    def test_dead_ensign_zero_final_turn_returns_peak(self, tmp_path):
        """An ensign that died mid-turn has a zero-usage final assistant entry.

        The script must report the last non-zero peak, not zero.
        """
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        meta_path = projects_dir / "agent-abc123.meta.json"
        jsonl_path = projects_dir / "agent-abc123.jsonl"

        meta_path.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))

        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 10000, "cache_creation_input_tokens": 20000, "cache_read_input_tokens": 30000,
            }}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 50000, "cache_creation_input_tokens": 60000, "cache_read_input_tokens": 65000,
            }}}),
            # Dead turn: all zeros
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            }}}),
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        # Second turn: 50000 + 60000 + 65000 = 175000 on a 200000-limit -> 87.5%
        assert data["resident_tokens"] == 175000
        assert data["usage_pct"] == pytest.approx(87.5)
        assert data["reuse_ok"] is False

    def test_live_ensign_last_turn_is_peak(self, tmp_path):
        """A healthy ensign's last turn has non-zero usage; returns that value."""
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        meta_path = projects_dir / "agent-abc123.meta.json"
        jsonl_path = projects_dir / "agent-abc123.jsonl"

        meta_path.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))

        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 1000, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 500,
            }}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 5000, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 2000,
            }}}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 20000, "cache_creation_input_tokens": 15000, "cache_read_input_tokens": 15000,
            }}}),
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        # Last turn: 20000 + 15000 + 15000 = 50000 on 200000 -> 25%
        assert data["resident_tokens"] == 50000
        assert data["usage_pct"] == pytest.approx(25.0)
        assert data["reuse_ok"] is True

    def test_multiple_trailing_zero_turns(self, tmp_path):
        """Multiple trailing zero-usage assistant turns still return the real peak."""
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        meta_path = projects_dir / "agent-abc123.meta.json"
        jsonl_path = projects_dir / "agent-abc123.jsonl"

        meta_path.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))

        zero_turn = json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
            "input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        }}})
        lines = [
            json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
                "input_tokens": 40000, "cache_creation_input_tokens": 40000, "cache_read_input_tokens": 40000,
            }}}),
            zero_turn,
            zero_turn,
            zero_turn,
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["resident_tokens"] == 120000


class TestMostRecentMatch:
    """When multiple meta.json files match, use most recently modified."""

    def test_picks_most_recent(self, tmp_path):
        projects_dir = tmp_path / ".claude" / "projects" / "test-project" / "session-1" / "subagents"
        projects_dir.mkdir(parents=True, exist_ok=True)

        # Older file
        old_meta = projects_dir / "agent-old111.meta.json"
        old_jsonl = projects_dir / "agent-old111.jsonl"
        old_meta.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))
        old_jsonl.write_text(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "usage": {
                "input_tokens": 1000,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }},
        }) + "\n")
        # Set older mtime
        os.utime(old_meta, (1000000, 1000000))

        # Newer file
        new_meta = projects_dir / "agent-new222.meta.json"
        new_jsonl = projects_dir / "agent-new222.jsonl"
        new_meta.write_text(json.dumps({"agentType": "spacedock-ensign-foo-impl"}))
        new_jsonl.write_text(json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "usage": {
                "input_tokens": 99000,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }},
        }) + "\n")
        # Set newer mtime
        os.utime(new_meta, (2000000, 2000000))

        make_team_config(tmp_path, "test-team", "spacedock-ensign-foo-impl", "claude-opus-4-6")

        result = run_context_budget(tmp_path, "spacedock-ensign-foo-impl")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["resident_tokens"] == 99000


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
