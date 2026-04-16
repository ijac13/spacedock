#!/usr/bin/env -S uv run --with pytest python
# /// script
# requires-python = ">=3.10"
# ///
# ABOUTME: Unit tests for status script's parse_mod_metadata helper (standing-teammate mod parsing).
# ABOUTME: Covers flat-key frontmatter, ## Agent Prompt extraction, and trailing-heading fail-loud.

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_SCRIPT = REPO_ROOT / "skills" / "commission" / "bin" / "status"


def _load_status_module():
    loader = importlib.machinery.SourceFileLoader("_status_lib_test", str(STATUS_SCRIPT))
    spec = importlib.util.spec_from_file_location(
        "_status_lib_test", str(STATUS_SCRIPT), loader=loader
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


status = _load_status_module()
parse_mod_metadata = status.parse_mod_metadata


def write_mod(path: Path, body: str) -> Path:
    path.write_text(body)
    return path


class TestStandingFlag:
    """AC-1: parse_mod_metadata recognizes standing: true flag."""

    def test_standing_flag_true(self, tmp_path):
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: true
---

## Agent Prompt

hello
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["standing"] is True
        assert meta["name"] == "foo"
        assert meta["frontmatter"]["standing"] == "true"

    def test_standing_flag_false(self, tmp_path):
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: false
---

## Agent Prompt

hello
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["standing"] is False

    def test_standing_flag_absent(self, tmp_path):
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
---

## Agent Prompt

hello
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["standing"] is False


class TestAgentPromptExtract:
    """AC-2: parser extracts ## Agent Prompt body verbatim (last-section convention)."""

    def test_extracts_prompt_body_verbatim(self, tmp_path):
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: true
---

## Hook: startup

some hook text

## Agent Prompt

Line 1 of prompt.
Line 2 of prompt.

- bullet
- another bullet
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["agent_prompt"] is not None
        # Body begins with blank line (the line AFTER the heading), then the
        # prompt lines.
        assert "Line 1 of prompt." in meta["agent_prompt"]
        assert "Line 2 of prompt." in meta["agent_prompt"]
        assert "- bullet" in meta["agent_prompt"]
        assert "some hook text" not in meta["agent_prompt"]

    def test_prompt_absent_returns_none(self, tmp_path):
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: true
---

## Hook: startup

only a hook, no prompt
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["agent_prompt"] is None


class TestTrailingHeadingFailLoud:
    """AC-7 (trailing content fail-loud) and (nested-## accepted)."""

    def test_errors_on_trailing_section_after_agent_prompt(self, tmp_path):
        """AC-7: A ## heading STRICTLY AFTER ## Agent Prompt is a convention violation.

        The regex matches only the literal `## Agent Prompt` heading line;
        everything after it including nested `##` inside fences is preserved
        verbatim. Bare `## ` headings at the left margin after the prompt
        heading are a convention violation and must fail loudly so the
        content doesn't silently leak into the prompt body.
        """
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: true
---

## Agent Prompt

the real prompt.

## Notes

this trailing section violates the convention.
""",
        )
        with pytest.raises(ValueError) as excinfo:
            parse_mod_metadata(str(mod))
        assert "## Notes" in str(excinfo.value)

    def test_accepts_nested_hashes_in_prompt_body(self, tmp_path):
        """AC-7: nested `##` inside code fences or emphasis is preserved unchanged.

        The regex matches only the literal `## Agent Prompt` heading line;
        everything after it including nested `##` inside fences is preserved
        verbatim. The parser walks the body toggling a fence flag on
        triple-backtick lines so `## ` that appears inside a fenced block
        is never treated as a convention-violating heading.
        """
        mod = write_mod(
            tmp_path / "mod.md",
            """---
name: foo
standing: true
---

## Agent Prompt

Reply format for text-passthrough:

```
## Heading inside fence
more fenced content
```

Some prose with ## inline.
""",
        )
        meta = parse_mod_metadata(str(mod))
        assert meta["agent_prompt"] is not None
        assert "## Heading inside fence" in meta["agent_prompt"]
        assert "## inline" in meta["agent_prompt"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
