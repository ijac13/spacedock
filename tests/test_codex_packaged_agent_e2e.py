# ABOUTME: Direct E2E proof for reusable packaged workers and explicit shutdown in the Codex Spacedock prototype.
# ABOUTME: Runs Codex FO on a packaged-agent variant of the keepalive fixture and validates worker reuse / shutdown.

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    CodexLogParser,
    git_add_commit,
    run_codex_first_officer,
    setup_fixture,
)


@pytest.mark.xfail(reason="pending #154 — test assertions target `agents/first-officer.md` but post-#085 skill-preload the content lives in the skill/references layer", strict=False)
@pytest.mark.live_codex
def test_codex_packaged_agent_e2e(test_project):
    """Codex FO reuses packaged workers and honors explicit shutdown."""
    t = test_project

    print("--- Phase 1: Set up packaged keepalive fixture ---")
    workflow_dir = setup_fixture(t, "keepalive-pipeline", "packaged-agent-pipeline")

    readme_path = workflow_dir / "README.md"
    readme_text = readme_path.read_text()
    readme_text = readme_text.replace(
        "    - name: implementation\n      worktree: true\n",
        "    - name: implementation\n      worktree: true\n      agent: spacedock:ensign\n",
    )
    readme_text = readme_text.replace(
        "    - name: validation\n      worktree: true\n      fresh: true\n      feedback-to: implementation\n      gate: true\n",
        "    - name: validation\n      worktree: true\n      fresh: true\n      feedback-to: implementation\n      gate: true\n      agent: spacedock:ensign\n",
    )
    readme_path.write_text(readme_text)
    git_add_commit(t.test_project_dir, "setup: codex packaged keepalive fixture")

    t.check("fixture explicitly declares spacedock packaged agent", "agent: spacedock:ensign" in readme_text)
    t.check_cmd(
        "status script runs without errors",
        [
            "python3",
            str(t.repo_root / "skills" / "commission" / "bin" / "status"),
            "--workflow-dir", "packaged-agent-pipeline",
        ],
        cwd=t.test_project_dir,
    )
    status_result = subprocess.run(
        [
            "python3",
            str(t.repo_root / "skills" / "commission" / "bin" / "status"),
            "--workflow-dir", "packaged-agent-pipeline", "--next",
        ],
        capture_output=True, text=True, cwd=t.test_project_dir, check=True,
    )
    t.check("status --next detects dispatchable entity",
            "keepalive-test-task" in status_result.stdout)
    print()

    print("--- Phase 2: Run Codex first officer ---")
    fo_exit = run_codex_first_officer(
        t, "packaged-agent-pipeline",
        run_goal="Process only the entity `keepalive-test-task`.",
        timeout_s=420,
    )
    t.check("Codex launcher exited cleanly", fo_exit == 0)
    print()

    print("--- Phase 3: Validate explicit packaged-agent path ---")
    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    fo_text = log.full_text()
    worker_messages = log.completed_agent_messages()
    invocation_text = (t.log_dir / "codex-fo-invocation.txt").read_text()
    t.check("harness invoked the spacedock first officer skill",
            "spacedock:first-officer" in invocation_text)
    t.check("FO or worker output mentions spacedock packaged id",
            bool(re.search(r"spacedock:ensign", fo_text)))
    t.check("FO keeps packaged logical id while dispatch stays on shared safe naming",
            "spacedock:ensign" in fo_text and "spacedock-ensign" in fo_text)
    t.check("FO spawned workers for the packaged agent path", log.spawn_count() >= 2)
    t.check("workers completed and returned results", len(worker_messages) >= 2)
    t.check("completed implementation worker received routed follow-up through send_input",
            bool(re.search(r"send_input", fo_text, re.IGNORECASE)))
    t.check("reused worker is described as active again after follow-up",
            bool(re.search(r"active again", fo_text, re.IGNORECASE)))
    t.check("critical-path reused follow-up is explicitly awaited with wait_agent",
            bool(re.search(r"critical path", fo_text, re.IGNORECASE))
            and bool(re.search(r"wait_agent|wait", fo_text, re.IGNORECASE)))

    send_input_target = ""
    reused_wait_target = ""
    reused_wait_message = ""
    follow_up_commit = ""
    follow_up_wait_after_send = False
    for raw_line in log.raw_lines:
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        item = entry.get("item", {})
        if not isinstance(item, dict) or item.get("type") != "collab_tool_call":
            continue
        tool = item.get("tool")
        receiver_ids = item.get("receiver_thread_ids") or []
        if tool == "send_input" and receiver_ids:
            send_input_target = receiver_ids[0]
            continue
        if tool == "wait" and send_input_target and receiver_ids and receiver_ids[0] == send_input_target:
            follow_up_wait_after_send = True
            reused_wait_target = receiver_ids[0]
            reused_wait_message = (
                (item.get("agents_states") or {}).get(reused_wait_target, {}).get("message") or ""
            )
            match = re.search(r"committed .* at `([0-9a-f]{7,40})`", reused_wait_message)
            if match:
                follow_up_commit = match.group(1)

    t.check("reused worker is awaited after send_input on the same handle", follow_up_wait_after_send)
    t.check("reused wait stays on the send_input target handle",
            reused_wait_target == send_input_target and bool(send_input_target))
    t.check("reused wait returns new completion evidence rather than the stale implementation summary",
            "Still needs attention: nothing." not in reused_wait_message)
    t.check("reused completion reports a new follow-up commit",
            bool(follow_up_commit and follow_up_commit != "9e941a7"))
    t.check("reused-worker follow-up does not spawn a replacement worker",
            not bool(re.search(r"replacement dispatch|spawning a replacement|spawn a replacement", fo_text, re.IGNORECASE)))
    t.check("Codex path explicitly shut down a no-longer-needed worker",
            bool(re.search(r"shutdown", fo_text, re.IGNORECASE)))
    t.check("shutdown happens only after the reused cycle completes",
            bool(re.search(r"reused cycle.*shutdown|follow-up.*shutdown|shutdown.*no longer needed", fo_text, re.IGNORECASE)))
    t.check("Codex path reports a human-readable worker label",
            bool(re.search(r"\b001-(impl|implementation|val|validation)/[A-Za-z0-9._-]+", fo_text)))

    entity_text = (workflow_dir / "keepalive-test-task.md").read_text()
    worktree_match = re.search(r"^worktree:\s*(.+)$", entity_text, re.MULTILINE)
    worktree_value = worktree_match.group(1).strip() if worktree_match else ""
    t.check("safe packaged worker key appears in worktree path", "spacedock-ensign" in worktree_value)
    t.check("raw packaged worker id does not leak into worktree path", "spacedock:ensign" not in worktree_value)

    branches = subprocess.run(
        ["git", "branch", "--list"],
        capture_output=True, text=True, cwd=t.test_project_dir, check=True,
    ).stdout
    t.check("safe packaged worker key appears in branch names", "spacedock-ensign/" in branches)
    t.check("raw packaged worker id does not leak into branch names", "spacedock:ensign" not in branches)

    worktree_path = t.test_project_dir / worktree_value
    greeting_text = (worktree_path / "greeting.txt").read_text()
    t.check("reused implementation follow-up applied the validator-requested fix",
            greeting_text == "Goodbye, World!")

    t.finish()

