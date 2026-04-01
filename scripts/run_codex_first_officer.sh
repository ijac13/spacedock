#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <workflow-dir> [codex-exec-args...]" >&2
  exit 2
fi

workflow_arg="$1"
shift

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
project_root="$(git rev-parse --show-toplevel)"
workflow_dir="$(cd "$project_root" && cd "$workflow_arg" && pwd)"
prompt_file="$repo_root/references/codex-first-officer-prompt.md"

if [ ! -f "$workflow_dir/README.md" ]; then
  echo "Workflow README not found at $workflow_dir/README.md" >&2
  exit 2
fi

if [ ! -f "$prompt_file" ]; then
  echo "Prompt file not found at $prompt_file" >&2
  exit 2
fi

{
  cat "$prompt_file"
  printf '\n\n## Workflow Target\n\nManage the workflow at: %s\n' "$workflow_dir"
} | codex exec \
  --json \
  --ephemeral \
  --skip-git-repo-check \
  --enable multi_agent \
  --dangerously-bypass-approvals-and-sandbox \
  -C "$project_root" \
  "$@" \
  -
