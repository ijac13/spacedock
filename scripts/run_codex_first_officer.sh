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

if [ ! -f "$workflow_dir/README.md" ]; then
  echo "Workflow README not found at $workflow_dir/README.md" >&2
  exit 2
fi

temp_home="$(mktemp -d)"
trap 'rm -rf "$temp_home"' EXIT

namespace_root="$temp_home/.agents/skills/spacedock"
mkdir -p "$namespace_root"

for skill_dir in "$repo_root"/skills/*; do
  if [ -d "$skill_dir" ] && [ -f "$skill_dir/SKILL.md" ]; then
    ln -s "$skill_dir" "$namespace_root/$(basename "$skill_dir")"
  fi
done

ln -s "$repo_root/skills" "$namespace_root/skills"
ln -s "$repo_root/references" "$namespace_root/references"
ln -s "$HOME/.codex" "$temp_home/.codex"

prompt="$(cat <<EOF
Use the \`spacedock:first-officer\` skill to manage the workflow at \`$workflow_dir\`.

Treat that path as the explicit workflow target. Do not ask to discover alternatives.
Do not narrate setup beyond what is needed to report a blocker or final outcome.
Once you have enough context to dispatch the first worker, dispatch immediately.
Stop after the first meaningful outcome for this run.
EOF
)"

HOME="$temp_home" CODEX_HOME="$temp_home/.codex" \
  codex exec \
    --json \
    --ephemeral \
    --skip-git-repo-check \
    --enable multi_agent \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$project_root" \
    "$@" \
    - <<<"$prompt"
