#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit tests for the live-tier pytest exit-code wrapper.
# ABOUTME: Verifies optional normalization of pytest's "no tests collected" exit code.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_pytest_tier.py"


def run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        cwd=REPO_ROOT,
        text=True,
    )


def test_run_pytest_tier_preserves_no_tests_collected_without_opt_in(tmp_path):
    result = run_helper(
        "--",
        sys.executable,
        "-m",
        "pytest",
        str(tmp_path),
        "--collect-only",
        "-q",
    )

    assert result.returncode == 5
    assert "no tests collected" in (result.stdout + result.stderr)


def test_run_pytest_tier_allows_no_tests_collected_with_opt_in(tmp_path):
    result = run_helper(
        "--allow-no-tests",
        "--",
        sys.executable,
        "-m",
        "pytest",
        str(tmp_path),
        "--collect-only",
        "-q",
    )

    assert result.returncode == 0
    assert "no tests collected" in (result.stdout + result.stderr)


def test_run_pytest_tier_preserves_real_failures():
    result = run_helper(
        "--allow-no-tests",
        "--",
        sys.executable,
        "-c",
        "import sys; sys.exit(3)",
    )

    assert result.returncode == 3
