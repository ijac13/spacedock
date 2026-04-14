#!/bin/bash
# ABOUTME: Release script that bumps versions, refits, generates changelog, and tags.
# ABOUTME: Works in a worktree so main stays clean during the release process.
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

MAIN_BRANCH=$(git branch --show-current)
RELEASE_BRANCH="release/$VERSION"
WORKTREE_PATH="$REPO_ROOT/.worktrees/release-$VERSION"
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

# --- Step 1: Create release worktree and bump version ---

echo "Creating release worktree: $WORKTREE_PATH (branch: $RELEASE_BRANCH)"
git worktree add "$WORKTREE_PATH" -b "$RELEASE_BRANCH"
cd "$WORKTREE_PATH"

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

for f in mods/*.md; do
    if [ -f "$f" ] && grep -q '^version:' "$f"; then
        sed -i '' "s/^version: .*$/version: $VERSION/" "$f"
    fi
done

# Sync self-hosted mod copies deterministically. The LLM-driven refit in step 2
# handles narrative scaffolding updates, but mod-copy sync is a byte-equality
# invariant enforced by tests/test_agent_content.py and must not depend on an
# LLM skill execution.
SELF_MODS_DIR="docs/plans/_mods"
if [ -d "$SELF_MODS_DIR" ]; then
    for canonical in mods/*.md; do
        target="$SELF_MODS_DIR/$(basename "$canonical")"
        if [ -f "$target" ]; then
            cp "$canonical" "$target"
        fi
    done
fi

git add "$PLUGIN_JSON" "$MARKETPLACE_JSON" mods/*.md
if [ -d "$SELF_MODS_DIR" ]; then
    git add "$SELF_MODS_DIR"
fi
git commit -m "release: bump version to spacedock@$VERSION"

# --- Step 2: Refit self-hosted workflow ---

SELF_HOSTED_WORKFLOW="docs/plans"
if [ -f "$SELF_HOSTED_WORKFLOW/README.md" ]; then
    echo ""
    echo "=========================================="
    echo "REFIT: Self-hosted workflow ($SELF_HOSTED_WORKFLOW)"
    echo "=========================================="
    echo ""
    echo "Running refit (non-interactive)..."
    echo ""

    REFIT_PROMPT="/spacedock:refit $SELF_HOSTED_WORKFLOW

Accept all changes. When showing diffs, approve all updates (mods, README version stamp). Do not ask for confirmation — proceed automatically."

    CLAUDE_ARGS=(-p "$REFIT_PROMPT" --plugin-dir "$REPO_ROOT" --dangerously-skip-permissions --model opus --effort low)
    if command -v safehouse >/dev/null 2>&1; then
        safehouse --add-dirs ~/.local/state claude "${CLAUDE_ARGS[@]}"
    else
        claude "${CLAUDE_ARGS[@]}"
    fi

    # Commit any refit changes
    if ! git diff-index --quiet HEAD --; then
        git add -A
        git commit -m "refit: upgrade workflow scaffolding to spacedock@$VERSION"
    else
        echo "(No refit changes to commit)"
    fi
fi

# --- Step 3: Generate changelog and tag (no push) ---

CHANGELOG_FILE=$(mktemp)
trap 'rm -f "$CHANGELOG_FILE"' EXIT

if [ -n "$PREV_TAG" ]; then
    LOG_RANGE="$PREV_TAG..HEAD"
else
    LOG_RANGE="HEAD"
fi

RAW_LOG=$(git log "$LOG_RANGE" --oneline --no-decorate)

if command -v claude >/dev/null 2>&1; then
    PROMPT="Summarize these git commits into a release changelog for spacedock v$VERSION. Plain text only — no markdown headers, no bold/italic. Start with one sentence describing the major theme of this release. Then list individual changes as '- ' bullet lines. For each bullet, lead with the user value (what upgrading gives you), then briefly describe what changed at a high level. Ignore workflow state changes (dispatch/done/backlog/validation commits, archived task frontmatter updates, entity file changes under docs/plans/). Group related commits into single entries."
    if [ -n "$EXTRA_INSTRUCTIONS" ]; then
        PROMPT="$PROMPT Additional instructions: $EXTRA_INSTRUCTIONS"
    fi
    echo "$RAW_LOG" | claude -p "$PROMPT" --model opus --effort low > "$CHANGELOG_FILE" 2>/dev/null || {
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

# Create tag from release branch
echo ""
echo "Creating tag $TAG (local only, not pushed)..."
git tag -a "$TAG" -m "Release $VERSION

$(cat "$CHANGELOG_FILE")"

# Return to main
cd "$REPO_ROOT"

# --- Step 4: Show next steps ---

echo ""
echo "=========================================="
echo "RELEASE PREPARED: $TAG"
echo "=========================================="
echo ""
echo "The release is ready in worktree '$WORKTREE_PATH' (branch '$RELEASE_BRANCH') with tag '$TAG'."
echo "Main branch is untouched. Nothing has been pushed."
echo ""
echo "To review:"
echo "  git log $MAIN_BRANCH..$RELEASE_BRANCH --oneline"
echo "  git diff $MAIN_BRANCH..$RELEASE_BRANCH"
echo ""
echo "To amend the changelog:"
echo "  git tag -d $TAG"
echo "  git tag -a $TAG -m 'Release $VERSION"
echo ""
echo "your changelog here'"
echo ""
echo "To publish:"
echo "  git merge $RELEASE_BRANCH"
echo "  git push origin $MAIN_BRANCH $TAG"
echo "  git worktree remove $WORKTREE_PATH"
echo "  git branch -d $RELEASE_BRANCH"
echo ""
echo "To abort:"
echo "  git worktree remove $WORKTREE_PATH"
echo "  git branch -D $RELEASE_BRANCH"
echo "  git tag -d $TAG"
