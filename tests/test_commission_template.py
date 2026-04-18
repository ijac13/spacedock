# ABOUTME: Static checks for the commission skill template (SKILL.md).
# ABOUTME: Asserts Schema section has no YAML fence and required sections exist.

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = REPO_ROOT / "skills" / "commission" / "SKILL.md"


def read_skill() -> str:
    return SKILL_PATH.read_text()


def extract_schema_section(text: str) -> str:
    """Return the text between '## Schema' and '### Field Reference' headings."""
    match = re.search(
        r"^## Schema\n(.*?)^### Field Reference",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Could not find ## Schema ... ### Field Reference in SKILL.md"
    return match.group(1)


def test_schema_section_has_no_yaml_fence():
    schema = extract_schema_section(read_skill())
    assert "```yaml" not in schema, (
        "## Schema section must not contain a ```yaml fence — "
        "the Field Reference table is the canonical field list"
    )


def test_schema_section_has_no_code_fence():
    schema = extract_schema_section(read_skill())
    assert "```" not in schema, (
        "## Schema section must not contain any code fence"
    )


def test_field_reference_heading_exists():
    text = read_skill()
    assert "### Field Reference" in text


def test_entity_label_template_section_has_yaml_fence():
    text = read_skill()
    match = re.search(
        r"^## \{Entity_label\} Template\n(.*?)^## ",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Could not find ## {Entity_label} Template section in SKILL.md"
    assert "```yaml" in match.group(1), (
        "## {Entity_label} Template section must contain a ```yaml fence"
    )


def test_entity_label_template_has_acceptance_criteria_block():
    text = read_skill()
    match = re.search(
        r"^## \{Entity_label\} Template\n(.*?)^## Commit Discipline",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Could not find ## {Entity_label} Template section in SKILL.md"
    body = match.group(1)
    assert "## Acceptance criteria" in body, (
        "## {Entity_label} Template must include an '## Acceptance criteria' "
        "heading so generated workflows inherit the AC convention"
    )
    assert "Each AC names a property" in body, (
        "## {Entity_label} Template must include the 'Each AC names a property' "
        "guidance line from the AC convention"
    )
    assert "Verified by:" in body, (
        "## {Entity_label} Template must include a 'Verified by:' exemplar line"
    )
