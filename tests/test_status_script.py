# ABOUTME: Tests for the Python status script's parsing and dispatch logic.
# ABOUTME: Covers frontmatter parsing, stage ordering, --next eligibility rules, and output format.

import os
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, '..', 'templates', 'status')


def build_status_script(tmpdir):
    """Substitute template variables and return path to a runnable status script."""
    script_path = os.path.join(tmpdir, 'status')
    with open(TEMPLATE_PATH, 'r') as f:
        content = f.read()
    content = content.replace('{spacedock_version}', '0.0.0-test')
    content = content.replace('{entity_label}', 'task')
    content = content.replace('{stage1}, {stage2}, ..., {last_stage}', 'backlog, ideation, implementation, validation, done')
    with open(script_path, 'w') as f:
        f.write(content)
    os.chmod(script_path, 0o755)
    return script_path


def run_status(pipeline_dir, *args, script_path=None):
    """Run the status script against a pipeline directory."""
    result = subprocess.run(
        ['python3', script_path] + list(args),
        capture_output=True, text=True,
        env={**os.environ, 'PIPELINE_DIR': pipeline_dir}
    )
    return result


def make_pipeline(tmpdir, readme_content, entities=None, archived=None):
    """Create a pipeline directory with README and entity files."""
    with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
        f.write(readme_content)
    for name, content in (entities or {}).items():
        with open(os.path.join(tmpdir, name), 'w') as f:
            f.write(content)
    if archived:
        archive_dir = os.path.join(tmpdir, '_archive')
        os.makedirs(archive_dir, exist_ok=True)
        for name, content in archived.items():
            with open(os.path.join(archive_dir, name), 'w') as f:
                f.write(content)


README_WITH_STAGES = textwrap.dedent("""\
    ---
    entity-type: task
    entity-label: task
    stages:
      defaults:
        worktree: false
        concurrency: 2
      states:
        - name: backlog
          initial: true
        - name: ideation
          gate: true
        - name: implementation
          worktree: true
        - name: validation
          worktree: true
          fresh: true
          gate: true
        - name: done
          terminal: true
    ---

    # Test Pipeline
    """)

README_NO_STAGES = textwrap.dedent("""\
    ---
    entity-type: task
    entity-label: task
    ---

    # Test Pipeline
    """)


def entity(id, title, status, score='', source='', worktree=''):
    """Generate entity frontmatter."""
    return textwrap.dedent(f"""\
        ---
        id: {id}
        title: {title}
        status: {status}
        source: {source}
        started:
        completed:
        verdict:
        score: {score}
        worktree: {worktree}
        ---

        Description.
        """)


class TestDefaultStatus(unittest.TestCase):
    """Test the default status table output."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)

    def test_basic_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'feature-a.md': entity('001', 'Feature A', 'backlog', '0.80', 'user'),
                'feature-b.md': entity('002', 'Feature B', 'ideation', '0.90', 'CL'),
            })
            result = run_status(tmpdir, script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')
            self.assertEqual(len(lines), 4)  # header + separator + 2 data rows
            # Check header
            self.assertIn('ID', lines[0])
            self.assertIn('SLUG', lines[0])
            self.assertIn('STATUS', lines[0])
            self.assertIn('TITLE', lines[0])
            self.assertIn('SCORE', lines[0])
            self.assertIn('SOURCE', lines[0])

    def test_sort_order_stage_then_score(self):
        """Entities sorted by stage order ascending, then score descending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'low-score.md': entity('001', 'Low Score', 'backlog', '0.30'),
                'high-score.md': entity('002', 'High Score', 'backlog', '0.90'),
                'ideation-task.md': entity('003', 'Ideation Task', 'ideation', '0.50'),
            })
            result = run_status(tmpdir, script_path=self.script_path)
            lines = result.stdout.strip().split('\n')[2:]  # skip header+separator
            # backlog (order 1) should come before ideation (order 2)
            # within backlog, high score first
            self.assertIn('high-score', lines[0])
            self.assertIn('low-score', lines[1])
            self.assertIn('ideation-task', lines[2])

    def test_empty_score_sorts_last(self):
        """Entities with empty scores sort after scored ones in same stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'scored.md': entity('001', 'Scored', 'backlog', '0.50'),
                'unscored.md': entity('002', 'Unscored', 'backlog', ''),
            })
            result = run_status(tmpdir, script_path=self.script_path)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertIn('scored', lines[0])
            self.assertIn('unscored', lines[1])

    def test_excludes_archive_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES,
                entities={'active.md': entity('001', 'Active', 'backlog', '0.50')},
                archived={'old.md': entity('002', 'Old', 'done', '0.80')},
            )
            result = run_status(tmpdir, script_path=self.script_path)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('active', lines[0])

    def test_archived_flag_includes_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES,
                entities={'active.md': entity('001', 'Active', 'backlog', '0.50')},
                archived={'old.md': entity('002', 'Old', 'done', '0.80')},
            )
            result = run_status(tmpdir, '--archived', script_path=self.script_path)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 2)

    def test_empty_fields_show_blank(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'blank.md': entity('001', 'Blank Fields', 'backlog'),
            })
            result = run_status(tmpdir, script_path=self.script_path)
            # Should not contain '-' or '0' for empty fields
            self.assertEqual(result.returncode, 0)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)


class TestNextOption(unittest.TestCase):
    """Test --next dispatch eligibility detection."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)

    def test_basic_dispatchable(self):
        """Entity in backlog (non-terminal, no gate, no worktree) is dispatchable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'ready.md': entity('001', 'Ready Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')
            self.assertIn('ID', lines[0])
            self.assertIn('SLUG', lines[0])
            self.assertIn('CURRENT', lines[0])
            self.assertIn('NEXT', lines[0])
            self.assertIn('WORKTREE', lines[0])
            data_lines = lines[2:]  # skip header+separator
            self.assertEqual(len(data_lines), 1)
            self.assertIn('ready', data_lines[0])
            self.assertIn('backlog', data_lines[0])
            self.assertIn('ideation', data_lines[0])

    def test_terminal_excluded(self):
        """Entity in terminal stage (done) is not dispatchable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'finished.md': entity('001', 'Finished', 'done', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 0)

    def test_gate_blocked_excluded(self):
        """Entity in a gated stage (ideation has gate: true) is not dispatchable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'gated.md': entity('001', 'Gated Task', 'ideation', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 0)

    def test_active_worktree_excluded(self):
        """Entity with non-empty worktree field is not dispatchable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'working.md': entity('001', 'Working', 'implementation', '0.80', worktree='.worktrees/ensign-working'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 0)

    def test_concurrency_limit(self):
        """Entity not dispatchable when next stage has active ensigns at capacity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                # Two actively-worked entities in ideation (concurrency default is 2)
                'in-ideation-1.md': entity('001', 'Ideation 1', 'ideation', '0.90', worktree='.worktrees/ensign-in-ideation-1'),
                'in-ideation-2.md': entity('002', 'Ideation 2', 'ideation', '0.85', worktree='.worktrees/ensign-in-ideation-2'),
                # This backlog entity wants to move to ideation but it's full
                'waiting.md': entity('003', 'Waiting', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 0)

    def test_concurrency_parked_not_counted(self):
        """Parked entities (no worktree) in a stage don't consume concurrency slots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                # Two entities in ideation but NOT actively worked (no worktree)
                'in-ideation-1.md': entity('001', 'Ideation 1', 'ideation', '0.90'),
                'in-ideation-2.md': entity('002', 'Ideation 2', 'ideation', '0.85'),
                # This backlog entity should be dispatchable — parked entities don't block
                'waiting.md': entity('003', 'Waiting', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 1)
            self.assertIn('waiting', data_lines[0])

    def test_concurrency_available(self):
        """Entity dispatchable when next stage has room below concurrency limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                # One actively-worked entity in ideation (concurrency=2, room for one more)
                'in-ideation.md': entity('001', 'Ideation 1', 'ideation', '0.90', worktree='.worktrees/ensign-in-ideation'),
                'waiting.md': entity('002', 'Waiting', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 1)
            self.assertIn('waiting', data_lines[0])

    def test_next_sorted_by_score_desc(self):
        """--next output sorted by score descending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a README with concurrency 2 and one active slot taken
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'low.md': entity('001', 'Low Priority', 'backlog', '0.30'),
                'high.md': entity('002', 'High Priority', 'backlog', '0.90'),
                'mid.md': entity('003', 'Mid Priority', 'backlog', '0.60'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            # No active ensigns in ideation, so concurrency allows 2 dispatches
            self.assertEqual(len(data_lines), 2)
            self.assertIn('high', data_lines[0])
            self.assertIn('mid', data_lines[1])

    def test_next_worktree_column(self):
        """WORKTREE column reflects the next stage's worktree property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                # backlog -> ideation (worktree: false by default)
                'to-ideation.md': entity('001', 'To Ideation', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertIn('no', data_lines[0])

    def test_next_worktree_yes(self):
        """WORKTREE column shows 'yes' when next stage has worktree: true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            readme = textwrap.dedent("""\
                ---
                entity-type: task
                stages:
                  defaults:
                    worktree: false
                    concurrency: 2
                  states:
                    - name: backlog
                      initial: true
                    - name: ideation
                    - name: implementation
                      worktree: true
                    - name: done
                      terminal: true
                ---

                # Test
                """)
            make_pipeline(tmpdir, readme, {
                'task.md': entity('001', 'Task', 'ideation', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 1)
            self.assertIn('yes', data_lines[0])
            self.assertIn('implementation', data_lines[0])

    def test_no_stages_block_error(self):
        """--next prints error and exits non-zero if README lacks stages block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_NO_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stages', result.stderr.lower())

    def test_unknown_status_skipped(self):
        """Entity with unknown status is skipped in --next."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'unknown.md': entity('001', 'Unknown', 'mystery', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 0)

    def test_empty_pipeline(self):
        """--next with no entities outputs header only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES)
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            self.assertEqual(result.returncode, 0)
            lines = result.stdout.strip().split('\n')
            self.assertEqual(len(lines), 2)  # header + separator

    def test_id_column_present(self):
        """--next output includes ID column."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('042', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertIn('042', data_lines[0])


class TestFrontmatterParsing(unittest.TestCase):
    """Test edge cases in YAML frontmatter parsing."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)

    def test_multiword_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'test.md': entity('001', 'A Multi Word Title', 'backlog', '0.50'),
            })
            result = run_status(tmpdir, script_path=self.script_path)
            self.assertIn('A Multi Word Title', result.stdout)

    def test_empty_worktree_not_blocked(self):
        """Entity with empty worktree: field is NOT considered actively worked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80', worktree=''),
            })
            result = run_status(tmpdir, '--next', script_path=self.script_path)
            data_lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(data_lines), 1)


if __name__ == '__main__':
    unittest.main()
