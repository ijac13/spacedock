# Runtime Live E2E Artifact Preservation Design

**Goal:** Preserve each live test's temp directory in CI and upload it as a GitHub Actions artifact on every `Runtime Live E2E` run.

**Why:** The current live workflow only exposes the outer job log. When a live test fails in CI, the per-test temp directory printed by `TestRunner` is lost with the runner filesystem, which blocks diagnosis of CI-only failures.

## Scope

- Preserve temp directories for both `claude-live` and `codex-live`.
- Store preserved test dirs under a deterministic per-job root instead of anonymous `mkdtemp()` paths.
- Upload those preserved directories as workflow artifacts on every run, not only on failure.

## Design

1. `scripts/test_lib.py` will honor a new environment variable, `SPACEDOCK_TEST_TMP_ROOT`.
   - When set, `TestRunner` will create its temp dir under that root with a stable prefix.
   - Existing behavior remains unchanged when the variable is absent.

2. `.github/workflows/runtime-live-e2e.yml` will set:
   - `KEEP_TEST_DIR=1`
   - `SPACEDOCK_TEST_TMP_ROOT` to a per-job path under `${{ runner.temp }}/spacedock-live/${{ github.job }}`

3. The workflow will upload `${{ env.SPACEDOCK_TEST_TMP_ROOT }}` with `actions/upload-artifact` using `if: always()`.
   - Artifact names should distinguish `claude-live` and `codex-live`.

## Validation

- Offline workflow test should assert `KEEP_TEST_DIR`, `SPACEDOCK_TEST_TMP_ROOT`, and upload-artifact steps are present for both live jobs.
- Helper unit test should assert `TestRunner` creates temp dirs under the configured root.
