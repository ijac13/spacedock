# ABOUTME: E2E regression test for team-mode dispatch completion-signal in the FO template.
# ABOUTME: Drives an FO through a team-dispatched worktree stage and asserts status advances.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    LogParser,
    emit_skip_result,
    git_add_commit,
    install_agents,
    probe_claude_runtime,
    read_entity_frontmatter,
    run_first_officer,
    setup_fixture,
)


# #154 reclassification: this test has no static FO content reads — its 1/5 inner failure is
# runtime entity-advancement / SendMessage signaling, not the post-#085 content-home drift #154
# targets. The xfail was misattributed by the #148 cycle-6 blanket marker pass; if the test fails
# at validation, surface it under a fresh task id.
@pytest.mark.live_claude
def test_dispatch_completion_signal(test_project, model, effort):
    """Team-mode dispatch: ensign SendMessage(team-lead, "Done: ..."); FO advances status."""
    t = test_project

    print("--- Phase 1: Set up test project from fixture ---")
    setup_fixture(t, "completion-signal-pipeline", "completion-signal-pipeline")
    install_agents(t, include_ensign=True)
    git_add_commit(t.test_project_dir, "setup: completion-signal regression fixture")
    status_cmd = [
        "python3",
        str(t.repo_root / "skills" / "commission" / "bin" / "status"),
        "--workflow-dir", "completion-signal-pipeline",
    ]
    t.check_cmd("status script runs without errors", status_cmd, cwd=t.test_project_dir)
    print()

    print("--- Phase 2: Run first officer (claude) ---")
    ok, reason = probe_claude_runtime(model)
    if not ok:
        emit_skip_result(
            f"live Claude runtime unavailable before FO dispatch: {reason}. "
            "This environment cannot currently prove or disprove the haiku regression."
        )

    abs_workflow = t.test_project_dir / "completion-signal-pipeline"
    fo_exit = run_first_officer(
        t,
        (
            f"Process all tasks through the workflow at {abs_workflow}/ to terminal completion. "
            "Drive every dispatchable task through its stages until the entity reaches the done "
            "stage and the local merge path archives it. Stop once the entity is archived."
        ),
        agent_id="spacedock:first-officer",
        extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "3.00"],
    )
    if fo_exit != 0:
        print(f"  (first officer exit code {fo_exit} — may be expected for the pre-fix hang case)")
    t.check("first officer exited cleanly within timeout (no pre-fix hang)", fo_exit == 0)

    print()
    print("--- Phase 3: Validation ---")
    print()
    print("[Entity Advancement]")
    entity_main = t.test_project_dir / "completion-signal-pipeline" / "completion-signal-task.md"
    entity_archive = t.test_project_dir / "completion-signal-pipeline" / "_archive" / "completion-signal-task.md"

    log = LogParser(t.log_dir / "fo-log.jsonl")
    log.write_agent_calls(t.log_dir / "agent-calls.txt")
    log.write_fo_texts(t.log_dir / "fo-texts.txt")
    log.write_agent_prompt(t.log_dir / "agent-prompts.txt")

    agent_calls = log.agent_calls()
    ensign_calls = [c for c in agent_calls if "ensign" in c["subagent_type"]]
    t.check("FO dispatched at least one ensign", len(ensign_calls) > 0)

    if entity_archive.is_file():
        t.pass_("entity advanced and was archived without manual captain intervention")
    elif entity_main.is_file():
        fm = read_entity_frontmatter(entity_main)
        status_val = fm.get("status", "")
        if status_val == "done":
            t.pass_(f"entity advanced to terminal stage (status: {status_val})")
        else:
            t.fail(
                f"entity did NOT advance past dispatched stage (status: {status_val!r}). "
                "This reproduces the bug: team-dispatched ensign sent no completion signal, "
                "so the FO's DISPATCH IDLE GUARDRAIL waited forever."
            )
    else:
        t.fail("entity file missing from both main and _archive (unexpected state)")

    # Sanity check: when the FO dispatched in team mode, the ensign prompt must carry
    # the SendMessage completion-signal instruction. In bare mode (no team_name on the
    # Agent call) the signal is intentionally absent — Agent() blocks and returns
    # inline, so SendMessage is unnecessary and would fail (no team to message).
    last_team_mode_prompt = next(
        (c["prompt"] for c in reversed(ensign_calls) if c.get("team_name")),
        None,
    )
    if last_team_mode_prompt is None:
        t.pass_(
            "FO dispatched in bare mode (no team_name on Agent call); SendMessage is "
            "unnecessary since Agent() returns inline. Entity-advancement checks above "
            "cover the end-to-end pre-fix hang regression."
        )
    elif 'SendMessage(to="team-lead"' in last_team_mode_prompt:
        t.pass_("team-mode ensign prompt carries SendMessage completion-signal instruction")
    else:
        t.fail(
            'team-mode ensign prompt does NOT carry SendMessage(to="team-lead", ...) '
            "instruction — the FO dropped the completion signal from its dispatch template."
        )

    t.finish()

