---
title: Use YAML frontmatter in generated README instead of HTML comments
status: backlog
source: CL feedback
started:
completed:
verdict:
score: 0.70
worktree:
---

The generated pipeline README stores metadata as HTML comments:

```html
<!-- commissioned-by: spacedock@0.2.0 -->
<!-- entity-type: product_idea -->
<!-- entity-label: idea -->
<!-- entity-label-plural: ideas -->
```

These should be YAML frontmatter instead:

```yaml
---
commissioned-by: spacedock@0.2.0
entity-type: product_idea
entity-label: idea
entity-label-plural: ideas
---
```

Reasons:
- Consistent with entity file pattern (everything uses YAML frontmatter)
- Standard YAML parsing instead of regex on HTML comments
- The first-officer already knows how to read frontmatter
- Pipeline discovery (future multi-pipeline first-officer) can use the same extraction logic for both README metadata and entity fields
