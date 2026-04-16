#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Static grep tests for standing-teammate prose in Claude runtime adapter + shared-core.
# ABOUTME: Covers AC-8 (adapter prose), AC-9 (shared-core concept), AC-10 (FO routing prose).

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_RUNTIME = REPO_ROOT / "skills" / "first-officer" / "references" / "claude-first-officer-runtime.md"
SHARED_CORE = REPO_ROOT / "skills" / "first-officer" / "references" / "first-officer-shared-core.md"


def read(path: Path) -> str:
    return path.read_text()


class TestClaudeAdapterProse:
    """AC-8: Claude runtime adapter documents the standing teammate spawn pass."""

    def test_heading_present(self):
        text = read(CLAUDE_RUNTIME)
        assert re.search(r"^### Standing teammate spawn pass$", text, re.MULTILINE)

    def test_helper_invocation_mentioned(self):
        text = read(CLAUDE_RUNTIME)
        assert "claude-team spawn-standing" in text

    def test_verbatim_discipline_phrasing(self):
        """Same 'forward verbatim' discipline used for claude-team build output."""
        text = read(CLAUDE_RUNTIME)
        assert re.search(r"[Ff]orward.*verbatim", text)

    def test_already_alive_status_handling(self):
        text = read(CLAUDE_RUNTIME)
        assert "already-alive" in text


class TestSharedCoreConcept:
    """AC-9: shared-core has a top-level `## Standing Teammates` concept section."""

    def test_section_heading_present(self):
        text = read(SHARED_CORE)
        assert re.search(r"^## Standing Teammates$", text, re.MULTILINE)

    def test_first_boot_wins_anchor(self):
        text = read(SHARED_CORE)
        assert "first-boot-wins" in text

    def test_team_scope_lifecycle_anchor(self):
        text = read(SHARED_CORE)
        assert "team-scope lifecycle" in text

    def test_routing_contract_anchor(self):
        text = read(SHARED_CORE)
        assert "routing contract" in text

    def test_declaration_format_anchor(self):
        text = read(SHARED_CORE)
        assert "declaration format" in text


class TestFORoutingProse:
    """AC-10: shared-core Dispatch section mentions comm-officer + lists out-of-scope cases."""

    def test_comm_officer_mentioned(self):
        text = read(SHARED_CORE)
        assert "comm-officer" in text

    def test_captain_chat_out_of_scope(self):
        text = read(SHARED_CORE)
        # The routing prose MUST explicitly exclude live captain-chat replies.
        assert re.search(r"out.?of.?scope.*captain-chat", text, re.IGNORECASE | re.DOTALL) or \
               re.search(r"[Oo]ut of scope[^\n]*captain[- ]chat", text)

    def test_operational_statuses_out_of_scope(self):
        text = read(SHARED_CORE)
        assert "operational statuses" in text or "short operational" in text

    def test_member_exists_check_mentioned(self):
        text = read(SHARED_CORE)
        assert "member_exists" in text


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
