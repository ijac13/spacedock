---
name: test-hook
description: Test mod that records merge hook execution
---

# Test Hook

A minimal mod for testing that merge hooks fire at merge time.

## Hook: merge

When this hook fires, append the entity slug (one per line) to `_merge-hook-fired.txt` in the workflow directory. Use this exact command:

```bash
echo "{slug}" >> {workflow_dir}/_merge-hook-fired.txt
```

Replace `{slug}` with the actual entity slug being merged. Replace `{workflow_dir}` with the actual workflow directory path.

After writing the file, proceed with the default local merge. This hook does NOT handle the merge itself — it only records that the hook was invoked.
