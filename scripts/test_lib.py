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
from datetime import datetime
from pathlib import Path


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


def create_test_project(runner: TestRunner) -> Path:
    """Create a temp git project with an empty initial commit."""
    project_dir = runner.test_dir / "test-project"
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


def generate_first_officer(
    runner: TestRunner,
    pipeline_dir: str,
    mission: str = "Test",
    entity_label: str = "task",
    entity_label_plural: str = "tasks",
    captain: str = "CL",
    first_stage: str = "backlog",
    last_stage: str = "done",
    spacedock_version: str = "test",
) -> Path:
    """Generate first-officer.md from template with variable substitution."""
    template = runner.repo_root / "templates" / "first-officer.md"
    content = template.read_text()

    dir_basename = os.path.basename(pipeline_dir)
    substitutions = {
        "__MISSION__": mission,
        "__DIR__": pipeline_dir,
        "__DIR_BASENAME__": dir_basename,
        "__PROJECT_NAME__": "test-project",
        "__ENTITY_LABEL__": entity_label,
        "__ENTITY_LABEL_PLURAL__": entity_label_plural,
        "__CAPTAIN__": captain,
        "__FIRST_STAGE__": first_stage,
        "__LAST_STAGE__": last_stage,
        "__SPACEDOCK_VERSION__": spacedock_version,
    }
    for placeholder, value in substitutions.items():
        content = content.replace(placeholder, value)

    agents_dir = runner.test_project_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    fo_path = agents_dir / "first-officer.md"
    fo_path.write_text(content)
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
        result = subprocess.run(
            cmd, stdout=log_file, stderr=subprocess.STDOUT,
            cwd=runner.test_project_dir,
        )

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
        result = subprocess.run(
            cmd, stdout=log_file, stderr=subprocess.STDOUT,
            cwd=runner.test_project_dir,
        )

    print()
    if result.returncode != 0:
        print(f"WARNING: first officer exited with code {result.returncode}")

    # Auto-extract stats
    extract_stats(log_path, "fo", runner.log_dir)

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
