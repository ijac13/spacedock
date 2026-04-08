---
id: 098
title: "pr-merge mod: include Closes #X when entity has linked issue"
status: validation
source: "#48"
started: 2026-04-08T15:43:15Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-pr-merge-closes-issue
issue: "#48"
pr:
---

The pr-merge mod's merge hook creates PRs with a static body. When an entity has a non-empty `issue` field in frontmatter, the PR body should include `Closes {issue}` so GitHub auto-closes the linked issue on merge.

## Stage Report

### 1. Research where the pr-merge mod template lives and how it gets generated/propagated — DONE

The canonical mod source is `/mods/pr-merge.md` in the Spacedock plugin root. During commission (Phase 2c), it is copied to `{dir}/_mods/pr-merge.md` for each workflow. The refit skill propagates updates from the canonical source to existing workflow copies.

### 2. Identify the exact line in the merge hook where the PR body is constructed — DONE

In `mods/pr-merge.md`, line 40, inside the "Hook: merge" section:

```
Create a PR: `gh pr create --base main --head {branch} --title "{entity title}" --body "Workflow entity: {entity title}"`.
```

This is the only place the PR body is constructed. The body is currently a static string with no conditional logic.

### 3. Propose the specific before/after wording for the template change — DONE

**Before (line 40):**
```
Create a PR: `gh pr create --base main --head {branch} --title "{entity title}" --body "Workflow entity: {entity title}"`. If `gh` is not available, warn the captain and fall back to local merge.
```

**After:**
```
Create a PR. Build the PR body: start with `Workflow entity: {entity title}`. If the entity has a non-empty `issue` field, append a blank line and `Closes {issue}` (using the value exactly as it appears in frontmatter, e.g., `#48` or `owner/repo#48`). Then run: `gh pr create --base main --head {branch} --title "{entity title}" --body "{constructed body}"`. If `gh` is not available, warn the captain and fall back to local merge.
```

This keeps the existing body content and conditionally appends the closing reference.

### 4. Define acceptance criteria with test plan for each — DONE

**AC1: Entity with `issue` field set produces `Closes {issue}` in PR body.**
- Test: Static inspection of the mod template — confirm the wording instructs the agent to include `Closes {issue}` when the field is non-empty. Then an E2E test: create an entity with `issue: "#99"`, trigger the merge hook, and verify the `gh pr create` command's `--body` argument contains `Closes #99`.
- Cost: Low. The mod is a natural-language template interpreted by an agent, so the "unit test" is verifying the template wording. E2E requires a real workflow run.

**AC2: Entity with empty `issue` field does NOT include `Closes` in PR body.**
- Test: Create an entity with `issue:` (empty), trigger merge hook, verify PR body is just `Workflow entity: {title}` with no `Closes` line.
- Cost: Low, same as AC1.

**AC3: Issue field formats are passed through verbatim.**
- The mod should not parse or reformat the `issue` value — it uses whatever is in the frontmatter. Formats like `#42`, `owner/repo#42`, or even a full URL should all work because GitHub's `Closes` keyword accepts all of these.
- Test: Verify the template wording says "using the value exactly as it appears in frontmatter" (or equivalent). No separate E2E needed — GitHub handles the parsing.

**AC4: Refit propagates the change to existing workflows.**
- Test: After updating `mods/pr-merge.md`, run refit on an existing workflow (e.g., `docs/plans/`) and verify the `_mods/pr-merge.md` copy is updated.
- Cost: Low — refit is an existing mechanism.

**Test plan summary:** The primary risk is low — this is a one-line wording change to a natural-language template. Static review of the template diff is sufficient to verify AC1-AC3. An E2E test with a real PR would be ideal but is high-cost for the risk level. Recommend: verify via the next real entity that goes through pr-merge (the pilot run for this very entity could serve as the E2E test).

### 5. Consider edge cases — DONE

| Edge case | Handling |
|-----------|----------|
| `issue: "#42"` (standard format) | Appends `Closes #42` — GitHub auto-closes issue 42 |
| `issue: "owner/repo#42"` (cross-repo) | Appends `Closes owner/repo#42` — GitHub handles cross-repo closing |
| `issue:` (empty) | No `Closes` line appended — body unchanged from current behavior |
| `issue: "https://github.com/owner/repo/issues/42"` (full URL) | Appends `Closes https://...` — GitHub accepts URLs in closing keywords |
| `issue: "not-a-number"` (malformed) | Passes through verbatim — GitHub will ignore it. Not our problem to validate. |
| `issue: "#42, #43"` (multiple issues) | Passes through verbatim as `Closes #42, #43`. GitHub does NOT support multiple issues in one `Closes` keyword this way — only the first would close. However, this format doesn't appear in any existing entity. If needed in the future, the schema could be extended to a list. Not in scope now (YAGNI). |
