# ABOUTME: Shared test helpers sourced by all test scripts.
# ABOUTME: Provides pass/fail framework, project setup, claude wrappers, and log extraction.

# --- Test framework ---

FAILURES=0
PASSES=0

pass() {
  PASSES=$((PASSES + 1))
  echo "  PASS: $1"
}

fail() {
  FAILURES=$((FAILURES + 1))
  echo "  FAIL: $1"
}

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    pass "$label"
  else
    fail "$label"
  fi
}

test_init() {
  local test_name="$1"
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[1]}")/.." && pwd)"
  TEST_DIR="$(mktemp -d)"
  LOG_DIR="$TEST_DIR"

  echo "=== $test_name ==="
  echo "Repo root:  $REPO_ROOT"
  echo "Test dir:   $TEST_DIR"
  echo ""
}

test_results() {
  echo ""
  echo "=== Results ==="
  local total=$((PASSES + FAILURES))
  echo "  $PASSES passed, $FAILURES failed (out of $total checks)"
  echo ""

  if [ $FAILURES -gt 0 ]; then
    echo "RESULT: FAIL"
    echo ""
    echo "Debug info:"
    echo "  Test dir:   $TEST_DIR"
    # List log files for convenience
    for f in "$LOG_DIR"/*.jsonl "$LOG_DIR"/*.txt; do
      [ -f "$f" ] && echo "  Log:        $f"
    done
    # Don't clean up on failure so logs can be inspected
    trap - EXIT
    exit 1
  else
    echo "RESULT: PASS"
    exit 0
  fi
}

# Default cleanup trap — scripts can override after sourcing
_test_lib_cleanup() {
  if [ -n "${KEEP_TEST_DIR:-}" ]; then
    echo "Test dir preserved at: $TEST_DIR"
  else
    rm -rf "$TEST_DIR"
  fi
}
trap _test_lib_cleanup EXIT

# --- Project setup ---

create_test_project() {
  cd "$TEST_DIR"
  git init test-project >/dev/null 2>&1
  cd "$TEST_DIR/test-project"
  git commit --allow-empty -m "init" >/dev/null 2>&1
  TEST_PROJECT_DIR="$TEST_DIR/test-project"
}

# setup_fixture "$fixture_name" "$pipeline_dir"
#   Copies a fixture from tests/fixtures/$fixture_name into the test project at $pipeline_dir.
#   Sets FIXTURE_DIR for reference.
setup_fixture() {
  local fixture_name="$1"
  local pipeline_dir="$2"
  FIXTURE_DIR="$REPO_ROOT/tests/fixtures/$fixture_name"

  cd "$TEST_PROJECT_DIR"
  mkdir -p "$pipeline_dir"

  # Copy all files from fixture root (not subdirectories)
  for f in "$FIXTURE_DIR"/*; do
    [ -f "$f" ] && cp "$f" "$pipeline_dir/"
  done

  # Copy subdirectories if they exist (e.g., _mods/)
  for d in "$FIXTURE_DIR"/*/; do
    [ -d "$d" ] && cp -R "$d" "$pipeline_dir/"
  done

  # Make status script executable if present
  [ -f "$pipeline_dir/status" ] && chmod +x "$pipeline_dir/status"
}

# generate_first_officer "$pipeline_dir" [mission] [entity_label] [entity_label_plural] [captain] [first_stage] [last_stage] [spacedock_version]
#   Runs sed substitution on templates/first-officer.md into .claude/agents/first-officer.md.
#   Derives project_name from the test-project directory basename.
generate_first_officer() {
  local pipeline_dir="$1"
  local mission="${2:-Test}"
  local entity_label="${3:-task}"
  local entity_label_plural="${4:-tasks}"
  local captain="${5:-CL}"
  local first_stage="${6:-backlog}"
  local last_stage="${7:-done}"
  local spacedock_version="${8:-test}"
  local dir_basename
  dir_basename="$(basename "$pipeline_dir")"

  cd "$TEST_PROJECT_DIR"
  mkdir -p .claude/agents
  sed \
    -e "s|__MISSION__|${mission}|g" \
    -e "s|__DIR__|${pipeline_dir}|g" \
    -e "s|__DIR_BASENAME__|${dir_basename}|g" \
    -e "s|__PROJECT_NAME__|test-project|g" \
    -e "s|__ENTITY_LABEL__|${entity_label}|g" \
    -e "s|__ENTITY_LABEL_PLURAL__|${entity_label_plural}|g" \
    -e "s|__CAPTAIN__|${captain}|g" \
    -e "s|__FIRST_STAGE__|${first_stage}|g" \
    -e "s|__LAST_STAGE__|${last_stage}|g" \
    -e "s|__SPACEDOCK_VERSION__|${spacedock_version}|g" \
    "$REPO_ROOT/templates/first-officer.md" > .claude/agents/first-officer.md
}

# --- Commission ---

# run_commission "$prompt" [extra_args...]
#   Runs claude -p with standard commission flags. Writes to $LOG_DIR/commission-log.jsonl.
#   Sets COMMISSION_EXIT with the exit code.
run_commission() {
  local prompt="$1"
  shift

  cd "$TEST_PROJECT_DIR"

  COMMISSION_EXIT=0
  claude -p "$prompt" \
    --plugin-dir "$REPO_ROOT" \
    --permission-mode bypassPermissions \
    --verbose \
    --output-format stream-json \
    "$@" \
    2>&1 > "$LOG_DIR/commission-log.jsonl" || COMMISSION_EXIT=$?

  echo ""
  if [ $COMMISSION_EXIT -ne 0 ]; then
    echo "WARNING: claude exited with code $COMMISSION_EXIT"
  fi

  # Auto-extract stats
  if [ -f "$LOG_DIR/commission-log.jsonl" ]; then
    extract_stats "$LOG_DIR/commission-log.jsonl" "commission"
  fi
}

# --- First officer ---

# run_first_officer "$prompt" [extra_args...]
#   Runs claude -p --agent first-officer with standard flags. Writes to $LOG_DIR/fo-log.jsonl.
#   Sets FO_EXIT with the exit code.
run_first_officer() {
  local prompt="$1"
  shift

  cd "$TEST_PROJECT_DIR"

  FO_EXIT=0
  claude -p "$prompt" \
    --agent first-officer \
    --permission-mode bypassPermissions \
    --verbose \
    --output-format stream-json \
    "$@" \
    2>&1 > "$LOG_DIR/fo-log.jsonl" || FO_EXIT=$?

  echo ""
  if [ $FO_EXIT -ne 0 ]; then
    echo "WARNING: first officer exited with code $FO_EXIT"
  fi

  # Auto-extract stats
  if [ -f "$LOG_DIR/fo-log.jsonl" ]; then
    extract_stats "$LOG_DIR/fo-log.jsonl" "fo"
  fi
}

# --- Log extraction ---

# extract_agent_calls "$log_file" ["$output_file"]
#   Extracts Agent() tool calls from a stream-json log.
#   Writes subagent_type, name, and prompt_preview per call.
extract_agent_calls() {
  local log_file="$1"
  local output_file="${2:-$LOG_DIR/agent-calls.txt}"

  python3 -c "
import json, sys

agent_calls = []

with open('$log_file') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'tool_use' and block.get('name') == 'Agent':
                        inp = block.get('input', {})
                        agent_calls.append({
                            'subagent_type': inp.get('subagent_type', ''),
                            'name': inp.get('name', ''),
                            'prompt': inp.get('prompt', ''),
                        })
        except:
            pass

with open('$output_file', 'w') as f:
    for call in agent_calls:
        f.write(f\"subagent_type={call['subagent_type']} name={call['name']}\n\")
        f.write(f\"prompt_preview={call['prompt'][:200]}\n\")
        f.write('---\n')
" 2>/dev/null
}

# extract_fo_texts "$log_file" ["$output_file"]
#   Extracts text blocks from assistant messages.
extract_fo_texts() {
  local log_file="$1"
  local output_file="${2:-$LOG_DIR/fo-texts.txt}"

  python3 -c "
import json, sys

fo_texts = []

with open('$log_file') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'text':
                        fo_texts.append(block['text'])
        except:
            pass

with open('$output_file', 'w') as f:
    f.write('\n'.join(fo_texts))
" 2>/dev/null
}

# extract_tool_calls "$log_file" ["$output_file"]
#   Extracts all tool_use blocks from assistant messages as JSON array.
extract_tool_calls() {
  local log_file="$1"
  local output_file="${2:-$LOG_DIR/tool-calls.json}"

  python3 -c "
import json, sys

tool_calls = []

with open('$log_file') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'tool_use':
                        tool_calls.append({
                            'name': block.get('name', ''),
                            'input': block.get('input', {})
                        })
        except:
            pass

with open('$output_file', 'w') as f:
    json.dump(tool_calls, f, indent=2)
" 2>/dev/null
}

# extract_agent_prompt "$log_file" ["$output_file"]
#   Extracts the prompt from the first Agent() tool call (for single-dispatch tests).
extract_agent_prompt() {
  local log_file="$1"
  local output_file="${2:-$LOG_DIR/agent-prompt.txt}"

  python3 -c "
import json, sys

agent_prompt = ''

with open('$log_file') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get('type') == 'assistant' and 'message' in obj:
                for block in obj['message'].get('content', []):
                    if block.get('type') == 'tool_use' and block.get('name') == 'Agent':
                        agent_prompt = block.get('input', {}).get('prompt', '')
        except:
            pass

with open('$output_file', 'w') as f:
    f.write(agent_prompt)
" 2>/dev/null
}

# --- Stats ---

# extract_stats "$log_file" "$phase_name"
#   Extracts wallclock, message counts, model delegation, and token usage from a stream-json log.
#   Prints to stdout and writes to $LOG_DIR/stats-$phase_name.txt.
extract_stats() {
  local log_file="$1"
  local phase_name="$2"
  local output_file="$LOG_DIR/stats-${phase_name}.txt"

  python3 -c "
import json, sys

first_ts = None
last_ts = None
assistant_count = 0
tool_result_count = 0
model_counts = {}
input_tokens = 0
output_tokens = 0
cache_read = 0
cache_write = 0

with open('$log_file') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)

            # Timestamps
            ts = obj.get('timestamp')
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            msg_type = obj.get('type', '')

            if msg_type == 'assistant' and 'message' in obj:
                assistant_count += 1
                model = obj['message'].get('model', obj.get('model', 'unknown'))
                model_counts[model] = model_counts.get(model, 0) + 1
                usage = obj['message'].get('usage', {})
                input_tokens += usage.get('input_tokens', 0)
                output_tokens += usage.get('output_tokens', 0)
                cache_read += usage.get('cache_read_input_tokens', 0)
                cache_write += usage.get('cache_creation_input_tokens', 0)
            elif msg_type == 'tool_result':
                tool_result_count += 1
        except:
            pass

# Wallclock calculation
wallclock = '?'
if first_ts and last_ts:
    from datetime import datetime
    try:
        # Try ISO format with fractional seconds
        fmt = '%Y-%m-%dT%H:%M:%S'
        t1 = first_ts[:19]
        t2 = last_ts[:19]
        d1 = datetime.fromisoformat(t1)
        d2 = datetime.fromisoformat(t2)
        delta = int((d2 - d1).total_seconds())
        wallclock = f'{delta}s'
    except:
        wallclock = '?'

lines = []
lines.append(f'=== Stats: $phase_name ===')
lines.append(f'  Wallclock:        {wallclock}')
lines.append(f'  Messages:         {assistant_count} assistant, {tool_result_count} tool_result')
model_str = ', '.join(f'{m}: {c}' for m, c in sorted(model_counts.items()))
lines.append(f'  Model delegation: {model_str}')
lines.append(f'  Input tokens:     {input_tokens:,}')
lines.append(f'  Output tokens:    {output_tokens:,}')
lines.append(f'  Cache read:       {cache_read:,}')
lines.append(f'  Cache write:      {cache_write:,}')

output = '\n'.join(lines)
print(output)

with open('$output_file', 'w') as f:
    f.write(output + '\n')
" 2>/dev/null || true
}
