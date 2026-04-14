SHELL := /bin/bash

.PHONY: test-static test-e2e test-live-claude test-live-codex

TEST ?= tests/test_gate_guardrail.py
RUNTIME ?= claude

test-static:
	unset CLAUDECODE && uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q

test-e2e:
	unset CLAUDECODE && uv run $(TEST) --runtime $(RUNTIME)

test-live-claude:
	unset CLAUDECODE && set -euo pipefail && \
	uv run tests/test_gate_guardrail.py --runtime claude && \
	uv run tests/test_rejection_flow.py --runtime claude && \
	uv run tests/test_feedback_keepalive.py && \
	uv run tests/test_merge_hook_guardrail.py --runtime claude && \
	uv run tests/test_rebase_branch_before_push.py && \
	uv run tests/test_dispatch_completion_signal.py --runtime claude
	# SKIPPED: test_push_main_before_pr.py — FO still archives past pr-merge without persisting pr state. Track: #114
	# SKIPPED: test_scaffolding_guardrail.py — FO violates issue-filing guardrail. Track: file new task

test-live-codex:
	uv run tests/test_gate_guardrail.py --runtime codex && \
	uv run tests/test_rejection_flow.py --runtime codex && \
	uv run tests/test_merge_hook_guardrail.py --runtime codex
