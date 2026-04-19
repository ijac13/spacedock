#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Failing tests for #201 FO bootstrap discipline (TeamCreate-skip in teams-mode sessions).
# ABOUTME: Landed pre-fix per TDD: each test must FAIL against main HEAD and PASS after the L1-L5 fixes.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_TEAM = REPO_ROOT / "skills" / "commission" / "bin" / "claude-team"
STATUS_TEMPLATE = REPO_ROOT / "skills" / "commission" / "bin" / "status"
RUNTIME_PROSE = REPO_ROOT / "skills" / "first-officer" / "references" / "claude-first-officer-runtime.md"
COMMISSION_SKILL = REPO_ROOT / "skills" / "commission" / "SKILL.md"
STANDING_FIXTURE_MOD = REPO_ROOT / "tests" / "fixtures" / "standing-teammate" / "_mods" / "echo-agent.md"


README_WITH_STAGES = """---
commissioned-by: spacedock@test
entity-label: task
stages:
  defaults:
    worktree: false
  states:
    - name: backlog
      initial: true
    - name: done
      terminal: true
---

# Test Workflow

## Stages

### `backlog`
- **Inputs:** seed
- **Outputs:** seed

### `done`
Terminal.
"""


def _build_status_script(tmp_path: Path) -> Path:
    """Materialize the status template (variable substitution) into a runnable script."""
    content = STATUS_TEMPLATE.read_text()
    content = content.replace("{spacedock_version}", "0.0.0-test")
    content = content.replace("{entity_label}", "task")
    content = content.replace("{stage1}, {stage2}, ..., {last_stage}", "backlog, done")
    script = tmp_path / "status"
    script.write_text(content)
    script.chmod(0o755)
    return script


def _make_minimal_workflow(tmp_path: Path) -> Path:
    wf = tmp_path / "workflow"
    wf.mkdir()
    (wf / "README.md").write_text(README_WITH_STAGES)
    (wf / "task.md").write_text(
        "---\nid: 001\ntitle: Task\nstatus: backlog\n---\n\nseed.\n"
    )
    return wf


def _path_without_gh() -> str:
    dirs = os.environ.get("PATH", "").split(os.pathsep)
    filtered = [d for d in dirs if not os.path.isfile(os.path.join(d, "gh"))]
    return os.pathsep.join(filtered)


# -------------------------------------------------------------------
# L1 — status --boot must surface TEAM_STATE
# -------------------------------------------------------------------
class TestStatusBootTeamState:
    """L1: `status --boot` output includes a TEAM_STATE section.

    Today: output has MODS / NEXT_ID / ORPHANS / PR_STATE / DISPATCHABLE but no TEAM_STATE.
    Post-fix: a TEAM_STATE header with at minimum a `present: true|false` line appears.
    """

    def test_status_boot_has_team_state_section(self, tmp_path):
        script = _build_status_script(tmp_path)
        wf = _make_minimal_workflow(tmp_path)

        env = {**os.environ, "PATH": _path_without_gh()}
        result = subprocess.run(
            [str(script), "--boot", "--workflow-dir", str(wf)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        lines = result.stdout.splitlines()
        assert "TEAM_STATE" in lines, (
            f"Expected TEAM_STATE header in --boot output, got sections: "
            f"{[l for l in lines if l and not l.startswith(' ') and ':' not in l][:10]}"
        )
        # Header must be followed by a structured `present:` line (true|false).
        idx = lines.index("TEAM_STATE")
        body = lines[idx + 1 : idx + 4]
        joined = "\n".join(body)
        assert "present:" in joined, (
            f"TEAM_STATE section must have a `present:` line; got body: {body!r}"
        )


# -------------------------------------------------------------------
# L2 — claude-team build must warn/refuse first bare dispatch without TeamCreate evidence
# -------------------------------------------------------------------
class TestBuildWarnsOnBareWithoutTeamEvidence:
    """L2: `claude-team build` signals on `bare_mode: true` with null team and no TeamCreate evidence.

    Today: silent exit 0 with valid dispatch JSON.
    Post-fix: either non-zero exit OR stderr warning naming TeamCreate/bare omission.
    """

    def test_build_signals_on_bare_without_team_evidence(self, tmp_path):
        wf = _make_minimal_workflow(tmp_path)
        inp = {
            "schema_version": 1,
            "entity_path": str(wf / "task.md"),
            "workflow_dir": str(wf),
            "stage": "backlog",
            "checklist": ["1. Do it"],
            "team_name": None,
            "bare_mode": True,
        }
        home = tmp_path / "home"
        home.mkdir()
        env = {**os.environ, "HOME": str(home)}
        result = subprocess.run(
            [sys.executable, str(CLAUDE_TEAM), "build", "--workflow-dir", str(wf)],
            input=json.dumps(inp),
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=env,
        )

        signaled_nonzero = result.returncode != 0
        stderr_lower = result.stderr.lower()
        signaled_stderr = any(
            token in stderr_lower
            for token in ("teamcreate", "bare", "intentional-bare", "team evidence")
        )

        assert signaled_nonzero or signaled_stderr, (
            f"Expected non-zero exit OR stderr warning naming TeamCreate/bare; "
            f"got exit={result.returncode}, stderr={result.stderr!r}"
        )


# -------------------------------------------------------------------
# L3 — FO runtime adapter prose must name TeamCreate Step 1 + name spawn-standing in sequencing rule
# -------------------------------------------------------------------
class TestRuntimeProseTeamCreateFirst:
    """L3: runtime adapter prose presents TeamCreate as the first team-mode tool call.

    Today: TeamCreate is step 2-3 of Team Creation (step 1 is "Derive project name").
    The `Sequencing rule` at line ~69 names TeamCreate/TeamDelete/Agent but NOT `spawn-standing`.
    Post-fix: TeamCreate surfaces as Step 1, and the sequencing rule names spawn-standing.
    """

    def test_prose_names_teamcreate_as_step_1(self):
        text = RUNTIME_PROSE.read_text()
        # Expect an explicit "Step 1" / "1." where TeamCreate (or its probe) is the imperative.
        # Post-fix the Team Creation section should begin with a TeamCreate-naming Step 1,
        # not a "Derive project name" Step 1.
        lines = text.splitlines()
        try:
            section_idx = next(
                i for i, ln in enumerate(lines) if ln.strip().startswith("## Team Creation")
            )
        except StopIteration:
            pytest.fail("Team Creation section not found in runtime prose")

        # First numbered item after the section header
        first_step = None
        for ln in lines[section_idx : section_idx + 15]:
            s = ln.strip()
            if s.startswith("1. "):
                first_step = s
                break
        assert first_step is not None, "No `1.` step found near Team Creation header"
        assert "TeamCreate" in first_step or "team" in first_step.lower() and "probe" in first_step.lower(), (
            f"Team Creation Step 1 must name TeamCreate (or the TeamCreate probe); "
            f"got: {first_step!r}"
        )

    def test_sequencing_rule_names_spawn_standing(self):
        text = RUNTIME_PROSE.read_text()
        # Find the Sequencing rule block; assert spawn-standing is named alongside
        # TeamCreate/TeamDelete/Agent in its must-not-combine list.
        idx = text.find("Sequencing rule")
        assert idx != -1, "No Sequencing rule block found"
        # Take the paragraph after "Sequencing rule" (until next blank line)
        tail = text[idx : idx + 600]
        assert "spawn-standing" in tail, (
            f"Sequencing rule must name `spawn-standing` as a team-mode call gated by "
            f"TeamCreate; block excerpt: {tail!r}"
        )


# -------------------------------------------------------------------
# L4 — commission Phase 3 must have an explicit Team Probe step
# -------------------------------------------------------------------
class TestCommissionPhase3TeamProbe:
    """L4: commission skill Phase 3 contains an explicit Team Probe step.

    Today: Phase 3 Step 2 says "Execute the first-officer startup procedure directly."
    Post-fix: a `Team Probe` step (or `ToolSearch.*TeamCreate` imperative) appears in Phase 3.
    """

    def test_phase3_has_team_probe(self):
        text = COMMISSION_SKILL.read_text()
        # Isolate Phase 3 through the end of its block (next ## or eof).
        idx = text.find("## Phase 3")
        assert idx != -1, "## Phase 3 heading missing"
        tail = text[idx:]
        next_phase = tail.find("\n## ", 5)
        phase3_block = tail if next_phase == -1 else tail[:next_phase]

        has_probe = "Team Probe" in phase3_block
        has_toolsearch = "ToolSearch" in phase3_block and "TeamCreate" in phase3_block
        assert has_probe or has_toolsearch, (
            "Phase 3 must contain a `Team Probe` step OR an explicit "
            "`ToolSearch(query=\"select:TeamCreate\")` imperative."
        )


# -------------------------------------------------------------------
# L5 — spawn-standing must reject empty/none team name
# -------------------------------------------------------------------
class TestSpawnStandingRejectsEmptyTeam:
    """L5: `claude-team spawn-standing --team none|""` exits non-zero with stderr.

    Today: exits 0 and emits spec JSON with literal `"team_name": "none"` (or "").
    This is exactly the PR #132 CI failure shape.
    """

    @pytest.mark.parametrize("bad_team", ["none", "", "None"])
    def test_rejects_bad_team_name(self, tmp_path, bad_team):
        assert STANDING_FIXTURE_MOD.is_file(), (
            f"Fixture mod missing: {STANDING_FIXTURE_MOD}"
        )
        env = {**os.environ, "HOME": str(tmp_path)}
        result = subprocess.run(
            [
                sys.executable,
                str(CLAUDE_TEAM),
                "spawn-standing",
                "--mod",
                str(STANDING_FIXTURE_MOD),
                "--team",
                bad_team,
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit for --team {bad_team!r}; "
            f"got exit=0 with stdout: {result.stdout!r}"
        )
        stderr_lower = result.stderr.lower()
        assert any(
            token in stderr_lower
            for token in ("team name", "teamcreate", "requires a real team")
        ), f"stderr should name the team-name requirement; got: {result.stderr!r}"
