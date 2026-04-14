#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit tests for helper functions in test_feedback_keepalive.py.
# ABOUTME: Guards stage-detection regex against regression when FO prompt formatting changes.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "scripts"))

from test_lib import _agent_targets_stage


class TestAgentTargetsStage:
    def test_matches_plain_stage_header(self):
        """Helper-format prompt: 'Stage: implementation' on its own line."""
        agent = {
            "name": "",
            "prompt": "You are working on: Task\n\nStage: implementation\n\n### Stage definition:\n",
        }
        assert _agent_targets_stage(agent, "implementation")

    def test_matches_markdown_bold_stage_header(self):
        """FO hand-assembled format: '**Stage:** implementation'."""
        agent = {
            "name": "",
            "prompt": "**Entity:** task (ID 001)\n\n**Stage:** implementation\n\n### Stage definition:\n",
        }
        assert _agent_targets_stage(agent, "implementation")

    def test_matches_plain_stage_validation(self):
        agent = {
            "name": "",
            "prompt": "You are working on: Task\n\nStage: validation\n",
        }
        assert _agent_targets_stage(agent, "validation")

    def test_matches_markdown_bold_stage_validation(self):
        agent = {
            "name": "",
            "prompt": "**Stage:** validation\n",
        }
        assert _agent_targets_stage(agent, "validation")

    def test_matches_when_name_contains_stage(self):
        """Falls back to name-field match when prompt doesn't have a Stage: line."""
        agent = {
            "name": "spacedock-ensign-my-task-implementation",
            "prompt": "some prompt without stage header",
        }
        assert _agent_targets_stage(agent, "implementation")

    def test_rejects_when_neither_name_nor_prompt_matches(self):
        agent = {
            "name": "unrelated-name",
            "prompt": "no stage line here",
        }
        assert not _agent_targets_stage(agent, "implementation")

    def test_rejects_wrong_stage_in_prompt(self):
        """Plain-format prompt that targets a different stage must not match."""
        agent = {
            "name": "",
            "prompt": "Stage: validation\n",
        }
        assert not _agent_targets_stage(agent, "implementation")

    def test_rejects_wrong_stage_in_markdown_bold(self):
        """Markdown-bold prompt that targets a different stage must not match."""
        agent = {
            "name": "",
            "prompt": "**Stage:** validation\n",
        }
        assert not _agent_targets_stage(agent, "implementation")

    def test_ignores_inline_stage_mention(self):
        """A 'stage: X' substring mid-sentence must not count as a dispatch target."""
        agent = {
            "name": "",
            "prompt": "The validation stage: implementation depends on the prior work.\n",
        }
        assert not _agent_targets_stage(agent, "implementation")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
