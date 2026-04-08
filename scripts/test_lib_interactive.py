# ABOUTME: Interactive multi-turn test harness for Claude Code sessions.
# ABOUTME: Drives claude via PTY for testing team behavior, idle handling, and captain-agent communication.

from __future__ import annotations

import os
import pty
import re
import select
import signal
import time
from pathlib import Path


def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ without CLAUDECODE so subprocess can launch claude."""
    return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return re.sub(
        r"\x1b\[[>?]?[0-9;]*[A-Za-z]"
        r"|\x1b\][^\x07]*\x07"
        r"|\x1b[()][A-Z0-9]"
        r"|\x1b>[0-9;]*[a-zA-Z]"
        r"|\x1b<[a-zA-Z]",
        "",
        text,
    )


class InteractiveSession:
    """Drive an interactive claude session via PTY for multi-turn testing.

    Usage:
        session = InteractiveSession(model="haiku", max_budget_usd=0.50)
        session.start()
        session.send("Say exactly HELLO")
        assert session.wait_for("HELLO", timeout=30)
        session.send("Now say GOODBYE")
        assert session.wait_for("GOODBYE", timeout=30)
        session.stop()
        log = session.get_log()
    """

    def __init__(
        self,
        model: str = "haiku",
        max_budget_usd: float | None = None,
        permission_mode: str = "bypassPermissions",
        cwd: str | Path | None = None,
        extra_args: list[str] | None = None,
    ):
        self.model = model
        self.max_budget_usd = max_budget_usd
        self.permission_mode = permission_mode
        self.cwd = str(cwd) if cwd else None
        self.extra_args = extra_args or []
        self._pid: int | None = None
        self._fd: int | None = None
        self._raw_output = b""
        self._send_pos = 0
        self._started = False

    def start(self, ready_timeout: float = 15.0) -> None:
        """Start the claude interactive session and wait for the prompt."""
        if self._started:
            raise RuntimeError("Session already started")

        env = _clean_env()
        cmd = ["claude", "--model", self.model, "--permission-mode", self.permission_mode]
        if self.max_budget_usd is not None:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])
        cmd.extend(self.extra_args)

        pid, fd = pty.fork()
        if pid == 0:
            if self.cwd:
                os.chdir(self.cwd)
            os.execvpe("claude", cmd, env)
            os._exit(1)

        self._pid = pid
        self._fd = fd
        self._started = True

        # Wait for the TUI to render the prompt (❯ character)
        start = time.time()
        while time.time() - start < ready_timeout:
            self._drain(timeout=1.0)
            clean = self.get_clean_output()
            if "\u276f" in clean:
                return
        raise TimeoutError(f"Session did not become ready within {ready_timeout}s")

    def send(self, message: str) -> None:
        """Type a message and press Enter to submit it.

        Records the output position before sending so that wait_for() can
        look at output produced after this send.
        """
        if not self._started or self._fd is None:
            raise RuntimeError("Session not started")

        self._send_pos = len(self._raw_output)
        for ch in message:
            os.write(self._fd, ch.encode())
            time.sleep(0.005)
        time.sleep(0.05)
        os.write(self._fd, b"\r")

    def wait_for(self, pattern: str, timeout: float = 30.0, min_matches: int = 2) -> bool:
        """Wait for a regex pattern to appear in output produced after the last send().

        The TUI echoes typed input, so the pattern from a sent message appears
        at least once as echo. Setting min_matches=2 (the default) ensures we
        see the pattern in the model's response, not just the input echo.
        Set min_matches=1 if you're looking for a pattern that won't be in the
        sent text (e.g., a tool call marker or system message).
        """
        start = time.time()
        pos = getattr(self, "_send_pos", 0)
        while time.time() - start < timeout:
            self._drain(timeout=1.0)
            new_bytes = self._raw_output[pos:]
            new_clean = _strip_ansi(new_bytes.decode("utf-8", errors="replace"))
            matches = len(re.findall(pattern, new_clean))
            if matches >= min_matches:
                return True
        return False

    def stop(self) -> None:
        """Stop the session by sending /exit and then killing the process."""
        if not self._started:
            return

        if self._fd is not None:
            try:
                # Try graceful exit
                self.send("/exit")
                time.sleep(2)
                self._drain(timeout=1.0)
            except OSError:
                pass

        if self._pid is not None:
            try:
                os.kill(self._pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self._pid, 0)
            except ChildProcessError:
                pass

        self._started = False

    def get_raw_output(self) -> bytes:
        """Return all raw bytes received from the PTY."""
        return self._raw_output

    def get_clean_output(self) -> str:
        """Return output with ANSI escape sequences stripped."""
        return _strip_ansi(self._raw_output.decode("utf-8", errors="replace"))

    def get_session_id(self) -> str | None:
        """Extract session ID from the output if visible."""
        clean = self.get_clean_output()
        match = re.search(r"session[:\s]+([0-9a-f-]{36})", clean, re.IGNORECASE)
        return match.group(1) if match else None

    def get_subagent_logs(self, project_dir: str | Path) -> list[Path]:
        """Find subagent JSONL logs for this session in the claude projects directory.

        The session must have been started with a specific project directory
        so we can locate the logs under ~/.claude/projects/<slug>/<session-id>/subagents/.
        """
        claude_dir = Path.home() / ".claude" / "projects"
        project_slug = str(Path(project_dir).resolve()).replace("/", "-")
        if project_slug.startswith("-"):
            project_slug = project_slug
        else:
            project_slug = "-" + project_slug

        project_session_dir = claude_dir / project_slug
        if not project_session_dir.is_dir():
            return []

        logs = []
        for session_dir in project_session_dir.iterdir():
            if session_dir.is_dir():
                subagents_dir = session_dir / "subagents"
                if subagents_dir.is_dir():
                    logs.extend(sorted(subagents_dir.glob("*.jsonl")))
        return logs

    def _drain(self, timeout: float = 0.5) -> None:
        """Read available data from the PTY without blocking."""
        if self._fd is None:
            return
        end = time.time() + timeout
        while time.time() < end:
            ready, _, _ = select.select([self._fd], [], [], min(0.1, end - time.time()))
            if ready:
                try:
                    data = os.read(self._fd, 4096)
                    if data:
                        self._raw_output += data
                    else:
                        break
                except OSError:
                    break
            else:
                break
