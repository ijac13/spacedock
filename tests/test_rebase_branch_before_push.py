# ABOUTME: E2E test for the pr-merge mod rebasing the branch onto main before pushing.
# ABOUTME: Verifies branch rebase via bare repo remote with merge-base validation and gh stub.

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (  # noqa: E402
    git_add_commit,
    install_agents,
    read_entity_frontmatter,
    run_first_officer,
    setup_fixture,
)


def _create_git_wrapper(test_dir: Path) -> Path:
    bin_dir = test_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    git_path = subprocess.run(["which", "git"], capture_output=True, text=True, check=True).stdout.strip()
    log_file = test_dir / "git-push-log.txt"
    wrapper = bin_dir / "git"
    # Detect `git push ...` and `git -C <path> push ...` forms. Skip leading
    # `-C <path>` pairs and any other leading options so the first non-option
    # argument is inspected as the subcommand.
    wrapper.write_text(
        f'#!/bin/bash\n'
        f'args=("$@")\n'
        f'i=0\n'
        f'while [ $i -lt ${{#args[@]}} ]; do\n'
        f'  case "${{args[$i]}}" in\n'
        f'    -C|-c|--git-dir|--work-tree|--namespace|--super-prefix)\n'
        f'      i=$((i+2));;\n'
        f'    --*=*|-*)\n'
        f'      i=$((i+1));;\n'
        f'    *) break;;\n'
        f'  esac\n'
        f'done\n'
        f'if [ "${{args[$i]}}" = "push" ]; then\n'
        f'  echo "$(date +%s.%N) git $*" >> {log_file}\n'
        f'fi\n'
        f'exec {git_path} "$@"\n'
    )
    wrapper.chmod(0o755)
    return bin_dir


def _create_gh_stub(test_dir: Path) -> Path:
    bin_dir = test_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_file = test_dir / "gh-calls.log"
    stub = bin_dir / "gh"
    stub.write_text(
        f'#!/bin/bash\n'
        f'echo "$*" >> {log_file}\n'
        f'if echo "$*" | grep -q "pr create"; then\n'
        f'  echo "https://github.com/test/test/pull/99"\n'
        f'fi\n'
        f'exit 0\n'
    )
    stub.chmod(0o755)
    return bin_dir


@pytest.mark.live_claude
@pytest.mark.serial
def test_rebase_branch_before_push(test_project, model, effort):
    """pr-merge mod rebases branch onto main via bare-repo remote before push."""
    t = test_project

    print("--- Phase 1: Set up test project with bare remote ---")
    bare_repo = t.test_dir / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare_repo)], capture_output=True, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare_repo)],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    subprocess.run(["git", "push", "origin", "main"],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    setup_fixture(t, "push-main-pipeline", "push-main-pipeline")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: push-main-pipeline fixture")
    subprocess.run(["git", "push", "origin", "main"],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    fork_point = subprocess.run(["git", "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True, cwd=t.test_project_dir).stdout.strip()
    print(f"  Test project: {t.test_project_dir}")
    print(f"  Bare remote:  {bare_repo}")
    print(f"  Fork point:   {fork_point}")

    print("\n--- Phase 2: Create diverged branch state ---")
    branch_name = "spacedock-ensign/push-main-entity"
    subprocess.run(["git", "checkout", "-b", branch_name],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    entity_path = t.test_project_dir / "push-main-pipeline" / "push-main-entity.md"
    entity_text = entity_path.read_text()
    entity_text = entity_text.replace("status: backlog", "status: done")
    entity_text += "\nPush main test complete.\n"
    entity_path.write_text(entity_text)
    git_add_commit(t.test_project_dir, "work: push main test complete")
    branch_commit = subprocess.run(["git", "rev-parse", "HEAD"],
                                   capture_output=True, text=True, check=True, cwd=t.test_project_dir).stdout.strip()
    print(f"  Branch commit: {branch_commit}")

    subprocess.run(["git", "checkout", "main"],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    other_pr_file = t.test_project_dir / "push-main-pipeline" / "other-pr-merged.txt"
    other_pr_file.write_text("This file simulates a commit from another PR merging on GitHub.\n")
    git_add_commit(t.test_project_dir, "merge: other PR merged on GitHub")
    subprocess.run(["git", "push", "origin", "main"],
                   capture_output=True, check=True, cwd=t.test_project_dir)
    main_head = subprocess.run(["git", "rev-parse", "HEAD"],
                               capture_output=True, text=True, check=True, cwd=t.test_project_dir).stdout.strip()
    print(f"  Main HEAD (advanced): {main_head}")

    merge_base_before = subprocess.run(["git", "merge-base", "main", branch_name],
                                       capture_output=True, text=True, check=True, cwd=t.test_project_dir).stdout.strip()
    print(f"  Merge base before rebase: {merge_base_before}")
    assert merge_base_before == fork_point, \
        f"Expected merge-base to be fork point {fork_point}, got {merge_base_before}"
    assert merge_base_before != main_head, "Branch should be behind main before the test runs"

    marker_file = t.test_project_dir / "push-main-pipeline" / "_state-marker.txt"
    marker_file.write_text("state commit marker - unpushed\n")
    git_add_commit(t.test_project_dir, "state: simulate unpushed state commit on main")
    t.check_cmd("status script runs without errors",
                ["push-main-pipeline/status"], cwd=t.test_project_dir)

    print()

    print("--- Phase 3: Create git wrapper and gh stub ---")
    bin_dir = _create_git_wrapper(t.test_dir)
    _create_gh_stub(t.test_dir)
    print(f"  Wrapper bin:  {bin_dir}")
    print()

    print("--- Phase 4: Run first officer (this takes ~60-120s) ---")
    abs_workflow = t.test_project_dir / "push-main-pipeline"
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{original_path}"
    try:
        run_first_officer(
            t,
            (
                f"Process the entity `push-main-entity` through the workflow at {abs_workflow}/ to completion. "
                f"The entity is already at status 'done' on branch '{branch_name}' with work committed. "
                "The branch needs to be rebased onto main and pushed as part of the pr-merge merge hook. "
                "When the pr-merge merge hook fires and asks for approval, approve the push immediately — "
                "say 'yes, go ahead' when asked. Do not wait for external input."
            ),
            agent_id="spacedock:first-officer",
            extra_args=["--model", model, "--effort", effort, "--max-budget-usd", "2.00"],
            log_name="fo-log.jsonl",
        )
    finally:
        os.environ["PATH"] = original_path
    print()

    print("--- Phase 5: Validate push ordering ---")
    push_log = t.test_dir / "git-push-log.txt"
    t.check("git push log file exists", push_log.is_file())
    if push_log.is_file():
        push_lines = push_log.read_text().strip().splitlines()
        print(f"  Push log ({len(push_lines)} lines):")
        for line in push_lines:
            print(f"    {line}")

        # Find the push-origin-main and push-origin-branch lines. Accept
        # `push origin X` with optional flags between `push` and `origin`
        # (e.g. `push -u origin X`), and with any git-level options before the
        # `push` subcommand (e.g. `git -C <dir> push origin X`).
        main_push_idx = None
        branch_push_idx = None
        push_origin_re = re.compile(r"(?:^|\s)push(?:\s+-\S+)*\s+origin\s+(\S+)")
        for i, line in enumerate(push_lines):
            m = push_origin_re.search(line)
            if not m:
                continue
            target = m.group(1)
            if target == "main":
                if main_push_idx is None:
                    main_push_idx = i
            else:
                if branch_push_idx is None:
                    branch_push_idx = i
        t.check("git push origin main found in push log", main_push_idx is not None)
        t.check("git push origin {branch} found in push log", branch_push_idx is not None)
        if main_push_idx is not None and branch_push_idx is not None:
            t.check("main pushed BEFORE branch", main_push_idx < branch_push_idx)
        else:
            t.fail("main pushed BEFORE branch (missing push log entries)")
    else:
        t.fail("git push origin main found in push log")
        t.fail("git push origin {branch} found in push log")
        t.fail("main pushed BEFORE branch")
    print()

    print("--- Phase 6: Validate branch was rebased onto main ---")
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )
    if branch_exists.returncode == 0:
        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", main_head, branch_name],
            capture_output=True, text=True, cwd=t.test_project_dir,
        )
        merge_base_after = subprocess.run(
            ["git", "merge-base", "main", branch_name],
            capture_output=True, text=True, check=True, cwd=t.test_project_dir,
        ).stdout.strip()
        print(f"  Other-PR commit:       {main_head}")
        print(f"  Merge base after:      {merge_base_after}")
        print(f"  Fork point (original): {fork_point}")
        t.check("other-PR commit is ancestor of branch (branch was rebased)",
                is_ancestor.returncode == 0)
        t.check("merge-base moved past original fork point",
                merge_base_after != fork_point)
    else:
        print("  Branch not found locally — checking remote")

    remote_branch_exists = subprocess.run(
        ["git", "-C", str(bare_repo), "rev-parse", "--verify", branch_name],
        capture_output=True, text=True,
    )
    if remote_branch_exists.returncode == 0:
        remote_is_ancestor = subprocess.run(
            ["git", "-C", str(bare_repo), "merge-base", "--is-ancestor", main_head, branch_name],
            capture_output=True, text=True,
        )
        remote_merge_base = subprocess.run(
            ["git", "-C", str(bare_repo), "merge-base", "main", branch_name],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        print(f"  Remote merge base:     {remote_merge_base}")
        t.check("remote: other-PR commit is ancestor of branch (rebased before push)",
                remote_is_ancestor.returncode == 0)
        remote_branch_files = subprocess.run(
            ["git", "-C", str(bare_repo), "ls-tree", "--name-only", branch_name, "push-main-pipeline/"],
            capture_output=True, text=True, check=True,
        ).stdout
        t.check("remote branch contains other-pr-merged.txt (from main via rebase)",
                "other-pr-merged.txt" in remote_branch_files)
        print(f"  Remote branch files in push-main-pipeline/:\n{remote_branch_files.strip()}")
    else:
        t.fail("remote: other-PR commit is ancestor of branch (rebased before push)")
        t.fail("remote branch contains other-pr-merged.txt (from main via rebase)")
        print("  Branch not found on remote")
    print()

    print("--- Phase 7: Validate PR creation ---")
    gh_log = t.test_dir / "gh-calls.log"
    if gh_log.is_file():
        gh_calls = gh_log.read_text()
        t.check("gh pr create was called", "pr create" in gh_calls)
        t.check("PR targets main", "--base main" in gh_calls)
        print(f"  gh calls:\n{gh_calls.strip()}")
    else:
        t.fail("gh pr create was called")
        t.fail("PR targets main")
    print()

    print("--- Phase 8: Validate entity state ---")
    entity_file = t.test_project_dir / "push-main-pipeline" / "push-main-entity.md"
    archive_file = t.test_project_dir / "push-main-pipeline" / "_archive" / "push-main-entity.md"
    if entity_file.is_file():
        fm = read_entity_frontmatter(entity_file)
        pr_val = fm.get("pr", "")
        t.check("entity has pr field set", pr_val != "")
        print(f"  Entity pr: {pr_val}")
        print(f"  Entity status: {fm.get('status', '?')}")
    elif archive_file.is_file():
        fm = read_entity_frontmatter(archive_file)
        pr_val = fm.get("pr", "")
        t.check("entity has pr field set", pr_val != "")
        print(f"  Entity (archived) pr: {pr_val}")
    else:
        print("  SKIP: entity file not found in either location — FO may not have completed within budget")

    if not archive_file.is_file():
        t.pass_("entity not archived (waiting for PR merge, per mod)")
    else:
        print("  NOTE: entity was archived — FO may have completed the full cycle")

    t.finish()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
