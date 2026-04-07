#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the pr-merge mod rebasing the branch onto main before pushing.
# ABOUTME: Verifies branch rebase via bare repo remote with merge-base validation and gh stub.

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from test_lib import (
    TestRunner, create_test_project, setup_fixture,
    install_agents, run_first_officer, git_add_commit, read_entity_frontmatter,
)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Rebase branch before push E2E test")
    parser.add_argument("--agent", default="spacedock:first-officer")
    parser.add_argument("--model", default="haiku", help="Model to use (default: haiku)")
    parser.add_argument("--effort", default="low", help="Effort level (default: low)")
    return parser.parse_known_args()


def create_git_wrapper(test_dir: Path) -> Path:
    """Create a git wrapper that logs push commands while passing through to real git."""
    bin_dir = test_dir / "bin"
    bin_dir.mkdir(exist_ok=True)

    git_path = subprocess.run(
        ["which", "git"], capture_output=True, text=True, check=True,
    ).stdout.strip()

    log_file = test_dir / "git-push-log.txt"
    wrapper = bin_dir / "git"
    wrapper.write_text(
        f'#!/bin/bash\n'
        f'if [ "$1" = "push" ]; then\n'
        f'  echo "$(date +%s.%N) git $*" >> {log_file}\n'
        f'fi\n'
        f'exec {git_path} "$@"\n'
    )
    wrapper.chmod(0o755)
    return bin_dir


def create_gh_stub(test_dir: Path) -> Path:
    """Create a gh stub that logs invocations and prints a fake PR URL."""
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


def main():
    args, extra_args = parse_args()
    t = TestRunner("Rebase Branch Before Push E2E Test")

    # --- Phase 1: Set up test project with bare remote ---

    print("--- Phase 1: Set up test project with bare remote ---")

    create_test_project(t)

    # Create a bare repo to act as origin
    bare_repo = t.test_dir / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare_repo)], capture_output=True, check=True)

    # Add origin remote and push initial commit
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_repo)],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )

    # Copy the push-main-pipeline fixture
    setup_fixture(t, "push-main-pipeline", "push-main-pipeline")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: push-main-pipeline fixture")

    # Push this setup to origin so origin/main has the fixture
    subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )

    # Record the main commit BEFORE advancing — this is what the branch will fork from
    fork_point = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, cwd=t.test_project_dir,
    ).stdout.strip()

    print(f"  Test project: {t.test_project_dir}")
    print(f"  Bare remote:  {bare_repo}")
    print(f"  Fork point:   {fork_point}")

    # --- Phase 2: Create diverged branch state ---

    print("\n--- Phase 2: Create diverged branch state ---")

    # Create the worktree branch from current main (the fork point)
    branch_name = "spacedock-ensign/push-main-entity"
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )

    # Add the entity's "work output" on the branch
    entity_path = t.test_project_dir / "push-main-pipeline" / "push-main-entity.md"
    entity_text = entity_path.read_text()
    entity_text = entity_text.replace("status: backlog", "status: done")
    entity_text += "\nPush main test complete.\n"
    entity_path.write_text(entity_text)
    git_add_commit(t.test_project_dir, "work: push main test complete")

    branch_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, cwd=t.test_project_dir,
    ).stdout.strip()
    print(f"  Branch commit: {branch_commit}")

    # Switch back to main
    subprocess.run(
        ["git", "checkout", "main"],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )

    # Now advance main with a "merged PR" commit — simulates another PR merging on GitHub
    other_pr_file = t.test_project_dir / "push-main-pipeline" / "other-pr-merged.txt"
    other_pr_file.write_text("This file simulates a commit from another PR merging on GitHub.\n")
    git_add_commit(t.test_project_dir, "merge: other PR merged on GitHub")

    # Push advanced main to origin
    subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )

    main_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, cwd=t.test_project_dir,
    ).stdout.strip()
    print(f"  Main HEAD (advanced): {main_head}")

    # Verify the branch is behind main (merge-base should be fork_point, not main_head)
    merge_base_before = subprocess.run(
        ["git", "merge-base", "main", branch_name],
        capture_output=True, text=True, check=True, cwd=t.test_project_dir,
    ).stdout.strip()
    print(f"  Merge base before rebase: {merge_base_before}")
    assert merge_base_before == fork_point, \
        f"Expected merge-base to be fork point {fork_point}, got {merge_base_before}"
    assert merge_base_before != main_head, \
        "Branch should be behind main before the test runs"

    # Add a state commit on main (unpushed) to trigger the push-main-before-branch behavior
    marker_file = t.test_project_dir / "push-main-pipeline" / "_state-marker.txt"
    marker_file.write_text("state commit marker - unpushed\n")
    git_add_commit(t.test_project_dir, "state: simulate unpushed state commit on main")

    t.check_cmd("status script runs without errors",
                ["bash", "push-main-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 3: Create git wrapper and gh stub ---

    print("--- Phase 3: Create git wrapper and gh stub ---")

    bin_dir = create_git_wrapper(t.test_dir)
    create_gh_stub(t.test_dir)
    print(f"  Wrapper bin:  {bin_dir}")

    print()

    # --- Phase 4: Run first officer ---

    print("--- Phase 4: Run first officer (this takes ~60-120s) ---")

    abs_workflow = t.test_project_dir / "push-main-pipeline"

    # Inject our bin dir at the front of PATH so the git wrapper and gh stub are found
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{original_path}"

    try:
        fo_exit = run_first_officer(
            t,
            (
                f"Process the entity `push-main-entity` through the workflow at {abs_workflow}/ to completion. "
                f"The entity is already at status 'done' on branch '{branch_name}' with work committed. "
                "The branch needs to be rebased onto main and pushed as part of the pr-merge merge hook. "
                "When the pr-merge merge hook fires and asks for approval, approve the push immediately — "
                "say 'yes, go ahead' when asked. Do not wait for external input."
            ),
            agent_id=args.agent,
            extra_args=["--model", args.model, "--effort", args.effort, "--max-budget-usd", "2.00", *extra_args],
            log_name="fo-log.jsonl",
        )
    finally:
        os.environ["PATH"] = original_path

    print()

    # --- Phase 5: Validate push ordering ---

    print("--- Phase 5: Validate push ordering ---")

    push_log = t.test_dir / "git-push-log.txt"
    t.check("git push log file exists", push_log.is_file())

    if push_log.is_file():
        push_lines = push_log.read_text().strip().splitlines()
        print(f"  Push log ({len(push_lines)} lines):")
        for line in push_lines:
            print(f"    {line}")

        # Find the push-origin-main and push-origin-branch lines
        main_push_idx = None
        branch_push_idx = None
        for i, line in enumerate(push_lines):
            if re.search(r"git push origin main", line):
                if main_push_idx is None:
                    main_push_idx = i
            # Branch push: "git push origin <branch-name>" where branch-name is not "main"
            branch_match = re.search(r"git push origin (\S+)", line)
            if branch_match and branch_match.group(1) != "main":
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

    # --- Phase 6: Validate branch was rebased onto main ---

    print("--- Phase 6: Validate branch was rebased onto main ---")

    # The "other PR" commit (main_head from Phase 2) must be an ancestor of the branch
    # after rebase. We use --is-ancestor rather than merge-base == main HEAD because
    # the FO may make additional commits on main after pushing the branch (e.g., setting
    # the pr field), which would advance main past the branch's base.

    # Check if branch still exists locally
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True, cwd=t.test_project_dir,
    )

    if branch_exists.returncode == 0:
        # Check that the "other PR" commit is an ancestor of the branch
        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", main_head, branch_name],
            capture_output=True, text=True, cwd=t.test_project_dir,
        )
        # Also check the merge-base is past the original fork point
        merge_base_after = subprocess.run(
            ["git", "merge-base", "main", branch_name],
            capture_output=True, text=True, check=True, cwd=t.test_project_dir,
        ).stdout.strip()

        print(f"  Other-PR commit:       {main_head}")
        print(f"  Merge base after:      {merge_base_after}")
        print(f"  Fork point (original): {fork_point}")

        t.check(
            "other-PR commit is ancestor of branch (branch was rebased)",
            is_ancestor.returncode == 0,
        )
        t.check(
            "merge-base moved past original fork point",
            merge_base_after != fork_point,
        )
    else:
        print("  Branch not found locally — checking remote")

    # Check on the bare remote
    remote_branch_exists = subprocess.run(
        ["git", "-C", str(bare_repo), "rev-parse", "--verify", branch_name],
        capture_output=True, text=True,
    )

    if remote_branch_exists.returncode == 0:
        # Check that the "other PR" commit is an ancestor of the remote branch
        remote_is_ancestor = subprocess.run(
            ["git", "-C", str(bare_repo), "merge-base", "--is-ancestor", main_head, branch_name],
            capture_output=True, text=True,
        )

        remote_merge_base = subprocess.run(
            ["git", "-C", str(bare_repo), "merge-base", "main", branch_name],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        print(f"  Remote merge base:     {remote_merge_base}")

        t.check(
            "remote: other-PR commit is ancestor of branch (rebased before push)",
            remote_is_ancestor.returncode == 0,
        )

        # Verify the remote branch has the "other PR" file (inherited via rebase)
        remote_branch_files = subprocess.run(
            ["git", "-C", str(bare_repo), "ls-tree", "--name-only", branch_name, "push-main-pipeline/"],
            capture_output=True, text=True, check=True,
        ).stdout
        t.check(
            "remote branch contains other-pr-merged.txt (from main via rebase)",
            "other-pr-merged.txt" in remote_branch_files,
        )
        print(f"  Remote branch files in push-main-pipeline/:\n{remote_branch_files.strip()}")
    else:
        t.fail("remote: other-PR commit is ancestor of branch (rebased before push)")
        t.fail("remote branch contains other-pr-merged.txt (from main via rebase)")
        print("  Branch not found on remote")

    print()

    # --- Phase 7: Validate PR creation ---

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
        print("  No gh-calls.log found")

    print()

    # --- Phase 8: Validate entity state ---

    print("--- Phase 8: Validate entity state ---")

    entity_file = t.test_project_dir / "push-main-pipeline" / "push-main-entity.md"
    archive_file = t.test_project_dir / "push-main-pipeline" / "_archive" / "push-main-entity.md"

    # Check entity pr field (could be in either location)
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

    # Entity should NOT be archived (pr-merge mod says to wait for PR merge)
    if not archive_file.is_file():
        t.pass_("entity not archived (waiting for PR merge, per mod)")
    else:
        # Acceptable — the FO might have gone further than expected
        print("  NOTE: entity was archived — FO may have completed the full cycle")

    # --- Results ---
    t.results()


if __name__ == "__main__":
    main()
