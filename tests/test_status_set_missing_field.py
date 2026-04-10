# ABOUTME: Tests for --set inserting fields missing from YAML frontmatter.
# ABOUTME: Covers adding new fields, updating existing fields, and mixed scenarios.

import os
import tempfile
import textwrap
import unittest

from test_status_script import (
    build_status_script,
    make_pipeline,
    run_status,
    README_WITH_STAGES,
)


def minimal_entity(id, title, status):
    """Generate entity frontmatter with only id, title, status — no pr, worktree, etc."""
    return textwrap.dedent(f"""\
        ---
        id: {id}
        title: {title}
        status: {status}
        ---

        Description.
        """)


class TestSetMissingField(unittest.TestCase):
    """Test --set when target field is missing from frontmatter."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)

    def _read_frontmatter(self, filepath):
        """Read frontmatter from a file, returning dict of fields."""
        fields = {}
        in_fm = False
        with open(filepath, 'r') as f:
            for line in f:
                line = line.rstrip('\n')
                if line == '---':
                    if in_fm:
                        break
                    in_fm = True
                    continue
                if in_fm and ':' in line:
                    key, _, val = line.partition(':')
                    fields[key.strip()] = val.strip()
        return fields

    def _read_body(self, filepath):
        """Read file content after frontmatter."""
        lines = []
        in_fm = False
        past_fm = False
        with open(filepath, 'r') as f:
            for line in f:
                if past_fm:
                    lines.append(line)
                    continue
                if line.rstrip('\n') == '---':
                    if in_fm:
                        past_fm = True
                    else:
                        in_fm = True
        return ''.join(lines)

    def test_set_missing_field_inserts_it(self):
        """Setting a field not present in frontmatter should insert it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': minimal_entity('001', 'Task A', 'backlog'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'pr=#42',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertIn('pr', fields,
                          'Missing field "pr" should have been inserted into frontmatter')
            self.assertEqual(fields['pr'], '#42')

    def test_set_existing_field_still_works(self):
        """Regression: setting a field that already exists should update it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': minimal_entity('001', 'Task A', 'backlog'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'status=ideation',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['status'], 'ideation')

    def test_set_mixed_existing_and_missing_fields(self):
        """Setting multiple fields where some exist and some don't — all should be written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': minimal_entity('001', 'Task A', 'backlog'),
            })
            result = run_status(tmpdir, '--set', 'task-a',
                                'status=implementation', 'pr=#42',
                                'worktree=.worktrees/foo',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['status'], 'implementation',
                             'Existing field should be updated')
            self.assertEqual(fields['pr'], '#42',
                             'Missing field "pr" should be inserted')
            self.assertEqual(fields['worktree'], '.worktrees/foo',
                             'Missing field "worktree" should be inserted')

    def test_set_missing_field_preserves_body(self):
        """Inserting a missing field should not corrupt the body after frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': minimal_entity('001', 'Task A', 'backlog'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'pr=#42',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            body = self._read_body(os.path.join(tmpdir, 'task-a.md'))
            self.assertIn('Description.', body,
                          'Body content after frontmatter should be preserved')

    def test_set_missing_field_preserves_existing_fields(self):
        """Inserting a missing field should not alter existing fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': minimal_entity('001', 'Task A', 'backlog'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'pr=#42',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['id'], '001')
            self.assertEqual(fields['title'], 'Task A')
            self.assertEqual(fields['status'], 'backlog')


if __name__ == '__main__':
    unittest.main()
