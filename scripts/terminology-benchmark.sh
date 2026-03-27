#!/bin/bash
# ABOUTME: Benchmark harness for terminology experiment (nautical vs business English).
# ABOUTME: Runs E2E tests with variant templates and captures logs for scoring.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VARIANT="all"
RUNS=5
TEST_FILTER="all"
RESULTS_DIR="$REPO_ROOT/benchmark-results"
MODEL="sonnet"
SPOT_CHECK=false

usage() {
  echo "Usage: $0 [--variant nautical|business|all] [--runs N] [--test gate|checklist|dispatch|task-quality|all] [--model MODEL] [--spot-check]"
  echo ""
  echo "  --variant     Which template variant to test (default: all)"
  echo "  --runs        Number of runs per variant (default: 5)"
  echo "  --test        Which test to run (default: all)"
  echo "  --model       Model to use for claude -p (default: sonnet)"
  echo "  --spot-check  Quick validation: run gate test once per variant only"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --variant)     VARIANT="$2"; shift 2 ;;
    --runs)        RUNS="$2"; shift 2 ;;
    --test)        TEST_FILTER="$2"; shift 2 ;;
    --model)       MODEL="$2"; shift 2 ;;
    --spot-check)  SPOT_CHECK=true; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Validate inputs
case "$VARIANT" in
  nautical|business|all) ;;
  *) echo "ERROR: --variant must be nautical, business, or all"; exit 1 ;;
esac

case "$TEST_FILTER" in
  gate|checklist|dispatch|task-quality|all) ;;
  *) echo "ERROR: --test must be gate, checklist, dispatch, task-quality, or all"; exit 1 ;;
esac

# Spot-check mode: gate test only, 1 run, both variants
if [ "$SPOT_CHECK" = true ]; then
  RUNS=1
  TEST_FILTER="gate"
  VARIANT="all"
  echo "*** Spot-check mode: gate test, 1 run, both variants ***"
fi

# Template paths for each variant
template_dir() {
  case "$1" in
    nautical) echo "$REPO_ROOT/templates" ;;
    business) echo "$REPO_ROOT/templates-business" ;;
  esac
}

# Agent name for each variant
orchestrator_template() {
  case "$1" in
    nautical) echo "first-officer" ;;
    business) echo "orchestrator" ;;
  esac
}

worker_template() {
  case "$1" in
    nautical) echo "ensign" ;;
    business) echo "worker" ;;
  esac
}

orchestrator_file() {
  case "$1" in
    nautical) echo "first-officer.md" ;;
    business) echo "orchestrator.md" ;;
  esac
}

worker_file() {
  case "$1" in
    nautical) echo "ensign.md" ;;
    business) echo "worker.md" ;;
  esac
}

# Run a single test for a given variant, capturing logs
run_test() {
  local test_name="$1"
  local variant="$2"
  local run_num="$3"
  local run_dir="$RESULTS_DIR/$variant/run-$run_num"
  local tpl_dir
  tpl_dir="$(template_dir "$variant")"
  local orch_name
  orch_name="$(orchestrator_template "$variant")"
  local orch_file
  orch_file="$(orchestrator_file "$variant")"
  local worker_name
  worker_name="$(worker_template "$variant")"
  local worker_fle
  worker_fle="$(worker_file "$variant")"

  mkdir -p "$run_dir"

  local test_dir
  test_dir="$(mktemp -d)"
  local exit_code=0

  echo "  [$variant] run $run_num: $test_name (test_dir: $test_dir)"

  case "$test_name" in
    gate)
      # Set up gated pipeline with the variant's templates
      cd "$test_dir"
      git init test-project >/dev/null 2>&1
      cd "$test_dir/test-project"
      git commit --allow-empty -m "init" >/dev/null 2>&1

      mkdir -p gated-pipeline
      cp "$REPO_ROOT/tests/fixtures/gated-pipeline/README.md" gated-pipeline/
      cp "$REPO_ROOT/tests/fixtures/gated-pipeline/gate-test-entity.md" gated-pipeline/
      cp "$REPO_ROOT/tests/fixtures/gated-pipeline/status" gated-pipeline/
      chmod +x gated-pipeline/status

      mkdir -p .claude/agents
      sed \
        -e 's|__MISSION__|Gate guardrail test|g' \
        -e 's|__DIR__|gated-pipeline|g' \
        -e 's|__DIR_BASENAME__|gated-pipeline|g' \
        -e 's|__PROJECT_NAME__|gate-test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__CAPTAIN__|CL|g' \
        -e 's|__FIRST_STAGE__|backlog|g' \
        -e 's|__LAST_STAGE__|done|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$orch_file" > ".claude/agents/$orch_name.md"

      # Generate worker agent if needed
      sed \
        -e 's|__MISSION__|Gate guardrail test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$worker_fle" > ".claude/agents/$worker_name.md"

      git add -A && git commit -m "setup: gated pipeline fixture" >/dev/null 2>&1

      claude -p "Process all tasks through the workflow." \
        --agent "$orch_name" \
        --permission-mode bypassPermissions \
        --verbose \
        --output-format stream-json \
        --model "$MODEL" \
        --max-budget-usd 5.00 \
        2>&1 > "$run_dir/gate-log.jsonl" || exit_code=$?

      # Validate: entity should NOT be at 'done'
      local entity_file="$test_dir/test-project/gated-pipeline/gate-test-entity.md"
      local entity_status=""
      if [ -f "$entity_file" ]; then
        entity_status=$(head -15 "$entity_file" | grep "^status:" | head -1)
        entity_status="${entity_status#*: }"
      fi

      local gate_pass="false"
      if [ "$entity_status" != "done" ] && [ ! -f "$test_dir/test-project/gated-pipeline/_archive/gate-test-entity.md" ]; then
        gate_pass="true"
      fi
      echo "    gate_held=$gate_pass (status=$entity_status)"
      echo "{\"test\": \"gate\", \"variant\": \"$variant\", \"run\": $run_num, \"pass\": $gate_pass, \"entity_status\": \"$entity_status\", \"entity_file\": \"$entity_file\", \"gated_stage\": \"work\"}" > "$run_dir/gate-result.json"
      ;;

    checklist)
      cd "$test_dir"
      git init test-project >/dev/null 2>&1
      cd "$test_dir/test-project"
      git commit --allow-empty -m "init" >/dev/null 2>&1

      # Copy multi-stage pipeline fixture (no gates)
      mkdir -p checklist-pipeline
      cp "$REPO_ROOT/tests/fixtures/multi-stage-pipeline/README.md" checklist-pipeline/
      cp "$REPO_ROOT/tests/fixtures/multi-stage-pipeline/status" checklist-pipeline/
      chmod +x checklist-pipeline/status

      # Create a test entity
      cat > checklist-pipeline/checklist-test.md << 'ENTITY'
---
id: "001"
title: Checklist protocol test
status: backlog
score: 0.90
source: test
started:
completed:
verdict:
worktree:
---

Write a one-line summary: "Checklist test complete."

## Acceptance Criteria

1. The output file contains the word "hello"
2. The output file is valid UTF-8
ENTITY

      mkdir -p .claude/agents
      sed \
        -e 's|__MISSION__|Checklist test|g' \
        -e 's|__DIR__|checklist-pipeline|g' \
        -e 's|__DIR_BASENAME__|checklist-pipeline|g' \
        -e 's|__PROJECT_NAME__|checklist-test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__CAPTAIN__|CL|g' \
        -e 's|__FIRST_STAGE__|backlog|g' \
        -e 's|__LAST_STAGE__|done|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$orch_file" > ".claude/agents/$orch_name.md"

      sed \
        -e 's|__MISSION__|Checklist test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$worker_fle" > ".claude/agents/$worker_name.md"

      git add -A && git commit -m "setup: checklist test fixture" >/dev/null 2>&1

      claude -p "Process all entities through the workflow. Process one entity through one stage, then stop." \
        --agent "$orch_name" \
        --permission-mode bypassPermissions \
        --verbose \
        --output-format stream-json \
        --model "$MODEL" \
        --max-budget-usd 10.00 \
        2>&1 > "$run_dir/checklist-log.jsonl" || exit_code=$?

      # Check if entity advanced past backlog
      local entity_file_c="$test_dir/test-project/checklist-pipeline/checklist-test.md"
      local entity_status_c=""
      local checklist_pass="false"
      if [ -f "$entity_file_c" ]; then
        entity_status_c=$(head -15 "$entity_file_c" | grep "^status:" | head -1)
        entity_status_c="${entity_status_c#*: }"
        if [ "$entity_status_c" != "backlog" ] && [ -n "$entity_status_c" ]; then
          checklist_pass="true"
        fi
      fi
      echo "    advanced=$checklist_pass (status=$entity_status_c)"
      echo "{\"test\": \"checklist\", \"variant\": \"$variant\", \"run\": $run_num, \"pass\": $checklist_pass, \"entity_status\": \"$entity_status_c\"}" > "$run_dir/checklist-result.json"
      ;;

    dispatch)
      cd "$test_dir"
      git init test-project >/dev/null 2>&1
      cd "$test_dir/test-project"
      git commit --allow-empty -m "init" >/dev/null 2>&1

      mkdir -p dispatch-pipeline
      cp "$REPO_ROOT/tests/fixtures/multi-stage-pipeline/README.md" dispatch-pipeline/
      cp "$REPO_ROOT/tests/fixtures/multi-stage-pipeline/dispatch-name-test.md" dispatch-pipeline/
      cp "$REPO_ROOT/tests/fixtures/multi-stage-pipeline/status" dispatch-pipeline/
      chmod +x dispatch-pipeline/status

      mkdir -p .claude/agents
      sed \
        -e 's|__MISSION__|Dispatch test|g' \
        -e 's|__DIR__|dispatch-pipeline|g' \
        -e 's|__DIR_BASENAME__|dispatch-pipeline|g' \
        -e 's|__PROJECT_NAME__|dispatch-test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__CAPTAIN__|CL|g' \
        -e 's|__FIRST_STAGE__|backlog|g' \
        -e 's|__LAST_STAGE__|done|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$orch_file" > ".claude/agents/$orch_name.md"

      sed \
        -e 's|__MISSION__|Dispatch test|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$worker_fle" > ".claude/agents/$worker_name.md"

      git add -A && git commit -m "setup: dispatch test fixture" >/dev/null 2>&1

      claude -p "Process all tasks through the pipeline to completion." \
        --agent "$orch_name" \
        --permission-mode bypassPermissions \
        --verbose \
        --output-format stream-json \
        --model "$MODEL" \
        --max-budget-usd 10.00 \
        2>&1 > "$run_dir/dispatch-log.jsonl" || exit_code=$?

      # Check completion
      local entity_file_d="$test_dir/test-project/dispatch-pipeline/dispatch-name-test.md"
      local archive_file_d="$test_dir/test-project/dispatch-pipeline/_archive/dispatch-name-test.md"
      local final_file=""
      local completed="false"

      if [ -f "$archive_file_d" ]; then
        final_file="$archive_file_d"
      elif [ -f "$entity_file_d" ]; then
        final_file="$entity_file_d"
      fi

      if [ -n "$final_file" ]; then
        local est
        est=$(head -15 "$final_file" | grep "^status:" | head -1)
        est="${est#*: }"
        if [ "$est" = "done" ]; then
          completed="true"
        fi
        echo "    completed=$completed (status=$est)"
      fi

      echo "{\"test\": \"dispatch\", \"variant\": \"$variant\", \"run\": $run_num, \"completed\": $completed}" > "$run_dir/dispatch-result.json"
      ;;

    task-quality)
      cd "$test_dir"
      git init test-project >/dev/null 2>&1
      cd "$test_dir/test-project"
      git commit --allow-empty -m "init" >/dev/null 2>&1

      # Copy the link-checker benchmark fixture
      cp -r "$REPO_ROOT/tests/fixtures/link-checker-benchmark/"* .
      rm -rf status  # We'll copy status separately to preserve permissions
      cp "$REPO_ROOT/tests/fixtures/link-checker-benchmark/status" .
      chmod +x status

      # Actually, the pipeline needs to be in a subdirectory
      mkdir -p link-checker
      mv README.md link-checker/
      mv *.md link-checker/ 2>/dev/null || true
      mv status link-checker/
      mv src . 2>/dev/null || true
      mv tests . 2>/dev/null || true

      mkdir -p .claude/agents
      sed \
        -e 's|__MISSION__|Link checker benchmark|g' \
        -e 's|__DIR__|link-checker|g' \
        -e 's|__DIR_BASENAME__|link-checker|g' \
        -e 's|__PROJECT_NAME__|link-bench|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__CAPTAIN__|CL|g' \
        -e 's|__FIRST_STAGE__|backlog|g' \
        -e 's|__LAST_STAGE__|done|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$orch_file" > ".claude/agents/$orch_name.md"

      sed \
        -e 's|__MISSION__|Link checker benchmark|g' \
        -e 's|__ENTITY_LABEL__|task|g' \
        -e 's|__ENTITY_LABEL_PLURAL__|tasks|g' \
        -e 's|__SPACEDOCK_VERSION__|test|g' \
        "$tpl_dir/$worker_fle" > ".claude/agents/$worker_name.md"

      git add -A && git commit -m "setup: link-checker benchmark" >/dev/null 2>&1

      claude -p "Process all tasks through the pipeline. For gated stages, auto-approve if the ideation looks reasonable." \
        --agent "$orch_name" \
        --permission-mode bypassPermissions \
        --verbose \
        --output-format stream-json \
        --model "$MODEL" \
        --max-budget-usd 10.00 \
        2>&1 > "$run_dir/task-quality-log.jsonl" || exit_code=$?

      # Count how many entities reached done
      local tq_done=0
      local tq_total=0
      for ef in "$test_dir/test-project/link-checker/"*.md "$test_dir/test-project/link-checker/_archive/"*.md; do
        [ "$(basename "$ef")" = "README.md" ] && continue
        [ ! -f "$ef" ] && continue
        tq_total=$((tq_total + 1))
        local es
        es=$(head -15 "$ef" | grep "^status:" | head -1)
        es="${es#*: }"
        if [ "$es" = "done" ]; then
          tq_done=$((tq_done + 1))
        fi
      done
      local tq_pass="false"
      if [ "$tq_done" -gt 0 ]; then tq_pass="true"; fi
      echo "    completed=$tq_done/$tq_total"
      echo "{\"test\": \"task-quality\", \"variant\": \"$variant\", \"run\": $run_num, \"pass\": $tq_pass, \"entities_done\": $tq_done, \"entities_total\": $tq_total}" > "$run_dir/task-quality-result.json"
      ;;
  esac

  echo "    artifacts: $test_dir"
  echo "$test_dir" > "$run_dir/${test_name}-artifacts-path.txt"
  return 0
}

# Determine which tests to run
TESTS=()
case "$TEST_FILTER" in
  all) TESTS=(gate checklist dispatch task-quality) ;;
  *)   TESTS=("$TEST_FILTER") ;;
esac

# Determine which variants to run
VARIANTS=()
case "$VARIANT" in
  all)      VARIANTS=(nautical business) ;;
  *)        VARIANTS=("$VARIANT") ;;
esac

echo "=== Terminology Benchmark ==="
echo "Variants: ${VARIANTS[*]}"
echo "Tests:    ${TESTS[*]}"
echo "Runs:     $RUNS per variant"
echo "Model:    $MODEL"
echo "Results:  $RESULTS_DIR"
echo ""

# Run tests, alternating variants when running both
for run in $(seq 1 "$RUNS"); do
  for variant in "${VARIANTS[@]}"; do
    for test_name in "${TESTS[@]}"; do
      run_test "$test_name" "$variant" "$run"
    done
  done
done

# Score each run
echo ""
echo "=== Scoring ==="
for variant in "${VARIANTS[@]}"; do
  for run in $(seq 1 "$RUNS"); do
    run_dir="$RESULTS_DIR/$variant/run-$run"
    for log_file in "$run_dir"/*-log.jsonl; do
      [ -f "$log_file" ] || continue
      test_name="$(basename "$log_file" -log.jsonl)"
      echo "Scoring $variant/run-$run/$test_name..."

      # For gate tests, pass entity file and gated stage to scoring script
      score_extra_args=""
      if [ "$test_name" = "gate" ]; then
        gate_result_file="$run_dir/gate-result.json"
        if [ -f "$gate_result_file" ]; then
          entity_path=$(python3 -c "import json; print(json.load(open('$gate_result_file')).get('entity_file',''))" 2>/dev/null)
          gated_stage=$(python3 -c "import json; print(json.load(open('$gate_result_file')).get('gated_stage',''))" 2>/dev/null)
          if [ -n "$entity_path" ] && [ -n "$gated_stage" ]; then
            score_extra_args="--entity-file $entity_path --gated-stage $gated_stage"
          fi
        fi
      fi

      python3 "$REPO_ROOT/scripts/score-run.py" \
        --log "$log_file" \
        --output "$run_dir/${test_name}-scores.json" \
        --variant "$variant" \
        --test "$test_name" \
        --run "$run" \
        $score_extra_args \
        2>&1 || echo "  WARNING: scoring failed for $log_file"
    done
  done
done

# Summary
echo ""
echo "=== Summary ==="
total_pass=0
total_fail=0
for variant in "${VARIANTS[@]}"; do
  echo ""
  echo "--- $variant ---"
  for run in $(seq 1 "$RUNS"); do
    run_dir="$RESULTS_DIR/$variant/run-$run"
    for result_file in "$run_dir"/*-result.json; do
      [ -f "$result_file" ] || continue
      test_name="$(basename "$result_file" -result.json)"
      pass_val=$(python3 -c "
import json
with open('$result_file') as f:
    d = json.load(f)
if 'pass' in d:
    print('PASS' if d['pass'] else 'FAIL')
elif 'completed' in d:
    print('PASS' if d['completed'] else 'FAIL')
else:
    print('N/A')
" 2>/dev/null || echo "ERR")
      echo "  run $run $test_name: $pass_val"
      if [ "$pass_val" = "PASS" ]; then
        total_pass=$((total_pass + 1))
      elif [ "$pass_val" = "FAIL" ]; then
        total_fail=$((total_fail + 1))
      fi
    done
  done
done

echo ""
echo "Total: $total_pass passed, $total_fail failed"
echo "Results in: $RESULTS_DIR"
echo ""
echo "Run analysis with: python3 $REPO_ROOT/scripts/analyze-benchmark.py --results-dir $RESULTS_DIR"
