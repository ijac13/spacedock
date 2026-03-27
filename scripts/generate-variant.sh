#!/bin/bash
# ABOUTME: Generates terminology variant templates from nautical source templates.
# ABOUTME: Reads a mapping file and applies substitutions to produce variant output.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAPPING=""
OUTPUT=""

usage() {
  echo "Usage: $0 --mapping <mapping-file> --output <output-dir>"
  echo ""
  echo "Generates variant agent templates by applying terminology substitutions"
  echo "from the nautical source templates in templates/."
  echo ""
  echo "  --mapping  Path to a .map file (one substitution per line, old=new)"
  echo "  --output   Output directory for generated templates"
  echo ""
  echo "Mapping file format:"
  echo "  Lines with .md= are filename mappings (e.g., first-officer.md=orchestrator.md)"
  echo "  All other lines are text substitutions (e.g., first officer=orchestrator)"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --mapping)  MAPPING="$2"; shift 2 ;;
    --output)   OUTPUT="$2"; shift 2 ;;
    --help|-h)  usage ;;
    *)          echo "Unknown option: $1"; usage ;;
  esac
done

if [ -z "$MAPPING" ] || [ -z "$OUTPUT" ]; then
  echo "ERROR: --mapping and --output are required"
  usage
fi

if [ ! -f "$MAPPING" ]; then
  echo "ERROR: mapping file not found: $MAPPING"
  exit 1
fi

# Parse the mapping file into sed args and filename renames (parallel arrays)
SED_ARGS=()
RENAME_FROM=()
RENAME_TO=()

while IFS='=' read -r old new; do
  # Skip empty lines and comments
  [ -z "$old" ] && continue
  case "$old" in \#*) continue ;; esac

  if echo "$old" | grep -q '\.md$'; then
    # Filename mapping
    RENAME_FROM+=("$old")
    RENAME_TO+=("$new")
  else
    # Text substitution — build sed expression
    # Escape sed special characters in old and new
    old_escaped=$(printf '%s\n' "$old" | sed 's/[&/\]/\\&/g')
    new_escaped=$(printf '%s\n' "$new" | sed 's/[&/\]/\\&/g')
    SED_ARGS+=("-e" "s/${old_escaped}/${new_escaped}/g")
  fi
done < "$MAPPING"

if [ ${#SED_ARGS[@]} -eq 0 ]; then
  echo "ERROR: no text substitutions found in mapping file"
  exit 1
fi

# Look up a filename rename. Returns the new name or the original if no mapping.
lookup_rename() {
  local filename="$1"
  local i=0
  while [ $i -lt ${#RENAME_FROM[@]} ]; do
    if [ "${RENAME_FROM[$i]}" = "$filename" ]; then
      echo "${RENAME_TO[$i]}"
      return
    fi
    i=$((i + 1))
  done
  echo "$filename"
}

# Create output directory
mkdir -p "$OUTPUT"

SOURCE_DIR="$REPO_ROOT/templates"

# Process each source template (markdown files only, not status script)
for src_file in "$SOURCE_DIR"/*.md; do
  src_basename="$(basename "$src_file")"

  # Determine output filename
  out_basename="$(lookup_rename "$src_basename")"
  out_file="$OUTPUT/$out_basename"

  # Apply all text substitutions
  sed "${SED_ARGS[@]}" "$src_file" > "$out_file"

  echo "  $src_basename -> $out_basename"
done

echo "Generated $(ls "$OUTPUT"/*.md 2>/dev/null | wc -l | tr -d ' ') templates in $OUTPUT"
