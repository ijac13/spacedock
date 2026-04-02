# ABOUTME: Shared test library for all Spacedock test scripts.
# ABOUTME: Provides test framework, project setup, claude wrappers, log parsing, and stats extraction.

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path


def _codex_skill_namespace_root(home_dir: Path) -> Path:
    return home_dir / ".agents" / "skills" / "spacedock"


def prepare_codex_skill_home(test_root: Path, repo_root: Path) -> Path:
    """Create an isolated HOME that exposes the current repo as the spacedock Codex skill namespace."""
    home_dir = test_root / "codex-home"
    namespace_root = _codex_skill_namespace_root(home_dir)
    namespace_root.mkdir(parents=True, exist_ok=True)

    skills_root = repo_root / "skills"
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            continue
        link_path = namespace_root / skill_dir.name
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(skill_dir, target_is_directory=True)

    for name, target in {
        "skills": skills_root,
        "agents": repo_root / "agents",
        "scripts": repo_root / "scripts",
        "references": repo_root / "references",
    }.items():
        link_path = namespace_root / name
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(target, target_is_directory=True)

    real_codex_home = Path(os.path.expanduser("~")) / ".codex"
    codex_home_link = home_dir / ".codex"
    if codex_home_link.exists() or codex_home_link.is_symlink():
        codex_home_link.unlink()
    codex_home_link.symlink_to(real_codex_home, target_is_directory=True)

    return home_dir


def resolve_codex_worker(agent_id: str, repo_root: Path | None = None) -> dict[str, object]:
    """Resolve a logical Codex worker id to a packaged asset and safe worker key."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    if not agent_id:
        raise ValueError("Codex worker id must not be empty")

    if agent_id.startswith("spacedock:"):
        agent_name = agent_id.split(":", 1)[1]
        asset_path = repo_root / "agents" / f"{agent_name}.md"
        if not asset_path.is_file():
            raise ValueError(f"Unknown Codex worker id: {agent_id}")
        return {
            "dispatch_agent_id": agent_id,
            "worker_key": re.sub(r"[^A-Za-z0-9._-]", "-", agent_id),
            "asset_kind": "agent",
            "asset_path": asset_path,
        }

    worker_key = re.sub(r"[^A-Za-z0-9._-]", "-", agent_id)
    return {
        "dispatch_agent_id": agent_id,
        "worker_key": worker_key,
        "asset_kind": "prompt",
        "asset_name": "generic-worker",
    }


def build_codex_first_officer_invocation_prompt(
    workflow_dir: str | Path,
    run_goal: str | None = None,
) -> str:
    workflow_dir = Path(workflow_dir)
    extra_goal = ""
    if run_goal:
        extra_goal = f"\n{run_goal.strip()}\n"
    return textwrap.dedent(
        f"""
        Use the `spacedock:first-officer` skill to manage the workflow at `{workflow_dir}`.

        Treat that path as the explicit workflow target. Do not ask to discover alternatives.
        Stay tightly bounded to the requested goal.
        Let the skill bootstrap the packaged first-officer agent asset and follow that agent directly.
        For bounded single-entity dispatches, prefer the helper at `~/.agents/skills/spacedock/scripts/codex_prepare_dispatch.py`
        instead of manually editing frontmatter, composing worktree names, or building the worker assignment by hand.
        For bounded terminal-completion runs, prefer the helper at `~/.agents/skills/spacedock/scripts/codex_finalize_terminal_entity.py`
        instead of freehand merge-hook, merge, archive, or worktree-cleanup steps.
        Any worker you spawn in this run MUST use `fork_context=false` with a fully self-contained prompt.
        Do not load reference docs unless you hit a real blocker.
        Do not reread your own skill files, inspect packaged worker agent assets before dispatch requires them, or open the `status` script source unless a blocker requires it.
        Run the workflow `status` script directly or with `python3` if needed. Never invoke it with `zsh`.
        Do not narrate setup beyond what is needed to report a blocker or final outcome.
        Once you have enough context to dispatch the first worker, dispatch immediately.
        Stop immediately once the requested bounded outcome is satisfied and send one final response.
        {extra_goal}
        """
    ).strip()


def build_codex_worker_bootstrap_prompt(
    resolved_worker: dict[str, object],
    workflow_dir: Path,
    entity_path: Path,
    stage_name: str,
    stage_definition_text: str,
    worktree_path: Path | None,
    checklist: list[str],
) -> str:
    if resolved_worker["asset_kind"] == "agent":
        lines = [
            f"You are the packaged worker `{resolved_worker['dispatch_agent_id']}`.",
            "Resolve your role definition before doing anything else.",
            "For packaged ids of the form `namespace:name`, read `~/.agents/skills/{namespace}/agents/{name}.md` first and follow it for this task.",
            "After resolving the role, continue with the assignment below.",
            "",
            "Assignment:",
            f"dispatch_agent_id: {resolved_worker['dispatch_agent_id']}",
            f"worker_key: {resolved_worker['worker_key']}",
            f"role_asset_kind: {resolved_worker['asset_kind']}",
            f"role_asset_name: {Path(str(resolved_worker['asset_path'])).stem}",
            f"workflow_dir: {workflow_dir}",
            f"entity_path: {entity_path}",
            f"stage_name: {stage_name}",
            "stage_definition_text:",
            stage_definition_text,
        ]
    else:
        lines = [
            "You are a generic worker handling one entity for one stage.",
            "Operate directly from the assignment below.",
            "Do not modify YAML frontmatter in entity files.",
            "Do not take over first-officer responsibilities.",
            "",
            "Assignment:",
            f"dispatch_agent_id: {resolved_worker['dispatch_agent_id']}",
            f"worker_key: {resolved_worker['worker_key']}",
            f"role_asset_kind: {resolved_worker['asset_kind']}",
            f"role_asset_name: {resolved_worker['asset_name']}",
            f"workflow_dir: {workflow_dir}",
            f"entity_path: {entity_path}",
            f"stage_name: {stage_name}",
            "stage_definition_text:",
            stage_definition_text,
        ]
    if worktree_path is not None:
        lines.append(f"worktree_path: {worktree_path}")
    if checklist:
        lines.extend(["checklist:"] + [f"- {item}" for item in checklist])
    return "\n".join(lines)


def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ without CLAUDECODE so subprocess can launch claude."""
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


class TestRunner:
    """Test framework with pass/fail counters, check helpers, and results summary."""

    def __init__(self, test_name: str, keep_test_dir: bool = False):
        self.test_name = test_name
        self.passes = 0
        self.failures = 0
        self.repo_root = Path(__file__).resolve().parent.parent
        self.test_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.test_dir
        self.keep_test_dir = keep_test_dir or bool(os.environ.get("KEEP_TEST_DIR"))
        self.test_project_dir: Path | None = None

        atexit.register(self._cleanup)

        print(f"=== {test_name} ===")
        print(f"Repo root:  {self.repo_root}")
        print(f"Test dir:   {self.test_dir}")
        print()

    def _cleanup(self):
        if self.keep_test_dir:
            print(f"Test dir preserved at: {self.test_dir}")
        elif self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def pass_(self, label: str):
        self.passes += 1
        print(f"  PASS: {label}")

    def fail(self, label: str):
        self.failures += 1
        print(f"  FAIL: {label}")

    def check(self, label: str, condition: bool):
        if condition:
            self.pass_(label)
        else:
            self.fail(label)

    def check_cmd(self, label: str, cmd: list[str], **kwargs) -> bool:
        """Run a command; pass if exit code 0, fail otherwise."""
        try:
            subprocess.run(cmd, capture_output=True, check=True, **kwargs)
            self.pass_(label)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.fail(label)
            return False

    def results(self):
        """Print summary and exit with appropriate code."""
        print()
        print("=== Results ===")
        total = self.passes + self.failures
        print(f"  {self.passes} passed, {self.failures} failed (out of {total} checks)")
        print()

        if self.failures > 0:
            print("RESULT: FAIL")
            print()
            print("Debug info:")
            print(f"  Test dir:   {self.test_dir}")
            for f in sorted(self.log_dir.glob("*.jsonl")) + sorted(self.log_dir.glob("*.txt")):
                print(f"  Log:        {f}")
            # Preserve test dir on failure
            self.keep_test_dir = True
            sys.exit(1)
        else:
            print("RESULT: PASS")
            sys.exit(0)


def create_test_project(runner: TestRunner, name: str = "test-project") -> Path:
    """Create a temp git project with an empty initial commit."""
    project_dir = runner.test_dir / name
    subprocess.run(["git", "init", str(project_dir)], capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        capture_output=True, check=True, cwd=project_dir,
    )
    runner.test_project_dir = project_dir
    return project_dir


def setup_fixture(runner: TestRunner, fixture_name: str, pipeline_dir: str) -> Path:
    """Copy a fixture from tests/fixtures/ into the test project pipeline directory."""
    fixture_path = runner.repo_root / "tests" / "fixtures" / fixture_name
    dest = runner.test_project_dir / pipeline_dir
    dest.mkdir(parents=True, exist_ok=True)

    # Copy all files and subdirectories from fixture
    for item in fixture_path.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    # Make status script executable if present
    status = dest / "status"
    if status.exists():
        status.chmod(status.stat().st_mode | 0o111)

    return dest


def install_agents(runner: TestRunner, include_ensign: bool = False) -> Path:
    """Copy agent templates into the test project's .claude/agents/ directory."""
    agents_dir = runner.test_project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    fo_path = agents_dir / "first-officer.md"
    shutil.copy2(runner.repo_root / "templates" / "first-officer.md", fo_path)

    if include_ensign:
        shutil.copy2(runner.repo_root / "templates" / "ensign.md", agents_dir / "ensign.md")

    return fo_path


def run_commission(
    runner: TestRunner,
    prompt: str,
    extra_args: list[str] | None = None,
    log_name: str = "commission-log.jsonl",
) -> int:
    """Run claude -p with commission flags. Returns exit code."""
    log_path = runner.log_dir / log_name
    cmd = [
        "claude", "-p", prompt,
        "--plugin-dir", str(runner.repo_root),
        "--permission-mode", "bypassPermissions",
        "--verbose",
        "--output-format", "stream-json",
    ]
    if extra_args:
        cmd.extend(extra_args)

    with open(log_path, "w") as log_file:
        try:
            result = subprocess.run(
                cmd, stdout=log_file, stderr=subprocess.STDOUT,
                cwd=runner.test_project_dir, env=_clean_env(), timeout=600,
            )
        except subprocess.TimeoutExpired:
            print("\n  TIMEOUT: commission exceeded 600s limit")
            return 124

    print()
    if result.returncode != 0:
        print(f"WARNING: claude exited with code {result.returncode}")

    # Auto-extract stats
    extract_stats(log_path, "commission", runner.log_dir)

    return result.returncode


def run_first_officer(
    runner: TestRunner,
    prompt: str,
    extra_args: list[str] | None = None,
    log_name: str = "fo-log.jsonl",
) -> int:
    """Run claude -p --agent first-officer. Returns exit code."""
    log_path = runner.log_dir / log_name
    cmd = [
        "claude", "-p", prompt,
        "--agent", "first-officer",
        "--permission-mode", "bypassPermissions",
        "--verbose",
        "--output-format", "stream-json",
    ]
    if extra_args:
        cmd.extend(extra_args)

    with open(log_path, "w") as log_file:
        try:
            result = subprocess.run(
                cmd, stdout=log_file, stderr=subprocess.STDOUT,
                cwd=runner.test_project_dir, env=_clean_env(), timeout=600,
            )
        except subprocess.TimeoutExpired:
            print("\n  TIMEOUT: first officer exceeded 600s limit")
            return 124

    print()
    if result.returncode != 0:
        print(f"WARNING: first officer exited with code {result.returncode}")

    # Auto-extract stats
    extract_stats(log_path, "fo", runner.log_dir)

    return result.returncode


def run_codex_first_officer(
    runner: TestRunner,
    workflow_dir: str,
    run_goal: str | None = None,
    extra_args: list[str] | None = None,
    log_name: str = "codex-fo-log.txt",
    timeout_s: int = 120,
) -> int:
    """Run the Codex first-officer skill via codex exec. Returns exit code."""
    log_path = runner.log_dir / log_name
    workflow_path = (runner.test_project_dir / workflow_dir).resolve()
    prompt = build_codex_first_officer_invocation_prompt(workflow_path, run_goal=run_goal)
    (runner.log_dir / "codex-fo-invocation.txt").write_text(prompt + "\n")

    skill_home = prepare_codex_skill_home(runner.test_dir, runner.repo_root)
    env = os.environ.copy()
    env["HOME"] = str(skill_home)
    env["CODEX_HOME"] = str(skill_home / ".codex")

    cmd = [
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--enable",
        "multi_agent",
        "--dangerously-bypass-approvals-and-sandbox",
        "-C",
        str(runner.test_project_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append("-")

    with open(log_path, "w") as log_file:
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=runner.test_project_dir,
                timeout=timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(f"\n  TIMEOUT: codex first officer exceeded {timeout_s}s limit")
            return 124

    print()
    if result.returncode != 0:
        print(f"WARNING: codex first officer exited with code {result.returncode}")

    return result.returncode


class LogParser:
    """Parses a stream-json JSONL log file from claude."""

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        self._entries: list[dict] | None = None

    @property
    def entries(self) -> list[dict]:
        if self._entries is None:
            self._entries = []
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return self._entries

    def assistant_messages(self) -> list[dict]:
        """Return all assistant message objects."""
        return [
            e for e in self.entries
            if e.get("type") == "assistant" and "message" in e
        ]

    def agent_calls(self) -> list[dict]:
        """Extract Agent() tool calls with subagent_type, name, and prompt."""
        calls = []
        for msg in self.assistant_messages():
            for block in msg["message"].get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Agent":
                    inp = block.get("input", {})
                    calls.append({
                        "subagent_type": inp.get("subagent_type", ""),
                        "name": inp.get("name", ""),
                        "prompt": inp.get("prompt", ""),
                    })
        return calls

    def fo_texts(self) -> list[str]:
        """Extract text blocks from assistant messages."""
        texts = []
        for msg in self.assistant_messages():
            for block in msg["message"].get("content", []):
                if block.get("type") == "text":
                    texts.append(block["text"])
        return texts

    def tool_calls(self) -> list[dict]:
        """Extract all tool_use blocks from assistant messages."""
        calls = []
        for msg in self.assistant_messages():
            for block in msg["message"].get("content", []):
                if block.get("type") == "tool_use":
                    calls.append({
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    })
        return calls

    def agent_prompt(self) -> str:
        """Extract the prompt from the last Agent() call (for tests that check dispatch content)."""
        prompt = ""
        for call in self.agent_calls():
            prompt = call["prompt"]
        return prompt

    def write_agent_calls(self, output_path: Path | str):
        """Write agent calls summary to a text file."""
        with open(output_path, "w") as f:
            for call in self.agent_calls():
                f.write(f"subagent_type={call['subagent_type']} name={call['name']}\n")
                f.write(f"prompt_preview={call['prompt'][:200]}\n")
                f.write("---\n")

    def write_fo_texts(self, output_path: Path | str):
        """Write concatenated FO texts to a file."""
        with open(output_path, "w") as f:
            f.write("\n".join(self.fo_texts()))

    def write_tool_calls(self, output_path: Path | str):
        """Write tool calls as JSON to a file."""
        with open(output_path, "w") as f:
            json.dump(self.tool_calls(), f, indent=2)

    def write_agent_prompt(self, output_path: Path | str):
        """Write the agent prompt to a file."""
        with open(output_path, "w") as f:
            f.write(self.agent_prompt())


class CodexLogParser:
    """Parses a mixed JSONL/plain-text log file from `codex exec --json`."""

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        self._raw_lines: list[str] | None = None
        self._json_entries: list[dict] | None = None

    @property
    def raw_lines(self) -> list[str]:
        if self._raw_lines is None:
            self._raw_lines = self.log_path.read_text().splitlines() if self.log_path.exists() else []
        return self._raw_lines

    @property
    def json_entries(self) -> list[dict]:
        if self._json_entries is None:
            entries: list[dict] = []
            for line in self.raw_lines:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self._json_entries = entries
        return self._json_entries

    def full_text(self) -> str:
        texts = list(self.raw_lines)
        for entry in self.json_entries:
            item = entry.get("item", {})
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    texts.append(text)
        return "\n".join(texts)

    def spawn_count(self) -> int:
        count = 0
        for entry in self.json_entries:
            item = entry.get("item", {})
            if not isinstance(item, dict):
                continue
            if item.get("type") != "collab_tool_call":
                continue
            if item.get("tool") in {"spawn", "spawn_agent"}:
                count += 1
        return count

    def completed_agent_messages(self) -> list[str]:
        messages: list[str] = []
        for entry in self.json_entries:
            item = entry.get("item", {})
            if not isinstance(item, dict):
                continue
            if item.get("type") != "collab_tool_call":
                continue
            if item.get("tool") != "wait":
                continue
            states = item.get("agents_states", {})
            if not isinstance(states, dict):
                continue
            for state in states.values():
                if not isinstance(state, dict):
                    continue
                if state.get("status") == "completed" and state.get("message"):
                    messages.append(str(state["message"]))
        return messages

    def write_text(self, output_path: Path | str):
        with open(output_path, "w") as f:
            f.write(self.full_text())


def extract_stats(log_path: Path | str, phase_name: str, output_dir: Path | str) -> dict:
    """Extract stats from a stream-json log. Prints and writes to file. Returns stats dict."""
    log_path = Path(log_path)
    output_dir = Path(output_dir)

    if not log_path.exists():
        return {}

    first_ts = None
    last_ts = None
    assistant_count = 0
    tool_result_count = 0
    model_counts: dict[str, int] = {}
    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    cache_write = 0

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp")
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            msg_type = obj.get("type", "")

            if msg_type == "assistant" and "message" in obj:
                assistant_count += 1
                model = obj["message"].get("model", obj.get("model", "unknown"))
                model_counts[model] = model_counts.get(model, 0) + 1
                usage = obj["message"].get("usage", {})
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                cache_read += usage.get("cache_read_input_tokens", 0)
                cache_write += usage.get("cache_creation_input_tokens", 0)
            elif msg_type == "tool_result":
                tool_result_count += 1

    # Wallclock calculation
    wallclock_s = None
    if first_ts and last_ts:
        try:
            d1 = datetime.fromisoformat(first_ts[:19])
            d2 = datetime.fromisoformat(last_ts[:19])
            wallclock_s = int((d2 - d1).total_seconds())
        except (ValueError, TypeError):
            pass

    wallclock_str = f"{wallclock_s}s" if wallclock_s is not None else "?"
    model_str = ", ".join(f"{m}: {c}" for m, c in sorted(model_counts.items()))

    lines = [
        f"=== Stats: {phase_name} ===",
        f"  Wallclock:        {wallclock_str}",
        f"  Messages:         {assistant_count} assistant, {tool_result_count} tool_result",
        f"  Model delegation: {model_str}",
        f"  Input tokens:     {input_tokens:,}",
        f"  Output tokens:    {output_tokens:,}",
        f"  Cache read:       {cache_read:,}",
        f"  Cache write:      {cache_write:,}",
    ]

    output = "\n".join(lines)
    print(output)

    output_file = output_dir / f"stats-{phase_name}.txt"
    output_file.write_text(output + "\n")

    return {
        "wallclock_s": wallclock_s,
        "assistant_count": assistant_count,
        "tool_result_count": tool_result_count,
        "model_counts": model_counts,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read": cache_read,
        "cache_write": cache_write,
    }


def git_add_commit(project_dir: Path, message: str):
    """Stage all and commit in the given project directory."""
    subprocess.run(["git", "add", "-A"], capture_output=True, check=True, cwd=project_dir)
    subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, check=True, cwd=project_dir,
    )


def read_entity_frontmatter(entity_path: Path) -> dict[str, str]:
    """Read YAML frontmatter fields from an entity file. Returns dict of field: value."""
    fields = {}
    in_frontmatter = False
    text = entity_path.read_text()
    for line in text.splitlines():
        if line.strip() == "---":
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if in_frontmatter and ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def file_contains(path: Path | str, pattern: str, case_insensitive: bool = False) -> bool:
    """Check if a file contains a regex pattern."""
    text = Path(path).read_text()
    flags = re.IGNORECASE if case_insensitive else 0
    return bool(re.search(pattern, text, flags))


def file_grep(path: Path | str, pattern: str, case_insensitive: bool = False) -> list[str]:
    """Return all lines matching a regex pattern in a file."""
    text = Path(path).read_text()
    flags = re.IGNORECASE if case_insensitive else 0
    return [line for line in text.splitlines() if re.search(pattern, line, flags)]
