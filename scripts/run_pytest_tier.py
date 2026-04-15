#!/usr/bin/env python3
# ABOUTME: Runs a pytest tier command and optionally treats "no tests collected" as success.
# ABOUTME: Used by live Makefile targets whose marker split can intentionally leave one tier empty.

from __future__ import annotations

import argparse
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a pytest tier command with optional exit-5 normalization."
    )
    parser.add_argument(
        "--allow-no-tests",
        action="store_true",
        help="Treat pytest exit code 5 (no tests collected) as success.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to execute. Pass it after `--`.",
    )
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("missing command; pass the wrapped command after `--`")
    return args


def main() -> int:
    args = parse_args()
    result = subprocess.run(args.command)
    if args.allow_no_tests and result.returncode == 5:
        return 0
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
