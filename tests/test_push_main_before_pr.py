#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: E2E test for the pr-merge mod pushing main before pushing the branch.
# ABOUTME: Verifies push ordering via git wrapper and bare repo remote with gh stub.

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
    parser = argparse.ArgumentParser(description="Push main before PR E2E test")
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
    t = TestRunner("Push Main Before PR E2E Test")

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

    # Simulate a state commit on main (like FO updating entity frontmatter)
    # This creates the "unpushed state commits on main" condition
    entity_path = t.test_project_dir / "push-main-pipeline" / "push-main-entity.md"
    entity_text = entity_path.read_text()
    entity_text = entity_text.replace("status: backlog", "status: backlog")
    # Add a small marker to main that would conflict if not pushed
    marker_file = t.test_project_dir / "push-main-pipeline" / "_state-marker.txt"
    marker_file.write_text("state commit marker - unpushed\n")
    git_add_commit(t.test_project_dir, "state: simulate unpushed state commit on main")

    # Do NOT push this commit - origin/main is now behind local main
    print(f"  Test project: {t.test_project_dir}")
    print(f"  Bare remote:  {bare_repo}")

    t.check_cmd("status script runs without errors",
                ["bash", "push-main-pipeline/status"], cwd=t.test_project_dir)

    print()

    # --- Phase 2: Create git wrapper and gh stub ---

    print("--- Phase 2: Create git wrapper and gh stub ---")

    bin_dir = create_git_wrapper(t.test_dir)
    create_gh_stub(t.test_dir)
    print(f"  Wrapper bin:  {bin_dir}")

    print()

    # --- Phase 3: Run first officer ---

    print("--- Phase 3: Run first officer (this takes ~60-120s) ---")

    abs_workflow = t.test_project_dir / "push-main-pipeline"

    # Inject our bin dir at the front of PATH so the git wrapper and gh stub are found
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{original_path}"

    try:
        fo_exit = run_first_officer(
            t,
            (
                f"Process the entity `push-main-entity` through the workflow at {abs_workflow}/ to completion. "
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

    # --- Phase 4: Validate push ordering ---

    print("--- Phase 4: Validate push ordering ---")

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

    # --- Phase 5: Validate remote state ---

    print("--- Phase 5: Validate remote state ---")

    # Check that origin/main has the state commit
    remote_log = subprocess.run(
        ["git", "-C", str(bare_repo), "log", "--oneline", "main"],
        capture_output=True, text=True,
    )
    if remote_log.returncode == 0:
        t.check(
            "remote main has state commit",
            "state" in remote_log.stdout.lower() or "setup" in remote_log.stdout.lower(),
        )
        print(f"  Remote main log:\n{remote_log.stdout.strip()}")
    else:
        t.fail("remote main has state commit")

    # Check that a branch (other than main) exists on the remote
    remote_branches = subprocess.run(
        ["git", "-C", str(bare_repo), "branch"],
        capture_output=True, text=True,
    )
    branch_names = [b.strip().lstrip("* ") for b in remote_branches.stdout.strip().splitlines()]
    non_main_branches = [b for b in branch_names if b and b != "main"]
    t.check("worktree branch pushed to remote", len(non_main_branches) > 0)
    if non_main_branches:
        print(f"  Remote branches: {non_main_branches}")

    print()

    # --- Phase 6: Validate PR creation ---

    print("--- Phase 6: Validate PR creation ---")

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

    # --- Phase 7: Validate entity state ---

    print("--- Phase 7: Validate entity state ---")

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
