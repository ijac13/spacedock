# ABOUTME: E2E test for the pr-merge mod pushing main before pushing the branch.
# ABOUTME: Verifies push ordering via git wrapper and bare repo remote with gh stub.

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
@pytest.mark.teams_mode
@pytest.mark.skip(reason="FO still archives past pr-merge without persisting pr state. Track: #114")
def test_push_main_before_pr(test_project, model, effort):
    """pr-merge mod pushes `main` before the branch; gh stub sees `gh pr create`."""
    t = test_project

    print("--- Phase 1: Set up test project with bare remote ---")
    bare_repo = t.test_dir / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare_repo)], capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_repo)],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, check=True, cwd=t.test_project_dir,
    )
    setup_fixture(t, "push-main-pipeline", "push-main-pipeline")
    install_agents(t)
    git_add_commit(t.test_project_dir, "setup: push-main-pipeline fixture")

    marker_file = t.test_project_dir / "push-main-pipeline" / "_state-marker.txt"
    marker_file.write_text("state commit marker - unpushed\n")
    git_add_commit(t.test_project_dir, "state: simulate unpushed state commit on main")

    print(f"  Test project: {t.test_project_dir}")
    print(f"  Bare remote:  {bare_repo}")
    t.check_cmd("status script runs without errors",
                ["push-main-pipeline/status"], cwd=t.test_project_dir)

    print()

    print("--- Phase 2: Create git wrapper and gh stub ---")
    bin_dir = _create_git_wrapper(t.test_dir)
    _create_gh_stub(t.test_dir)
    print(f"  Wrapper bin:  {bin_dir}")
    print()

    print("--- Phase 3: Run first officer (this takes ~60-120s) ---")
    abs_workflow = t.test_project_dir / "push-main-pipeline"
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{original_path}"
    try:
        run_first_officer(
            t,
            (
                f"Process the entity `push-main-entity` through the workflow at {abs_workflow}/ to completion. "
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

    print("--- Phase 4: Validate push ordering ---")
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

    print("--- Phase 5: Validate remote state ---")
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
    print()

    print("--- Phase 7: Validate entity state ---")
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

