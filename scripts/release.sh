#!/bin/bash
# ABOUTME: Interactive release script that bumps versions, generates changelog, tags, and pushes.
# ABOUTME: Updates plugin.json and marketplace.json, creates annotated git tag with changelog.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="${1:-}"
EXTRA_INSTRUCTIONS="${2:-}"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version> [extra_instructions]"
    echo "Example: $0 0.4.0"
    echo "Example: $0 0.4.0 \"Focus on the new commission flow\""
    exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 0.4.0)"
    exit 1
fi

TAG="v$VERSION"

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Error: Tag $TAG already exists"
    exit 1
fi

if ! git diff-index --quiet HEAD --; then
    echo "Error: You have uncommitted changes. Please commit or stash them first."
    exit 1
fi

PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

# Bump version in plugin.json and marketplace.json
PLUGIN_JSON=".claude-plugin/plugin.json"
MARKETPLACE_JSON=".claude-plugin/marketplace.json"

OLD_VERSION=$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])")
echo "Bumping version: $OLD_VERSION -> $VERSION"

python3 -c "
import json, sys
with open('$PLUGIN_JSON', 'r') as f:
    data = json.load(f)
data['version'] = '$VERSION'
with open('$PLUGIN_JSON', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

python3 -c "
import json, sys
with open('$MARKETPLACE_JSON', 'r') as f:
    data = json.load(f)
for plugin in data.get('plugins', []):
    plugin['version'] = '$VERSION'
with open('$MARKETPLACE_JSON', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

git add "$PLUGIN_JSON" "$MARKETPLACE_JSON"
git commit -m "release: bump version to spacedock@$VERSION"

# Refit self-hosted workflow (docs/plans/) with the new version
SELF_HOSTED_WORKFLOW="docs/plans"
if [ -f "$SELF_HOSTED_WORKFLOW/README.md" ]; then
    echo ""
    echo "=========================================="
    echo "REFIT: Self-hosted workflow ($SELF_HOSTED_WORKFLOW)"
    echo "=========================================="
    echo ""
    echo "Running refit..."
    echo ""

    CLAUDE_ARGS=(-p "/spacedock:refit $SELF_HOSTED_WORKFLOW" --plugin-dir "$REPO_ROOT" --dangerously-skip-permissions)
    if command -v safehouse >/dev/null 2>&1; then
        safehouse claude "${CLAUDE_ARGS[@]}"
    else
        claude "${CLAUDE_ARGS[@]}"
    fi

    # Commit any refit changes
    if ! git diff-index --quiet HEAD --; then
        git commit -m "refit: upgrade workflow scaffolding to spacedock@$VERSION" -a
    else
        echo "(No refit changes to commit)"
    fi
fi

# Generate changelog
CHANGELOG_FILE=$(mktemp)
trap 'rm -f "$CHANGELOG_FILE"' EXIT

if [ -n "$PREV_TAG" ]; then
    LOG_RANGE="$PREV_TAG..HEAD"
else
    LOG_RANGE="HEAD"
fi

RAW_LOG=$(git log "$LOG_RANGE" --oneline --no-decorate)

if command -v claude >/dev/null 2>&1; then
    PROMPT="Summarize these git commits into a concise release changelog for spacedock v$VERSION. Focus on shipped user value — what a user of the spacedock plugin gets from upgrading. Ignore workflow state changes (dispatch/done/backlog/validation commits, archived task frontmatter updates, entity file changes under docs/plans/). Group by features and fixes. Be brief — one line per item, no markdown headers, just bullet points."
    if [ -n "$EXTRA_INSTRUCTIONS" ]; then
        PROMPT="$PROMPT Additional instructions: $EXTRA_INSTRUCTIONS"
    fi
    echo "$RAW_LOG" | claude -p "$PROMPT" > "$CHANGELOG_FILE" 2>/dev/null || {
        echo "(Claude unavailable, falling back to git log)"
        echo "$RAW_LOG" > "$CHANGELOG_FILE"
    }
else
    echo "$RAW_LOG" > "$CHANGELOG_FILE"
fi

echo ""
echo "=========================================="
echo "PROPOSED CHANGELOG FOR $TAG"
echo "=========================================="
cat "$CHANGELOG_FILE"
echo ""
echo "=========================================="
echo ""

read -p "Accept this changelog and create release $TAG? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Release cancelled. Version bump commit remains — amend or reset if needed."
    exit 0
fi

echo "Creating tag $TAG..."
git tag -a "$TAG" -m "Release $VERSION

$(cat "$CHANGELOG_FILE")"

echo "Pushing tag and branch to origin..."
git push origin HEAD "$TAG"

echo ""
echo "Release $TAG created and pushed successfully!"
echo ""
echo "GitHub release URL: https://github.com/clkao/spacedock/releases/tag/$TAG"
echo ""
echo "To update your local install:"
echo "  claude plugin marketplace update spacedock"
echo "  claude plugin update spacedock@spacedock"
