# ABOUTME: Direct E2E proof for reusable packaged workers and explicit shutdown in the Codex Spacedock prototype.
# ABOUTME: Runs Codex FO on a packaged-agent variant of the keepalive fixture and validates worker reuse / shutdown.

from __future__ import annotations

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


def _completion_commit_hash(message: str) -> str:
    for pattern in (
        r"New commit:\s*`?([0-9a-f]{7,40})`?",
        r"New commit id:\s*`?([0-9a-f]{7,40})`?",
        r"New commit hash:\s*`?([0-9a-f]{7,40})`?",
        r"Final commit:\s*`?([0-9a-f]{7,40})`?",
        r"Created commit\s*`?([0-9a-f]{7,40})`?",
        r"Commit hash:\s*`?([0-9a-f]{7,40})`?",
        r"Commit:\s*`?([0-9a-f]{7,40})`?",
        r"with hash\s*`?([0-9a-f]{7,40})`?",
        r"committed .* at `([0-9a-f]{7,40})`",
    ):
        match = re.search(pattern, message)
        if match:
            return match.group(1)
    if re.search(r"commits? were created as", message, re.IGNORECASE):
        hashes = re.findall(r"`([0-9a-f]{7,40})`", message)
        if hashes:
            return hashes[-1]
    hashes = re.findall(r"\b[0-9a-f]{7,40}\b", message)
    if hashes:
        return hashes[-1]
    return ""


def test_completion_commit_hash_accepts_new_commit_id_wording():
    message = "New commit id: `98a571e` (`implementation: record keepalive feedback follow-up`)."

    assert _completion_commit_hash(message) == "98a571e"


def test_completion_commit_hash_accepts_new_commit_wording():
    message = "New commit: `14cafb9` (`implementation: finalize cycle 1 report`)"

    assert _completion_commit_hash(message) == "14cafb9"


def test_completion_commit_hash_accepts_multiple_created_commits_wording():
    message = (
        "Worker `spacedock:ensign` completed. Updated `greeting.txt` and the follow-up "
        "implementation/report commits were created as `80ecf32` and `6e98bc7`."
    )

    assert _completion_commit_hash(message) == "6e98bc7"


def test_completion_commit_hash_accepts_with_hash_wording():
    message = (
        "`greeting.txt` now contains exactly `Goodbye, World!`.\n\n"
        "Committed on `spacedock-ensign/keepalive-test-task` as "
        "`implementation: apply rejection follow-up` with hash `8dcce7a1e1f6c15a344e68a42a0ea04cc7d87b14`."
    )

    assert _completion_commit_hash(message) == "8dcce7a1e1f6c15a344e68a42a0ea04cc7d87b14"


def test_completion_commit_hash_accepts_created_commit_wording():
    message = (
        "`spacedock:ensign` completed.\n\n"
        "Created commit `bd314e559a4edd84f46a94c4e4635f7952cf2b88` with message "
        "`implementation: update greeting for validation gate`."
    )

    assert _completion_commit_hash(message) == "bd314e559a4edd84f46a94c4e4635f7952cf2b88"


def test_completion_commit_hash_accepts_new_commit_hash_wording():
    message = (
        "New commit hash: `f6878bf` (`implementation: record feedback cycle 1 report`); "
        "the content-fix commit it records is `ea6775c`."
    )

    assert _completion_commit_hash(message) == "f6878bf"


def _packaged_reuse_stop_ready(log_path: Path) -> bool:
    log = CodexLogParser(log_path)
    send_input_target = ""
    reused_wait_index = -1
    reused_wait_target = ""
    for idx, item in enumerate(log.collab_tool_calls()):
        tool = item.get("tool")
        receiver_ids = item.get("receiver_thread_ids") or []
        if tool == "send_input" and receiver_ids:
            send_input_target = receiver_ids[0]
            continue
        if tool == "wait" and send_input_target and receiver_ids and receiver_ids[0] == send_input_target:
            reused_wait_index = idx
            reused_wait_target = receiver_ids[0]
            continue
        if (
            reused_wait_index >= 0
            and idx > reused_wait_index
            and tool == "close_agent"
            and receiver_ids
            and receiver_ids[0] == reused_wait_target
        ):
            return True
    return False


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
        run_goal=(
            "Process only the entity `keepalive-test-task`. "
            "Drive it from backlog through implementation and validation. "
            "When validation recommends `REJECTED`, immediately record feedback cycle 1 on the "
            "FO-owned main-branch entity file, route the concrete fix request back to the kept-alive "
            "implementation handle via `send_input`, wait on that same handle for the routed follow-up "
            "completion, explicitly shut down both workers, and stop at that bounded routed-reuse outcome."
        ),
        timeout_s=900,
        stop_checker=_packaged_reuse_stop_ready,
    )
    t.check("Codex launcher exited cleanly", fo_exit == 0)
    print()

    print("--- Phase 3: Validate explicit packaged-agent path ---")
    log = CodexLogParser(t.log_dir / "codex-fo-log.txt")
    operator_messages = "\n".join(log.agent_message_texts())
    collab_calls = log.collab_tool_calls()
    spawn_prompts = "\n".join(
        call.get("prompt") or ""
        for call in collab_calls
        if call.get("tool") in {"spawn", "spawn_agent"}
    )
    worker_messages = log.completed_agent_messages()
    invocation_text = (t.log_dir / "codex-fo-invocation.txt").read_text()
    t.check("harness invoked the spacedock first officer skill",
            "spacedock:first-officer" in invocation_text)
    t.check("FO or worker output mentions spacedock packaged id",
            bool(re.search(r"spacedock:ensign", spawn_prompts)))
    t.check("FO keeps packaged logical id while dispatch stays on shared safe naming",
            "spacedock:ensign" in spawn_prompts and "spacedock-ensign" in spawn_prompts)
    t.check("FO spawned workers for the packaged agent path", log.spawn_count() >= 2)
    t.check("workers completed and returned results", len(worker_messages) >= 2)
    t.check("completed implementation worker received routed follow-up through send_input",
            any(call.get("tool") == "send_input" for call in collab_calls))
    t.check("reused worker is described as active again after follow-up",
            bool(re.search(r"active again", operator_messages, re.IGNORECASE)))
    t.check("critical-path reused follow-up is explicitly awaited with wait_agent",
            bool(re.search(r"critical path", operator_messages, re.IGNORECASE))
            and any(call.get("tool") == "wait" for call in collab_calls))

    send_input_index = -1
    send_input_target = ""
    reused_wait_target = ""
    reused_wait_message = ""
    follow_up_commit = ""
    follow_up_wait_after_send = False
    reused_wait_index = -1
    replacement_dispatch_after_send = False
    close_agent_after_reused_wait = False
    for idx, item in enumerate(collab_calls):
        tool = item.get("tool")
        receiver_ids = item.get("receiver_thread_ids") or []
        if tool == "send_input" and receiver_ids:
            send_input_index = idx
            send_input_target = receiver_ids[0]
            continue
        if tool == "wait" and send_input_target and receiver_ids and receiver_ids[0] == send_input_target:
            follow_up_wait_after_send = True
            reused_wait_index = idx
            reused_wait_target = receiver_ids[0]
            reused_wait_message = (
                (item.get("agents_states") or {}).get(reused_wait_target, {}).get("message") or ""
            )
            follow_up_commit = _completion_commit_hash(reused_wait_message)
            continue
        if (
            reused_wait_index >= 0
            and idx > reused_wait_index
            and tool == "close_agent"
            and receiver_ids
            and receiver_ids[0] == reused_wait_target
        ):
            close_agent_after_reused_wait = True
        if (
            send_input_index >= 0
            and idx > send_input_index
            and tool in {"spawn", "spawn_agent"}
            and re.search(r"stage_name:\s*implementation", item.get("prompt") or "", re.IGNORECASE)
            and "keepalive-test-task" in (item.get("prompt") or "")
        ):
            replacement_dispatch_after_send = True

    t.check("reused worker is awaited after send_input on the same handle", follow_up_wait_after_send)
    t.check("reused wait stays on the send_input target handle",
            reused_wait_target == send_input_target and bool(send_input_target))
    t.check("reused wait describes the routed feedback fix rather than only the original implementation",
            bool(re.search(r"feedback cycle 1|Goodbye, World!", reused_wait_message, re.IGNORECASE)))
    t.check("reused completion reports a new follow-up commit",
            bool(follow_up_commit and follow_up_commit != "9e941a7"))
    t.check("reused-worker follow-up does not spawn a replacement worker",
            not replacement_dispatch_after_send)
    t.check("Codex path explicitly shut down a no-longer-needed worker",
            any(call.get("tool") == "close_agent" for call in collab_calls)
            or bool(re.search(r"shutting down|shutdown", operator_messages, re.IGNORECASE)))
    t.check("shutdown happens only after the reused cycle completes",
            close_agent_after_reused_wait
            or bool(re.search(r"reused cycle.*shutting down|follow-up.*shutting down|shutting down.*reused", operator_messages, re.IGNORECASE)))
    t.check("Codex path reports a human-readable worker label",
            bool(re.search(r"\b001-(impl|implementation|val|validation)/[A-Za-z0-9._-]+", operator_messages)))
    t.check("operator-facing worker label is reported alongside logical id or handle",
            bool(re.search(r"\b001-(impl|implementation|val|validation)/[A-Za-z0-9._-]+.*(spacedock:ensign|handle)|(?:spacedock:ensign|handle).*\b001-(impl|implementation|val|validation)/[A-Za-z0-9._-]+", operator_messages, re.IGNORECASE | re.DOTALL)))

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
            greeting_text.strip() == "Goodbye, World!")

    t.finish()
