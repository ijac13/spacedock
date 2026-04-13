.PHONY: test-static test-e2e

TEST ?= tests/test_gate_guardrail.py
RUNTIME ?= claude

test-static:
	unset CLAUDECODE && uv run --with pytest python -m pytest tests/ --ignore=tests/fixtures -q

test-e2e:
	unset CLAUDECODE && uv run $(TEST) --runtime $(RUNTIME)
