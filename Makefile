SHELL := /bin/bash

.PHONY: test-static test-e2e test-live-claude test-live-claude-opus test-live-codex

TEST ?= tests/
RUNTIME ?= claude
LIVE_CLAUDE_WORKERS ?= 2
LIVE_CODEX_WORKERS ?= 2

test-static:
	unset CLAUDECODE && uv run pytest tests/ --ignore=tests/fixtures \
	  -m "not live_claude and not live_codex" -q

# Single-file live override — pass TEST=tests/<file>.py RUNTIME=claude|codex.
# Replaces the old test-e2e-commission target: `make test-e2e TEST=tests/test_commission.py`.
test-e2e:
	unset CLAUDECODE && uv run pytest $(TEST) --runtime $(RUNTIME) -v

test-live-claude:
	unset CLAUDECODE && { \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_claude and serial" --runtime claude -x -v ; SEQ=$$? ; \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_claude and not serial" --runtime claude \
	    -n $(LIVE_CLAUDE_WORKERS) -v ; PAR=$$? ; \
	  test $$SEQ -eq 0 -a $$PAR -eq 0 ; \
	}
	# SKIPPED: test_scaffolding_guardrail.py carries @pytest.mark.skip (see the file). Track: file new task.

# test-live-claude-opus runs the same suite with --model opus --effort low overrides —
# use it to manually verify stronger-model compliance when haiku flakes.
test-live-claude-opus:
	unset CLAUDECODE && { \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_claude and serial" --runtime claude --model opus --effort low -x -v ; SEQ=$$? ; \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_claude and not serial" --runtime claude --model opus --effort low \
	    -n $(LIVE_CLAUDE_WORKERS) -v ; PAR=$$? ; \
	  test $$SEQ -eq 0 -a $$PAR -eq 0 ; \
	}

test-live-codex:
	{ \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_codex and serial" --runtime codex -x -v ; SEQ=$$? ; \
	  uv run pytest tests/ --ignore=tests/fixtures \
	    -m "live_codex and not serial" --runtime codex \
	    -n $(LIVE_CODEX_WORKERS) -v ; PAR=$$? ; \
	  test $$SEQ -eq 0 -a $$PAR -eq 0 ; \
	}
