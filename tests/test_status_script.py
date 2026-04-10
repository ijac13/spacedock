# ABOUTME: Tests for the Python status script's parsing and dispatch logic.
# ABOUTME: Covers frontmatter parsing, stage ordering, --next eligibility rules, and output format.

import os
import subprocess
import tempfile
import textwrap
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, '..', 'skills', 'commission', 'bin', 'status')


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


def run_status(pipeline_dir, *args, script_path=None, extra_env=None):
    """Run the status script against a pipeline directory."""
    env = {**os.environ, 'PIPELINE_DIR': pipeline_dir}
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ['python3', script_path] + list(args),
        capture_output=True, text=True,
        env=env,
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


def entity(id, title, status, score='', source='', worktree='', pr=''):
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
        pr: {pr}
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

    def test_plugin_mode_uses_explicit_workflow_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'feature-a.md': entity('001', 'Feature A', 'backlog', '0.80', 'user'),
            })
            result = subprocess.run(
                ['python3', self.script_path, '--workflow-dir', tmpdir],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('feature-a', result.stdout)

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


class TestWhereFilter(unittest.TestCase):
    """Test --where filtering."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)

    def test_exact_match(self):
        """--where 'status = backlog' returns only backlog entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'in-backlog.md': entity('001', 'Backlog Task', 'backlog', '0.80'),
                'in-ideation.md': entity('002', 'Ideation Task', 'ideation', '0.90'),
                'also-backlog.md': entity('003', 'Also Backlog', 'backlog', '0.70'),
            })
            result = run_status(tmpdir, '--where', 'status = backlog', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertIn('backlog', line)
            # ideation entity must not appear
            self.assertNotIn('in-ideation', result.stdout)

    def test_not_equal_with_value(self):
        """--where 'status != done' excludes entities with status done."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'active.md': entity('001', 'Active', 'backlog', '0.80'),
                'finished.md': entity('002', 'Finished', 'done', '0.90'),
                'working.md': entity('003', 'Working', 'implementation', '0.70'),
            })
            result = run_status(tmpdir, '--where', 'status != done', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertNotIn('done', line.split()[2] if len(line.split()) > 2 else '')
            self.assertNotIn('finished', result.stdout)

    def test_non_empty_filter(self):
        """--where 'worktree !=' returns entities with non-empty worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'has-wt.md': entity('001', 'Has Worktree', 'implementation', '0.80', worktree='.worktrees/test'),
                'no-wt.md': entity('002', 'No Worktree', 'backlog', '0.90'),
            })
            result = run_status(tmpdir, '--where', 'worktree !=', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('has-wt', lines[0])

    def test_empty_filter(self):
        """--where 'worktree =' returns entities with empty worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'has-wt.md': entity('001', 'Has Worktree', 'implementation', '0.80', worktree='.worktrees/test'),
                'no-wt.md': entity('002', 'No Worktree', 'backlog', '0.90'),
            })
            result = run_status(tmpdir, '--where', 'worktree =', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('no-wt', lines[0])

    def test_non_empty_pr_field(self):
        """--where 'pr !=' returns entities with non-empty pr field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'has-pr.md': entity('001', 'Has PR', 'validation', '0.80', pr='#19'),
                'no-pr.md': entity('002', 'No PR', 'backlog', '0.90'),
            })
            result = run_status(tmpdir, '--where', 'pr !=', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('has-pr', lines[0])

    def test_multiple_where_and_together(self):
        """Multiple --where clauses AND together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'match.md': entity('001', 'Match', 'backlog', '0.80', source='user'),
                'wrong-status.md': entity('002', 'Wrong Status', 'ideation', '0.90', source='user'),
                'wrong-source.md': entity('003', 'Wrong Source', 'backlog', '0.70', source='CL'),
            })
            result = run_status(tmpdir,
                '--where', 'status = backlog',
                '--where', 'source = user',
                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('match', lines[0])

    def test_where_composes_with_next(self):
        """--where composes with --next."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'high.md': entity('001', 'High Priority', 'backlog', '0.90', source='user'),
                'low.md': entity('002', 'Low Priority', 'backlog', '0.50', source='CL'),
            })
            result = run_status(tmpdir,
                '--next', '--where', 'source = user',
                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('high', lines[0])
            self.assertNotIn('low', result.stdout.split('\n', 3)[-1])

    def test_where_composes_with_archived(self):
        """--where composes with --archived."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES,
                entities={'active.md': entity('001', 'Active', 'backlog', '0.80')},
                archived={
                    'old-done.md': entity('002', 'Old Done', 'done', '0.90'),
                    'old-backlog.md': entity('003', 'Old Backlog', 'backlog', '0.70'),
                },
            )
            result = run_status(tmpdir,
                '--archived', '--where', 'status = backlog',
                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertIn('backlog', line)

    def test_no_matching_entities_header_only(self):
        """--where with no matches returns header only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--where', 'status = done', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')
            self.assertEqual(len(lines), 2)  # header + separator only

    def test_where_on_nonexistent_field(self):
        """--where on a field not in frontmatter treats it as empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            # Filter for non-empty 'nonexistent' — should match nothing
            result = run_status(tmpdir, '--where', 'nonexistent !=', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')
            self.assertEqual(len(lines), 2)  # header + separator only

            # Filter for empty 'nonexistent' — should match everything
            result2 = run_status(tmpdir, '--where', 'nonexistent =', script_path=self.script_path)
            self.assertEqual(result2.returncode, 0, result2.stderr)
            lines2 = result2.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines2), 1)


class TestBootOption(unittest.TestCase):
    """Test --boot startup data output."""

    def setUp(self):
        self._script_dir = tempfile.mkdtemp()
        self.script_path = build_status_script(self._script_dir)

    def tearDown(self):
        os.unlink(self.script_path)
        os.rmdir(self._script_dir)


    def _make_fake_git(self, tmpdir, worktree_output=''):
        """Create a fake git script that returns canned worktree list output."""
        fake_bin = os.path.join(tmpdir, '_fake_bin')
        os.makedirs(fake_bin, exist_ok=True)
        git_script = os.path.join(fake_bin, 'git')
        with open(git_script, 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('if [ "$1" = "worktree" ] && [ "$2" = "list" ]; then\n')
            f.write('  cat <<\'GITEOF\'\n')
            f.write(worktree_output)
            f.write('GITEOF\n')
            f.write('  exit 0\n')
            f.write('fi\n')
            f.write('exit 1\n')
        os.chmod(git_script, 0o755)
        return fake_bin

    def _make_fake_gh(self, tmpdir, pr_states=None):
        """Create a fake gh script that returns canned PR states.

        pr_states: dict mapping PR number (str) to state (e.g., {'19': 'MERGED'})
        """
        fake_bin = os.path.join(tmpdir, '_fake_bin')
        os.makedirs(fake_bin, exist_ok=True)
        gh_script = os.path.join(fake_bin, 'gh')
        # Build case branches
        cases = ''
        for pr_num, state in (pr_states or {}).items():
            cases += '  %s) echo "%s"; exit 0;;\n' % (pr_num, state)
        with open(gh_script, 'w') as f:
            f.write('#!/bin/sh\n')
            f.write('# Fake gh for testing PR state checks\n')
            f.write('if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n')
            f.write('  PR_NUM="$3"\n')
            f.write('  case "$PR_NUM" in\n')
            f.write(cases)
            f.write('  *) echo "not found" >&2; exit 1;;\n')
            f.write('  esac\n')
            f.write('fi\n')
            f.write('exit 1\n')
        os.chmod(gh_script, 0o755)
        return fake_bin

    def _path_without_gh(self):
        """Return a PATH string that excludes directories containing a real gh binary."""
        dirs = os.environ.get('PATH', '').split(os.pathsep)
        filtered = [d for d in dirs if not os.path.isfile(os.path.join(d, 'gh'))]
        return os.pathsep.join(filtered)

    # AC1: MODS section with hooks
    def test_mods_with_hooks(self):
        """MODS section lists hooks grouped by lifecycle point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            mods_dir = os.path.join(tmpdir, '_mods')
            os.makedirs(mods_dir)
            with open(os.path.join(mods_dir, 'pr-merge.md'), 'w') as f:
                f.write('---\nname: pr-merge\n---\n\n## Hook: startup\n\nDo stuff.\n\n## Hook: idle\n\nMore stuff.\n')
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            self.assertIn('MODS', lines)
            # Check hook points are listed
            self.assertTrue(any('startup: pr-merge' in line for line in lines), lines)
            self.assertTrue(any('idle: pr-merge' in line for line in lines), lines)

    # AC2: MODS: none when no mods exist
    def test_mods_none(self):
        """MODS shows 'MODS: none' when no mods directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('MODS: none', result.stdout)

    # AC3: NEXT_ID across active + archive
    def test_next_id_across_active_and_archive(self):
        """NEXT_ID is computed from highest ID across active and archived entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES,
                entities={
                    'task-a.md': entity('001', 'Task A', 'backlog'),
                    'task-c.md': entity('003', 'Task C', 'backlog'),
                },
                archived={
                    'task-b.md': entity('"004"', 'Task B', 'done'),
                },
            )
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NEXT_ID: 005', result.stdout)

    # AC4: Quoted values normalize consistently
    def test_quoted_frontmatter_values_are_normalized(self):
        """Quoted YAML frontmatter values are parsed without literal quote characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'quoted.md': entity('"084"', 'Quoted Task', 'backlog', pr='"#28"'),
            })
            result = run_status(tmpdir, '--where', 'id = 084', script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines), 1)
            self.assertIn('084', lines[0])
            self.assertNotIn('"084"', result.stdout)

            result2 = run_status(tmpdir, '--where', 'pr = #28', script_path=self.script_path)
            self.assertEqual(result2.returncode, 0, result2.stderr)
            lines2 = result2.stdout.strip().split('\n')[2:]
            self.assertEqual(len(lines2), 1)
            self.assertIn('quoted', lines2[0])
            self.assertNotIn('"#28"', result2.stdout)

    # AC4: ORPHANS with DIR_EXISTS and BRANCH_EXISTS
    def test_orphans_with_existence_checks(self):
        """ORPHANS section shows entities with worktree field and existence columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wt_path = os.path.join(tmpdir, '.worktrees', 'ensign-task-a')
            os.makedirs(wt_path)
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'implementation', worktree='.worktrees/ensign-task-a'),
                'task-b.md': entity('002', 'Task B', 'implementation', worktree='.worktrees/ensign-task-b'),
            })
            # Create fake git that reports ensign-task-a as a branch
            worktree_output = (
                'worktree /main\n'
                'HEAD abc123\n'
                'branch refs/heads/main\n'
                '\n'
                'worktree %s\n'
                'HEAD def456\n'
                'branch refs/heads/ensign-task-a\n'
                '\n'
            ) % wt_path
            fake_bin = self._make_fake_git(tmpdir, worktree_output)
            # Put fake git first, but exclude real gh
            path = fake_bin + os.pathsep + self._path_without_gh()
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            # Find ORPHANS section
            orphan_idx = lines.index('ORPHANS')
            self.assertGreater(orphan_idx, -1)
            # Header row
            self.assertIn('DIR_EXISTS', lines[orphan_idx + 1])
            self.assertIn('BRANCH_EXISTS', lines[orphan_idx + 1])
            # task-a: dir exists, branch exists
            task_a_line = [l for l in lines if 'task-a' in l and '001' in l][0]
            self.assertIn('yes', task_a_line.split('ensign-task-a')[1][:30])
            # task-b: dir does not exist, branch does not exist
            task_b_line = [l for l in lines if 'task-b' in l and '002' in l][0]
            parts = task_b_line.split()
            # Last two columns should be 'no' 'no'
            self.assertEqual(parts[-2], 'no')
            self.assertEqual(parts[-1], 'no')

    def test_orphans_namespaced_branch_detected(self):
        """Branch with / in name is correctly detected via worktree path lookup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wt_path = os.path.join(tmpdir, '.worktrees', 'ensign-feature-name')
            os.makedirs(wt_path)
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'feature-name.md': entity('001', 'Feature', 'implementation',
                                          worktree='.worktrees/ensign-feature-name'),
            })
            worktree_output = (
                'worktree /main\n'
                'HEAD abc123\n'
                'branch refs/heads/main\n'
                '\n'
                'worktree %s\n'
                'HEAD def456\n'
                'branch refs/heads/ensign/feature-name\n'
                '\n'
            ) % wt_path
            fake_bin = self._make_fake_git(tmpdir, worktree_output)
            path = fake_bin + os.pathsep + self._path_without_gh()
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            feature_line = [l for l in lines if 'feature-name' in l and '001' in l][0]
            parts = feature_line.split()
            # dir exists, branch exists
            self.assertEqual(parts[-2], 'yes', 'DIR_EXISTS should be yes')
            self.assertEqual(parts[-1], 'yes', 'BRANCH_EXISTS should be yes')

    def test_orphans_missing_worktree_detected(self):
        """Entity whose worktree path is not in git worktree list reports BRANCH_EXISTS: no."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create the worktree directory either
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'ghost.md': entity('002', 'Ghost', 'implementation',
                                   worktree='.worktrees/ensign-ghost'),
            })
            worktree_output = (
                'worktree /main\n'
                'HEAD abc123\n'
                'branch refs/heads/main\n'
                '\n'
            )
            fake_bin = self._make_fake_git(tmpdir, worktree_output)
            path = fake_bin + os.pathsep + self._path_without_gh()
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            ghost_line = [l for l in lines if 'ghost' in l and '002' in l][0]
            parts = ghost_line.split()
            self.assertEqual(parts[-2], 'no', 'DIR_EXISTS should be no')
            self.assertEqual(parts[-1], 'no', 'BRANCH_EXISTS should be no')

    def test_orphans_simple_branch_still_works(self):
        """Branch without / in name is still correctly detected (no regression)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wt_path = os.path.join(tmpdir, '.worktrees', 'remove-codex-dispatcher')
            os.makedirs(wt_path)
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'codex.md': entity('003', 'Codex', 'implementation',
                                   worktree='.worktrees/remove-codex-dispatcher'),
            })
            worktree_output = (
                'worktree /main\n'
                'HEAD abc123\n'
                'branch refs/heads/main\n'
                '\n'
                'worktree %s\n'
                'HEAD def456\n'
                'branch refs/heads/remove-codex-dispatcher\n'
                '\n'
            ) % wt_path
            fake_bin = self._make_fake_git(tmpdir, worktree_output)
            path = fake_bin + os.pathsep + self._path_without_gh()
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            codex_line = [l for l in lines if 'codex' in l and '003' in l][0]
            parts = codex_line.split()
            self.assertEqual(parts[-2], 'yes', 'DIR_EXISTS should be yes')
            self.assertEqual(parts[-1], 'yes', 'BRANCH_EXISTS should be yes')

    # AC5: ORPHANS: none
    def test_orphans_none(self):
        """ORPHANS shows 'ORPHANS: none' when no entities have worktree fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('ORPHANS: none', result.stdout)

    # AC6: PR_STATE with PR number and state
    def test_pr_state_with_pr(self):
        """PR_STATE shows PR number and state for PR-pending entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'validation', pr='#19'),
            })
            fake_bin = self._make_fake_gh(tmpdir, {'19': 'MERGED'})
            path = fake_bin + os.pathsep + os.environ.get('PATH', '')
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            self.assertIn('PR_STATE', lines)
            pr_line = [l for l in lines if '#19' in l][0]
            self.assertIn('MERGED', pr_line)
            self.assertIn('001', pr_line)

    # AC7: PR_STATE when gh unavailable
    def test_pr_state_gh_unavailable(self):
        """PR_STATE shows 'gh not available' when gh is not on PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'validation', pr='#19'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PR_STATE: gh not available', result.stdout)

    # AC8: PR_STATE skips terminal entities
    def test_pr_state_skips_terminal(self):
        """PR_STATE skips entities in terminal status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'done-task.md': entity('001', 'Done Task', 'done', pr='#19'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('PR_STATE: none', result.stdout)

    # AC9: DISPATCHABLE section matches --next
    def test_dispatchable_matches_next(self):
        """DISPATCHABLE section contains the same data as --next output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'ready.md': entity('001', 'Ready Task', 'backlog', '0.80'),
            })
            # Get --next output for comparison
            next_result = run_status(tmpdir, '--next', script_path=self.script_path)
            # Get --boot output
            boot_result = run_status(tmpdir, '--boot', script_path=self.script_path,
                                    extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(boot_result.returncode, 0, boot_result.stderr)
            lines = boot_result.stdout.split('\n')
            disp_idx = lines.index('DISPATCHABLE')
            # The next table content should follow
            next_lines = next_result.stdout.strip().split('\n')
            boot_disp_lines = lines[disp_idx + 1:]
            # Compare header and data (strip trailing empty lines)
            boot_disp_lines = [l for l in boot_disp_lines if l]
            for i, expected in enumerate(next_lines):
                self.assertEqual(boot_disp_lines[i].rstrip(), expected.rstrip())

    # AC12: --boot errors without stages block
    def test_boot_requires_stages(self):
        """--boot prints error and exits non-zero if README lacks stages block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_NO_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('stages', result.stderr.lower())

    # AC13: --boot incompatible with --next
    def test_boot_incompatible_with_next(self):
        """--boot combined with --next produces an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            result = run_status(tmpdir, '--boot', '--next', script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('incompatible', result.stderr.lower())

    # AC13: --boot incompatible with --archived
    def test_boot_incompatible_with_archived(self):
        """--boot combined with --archived produces an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            result = run_status(tmpdir, '--boot', '--archived', script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('incompatible', result.stderr.lower())

    # AC13: --boot incompatible with --where
    def test_boot_incompatible_with_where(self):
        """--boot combined with --where produces an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            result = run_status(tmpdir, '--boot', '--where', 'status = backlog',
                               script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('incompatible', result.stderr.lower())

    # AC14: section order
    def test_section_order(self):
        """All sections appear in deterministic order: MODS, NEXT_ID, ORPHANS, PR_STATE, DISPATCHABLE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            output = result.stdout
            # Find positions of section markers
            mods_pos = output.index('MODS')
            next_id_pos = output.index('NEXT_ID')
            orphans_pos = output.index('ORPHANS')
            pr_state_pos = output.index('PR_STATE')
            disp_pos = output.index('DISPATCHABLE')
            self.assertLess(mods_pos, next_id_pos)
            self.assertLess(next_id_pos, orphans_pos)
            self.assertLess(orphans_pos, pr_state_pos)
            self.assertLess(pr_state_pos, disp_pos)

    # Reviewer addition: mod file with no ## Hook: headings
    def test_mods_file_without_hooks(self):
        """Mod file with no ## Hook: headings is silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            mods_dir = os.path.join(tmpdir, '_mods')
            os.makedirs(mods_dir)
            with open(os.path.join(mods_dir, 'empty-mod.md'), 'w') as f:
                f.write('---\nname: empty-mod\n---\n\n# No hooks here\n\nJust text.\n')
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('MODS: none', result.stdout)

    # Reviewer addition: multiple mods registering for the same hook point
    def test_multiple_mods_same_hook(self):
        """Multiple mods registering for the same hook point are listed comma-separated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task.md': entity('001', 'Task', 'backlog'),
            })
            mods_dir = os.path.join(tmpdir, '_mods')
            os.makedirs(mods_dir)
            with open(os.path.join(mods_dir, 'auto-label.md'), 'w') as f:
                f.write('---\nname: auto-label\n---\n\n## Hook: startup\n\nLabel stuff.\n')
            with open(os.path.join(mods_dir, 'pr-merge.md'), 'w') as f:
                f.write('---\nname: pr-merge\n---\n\n## Hook: startup\n\nMerge stuff.\n')
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': self._path_without_gh()})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            startup_line = [l for l in lines if l.startswith('startup:')][0]
            self.assertIn('auto-label', startup_line)
            self.assertIn('pr-merge', startup_line)
            # Alphabetical order
            self.assertIn('startup: auto-label, pr-merge', startup_line)

    # Reviewer addition: PR_STATE ERROR for specific PR failure
    def test_pr_state_per_pr_error(self):
        """PR_STATE shows ERROR when gh pr view fails for a specific PR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'good-pr.md': entity('001', 'Good PR', 'validation', pr='#19'),
                'bad-pr.md': entity('002', 'Bad PR', 'validation', pr='#99'),
            })
            # Only PR 19 returns a state; PR 99 will get an error
            fake_bin = self._make_fake_gh(tmpdir, {'19': 'MERGED'})
            path = fake_bin + os.pathsep + self._path_without_gh()
            result = run_status(tmpdir, '--boot', script_path=self.script_path,
                               extra_env={'PATH': path})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.split('\n')
            good_line = [l for l in lines if '#19' in l][0]
            bad_line = [l for l in lines if '#99' in l][0]
            self.assertIn('MERGED', good_line)
            self.assertIn('ERROR', bad_line)


class TestSetOption(unittest.TestCase):
    """Test --set field update functionality."""

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

    def test_set_single_field(self):
        """AC1: --set {slug} {field}={value} updates the specified field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'status=ideation',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['status'], 'ideation')

    def test_set_multiple_fields(self):
        """AC2: Multiple field=value pairs in one call update all fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--set', 'task-a',
                                'status=ideation', 'worktree=.worktrees/ensign-foo',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['status'], 'ideation')
            self.assertEqual(fields['worktree'], '.worktrees/ensign-foo')

    def test_set_clear_field(self):
        """AC3: field= (empty value) clears the field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'implementation', '0.80',
                                    worktree='.worktrees/ensign-foo'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'worktree=',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['worktree'], '')

    def test_set_timestamp_auto_fill(self):
        """AC4: Bare timestamp field auto-fills with current UTC ISO 8601 time."""
        import re
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            before = datetime.now(timezone.utc)
            result = run_status(tmpdir, '--set', 'task-a', 'started',
                                script_path=self.script_path)
            after = datetime.now(timezone.utc)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            ts = fields['started']
            # Verify ISO 8601 format
            self.assertRegex(ts, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
            # Verify time is within tolerance
            parsed = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            self.assertGreaterEqual(parsed, before.replace(microsecond=0))
            self.assertLessEqual(parsed, after.replace(microsecond=0) + __import__('datetime').timedelta(seconds=1))

    def test_set_bare_non_timestamp_error(self):
        """AC5: Bare non-timestamp field name is rejected with an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'status',
                                script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('status', result.stderr.lower())

    def test_set_nonexistent_entity_error(self):
        """AC6: Non-zero exit and error if entity file does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES)
            result = run_status(tmpdir, '--set', 'nonexistent', 'status=done',
                                script_path=self.script_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('nonexistent', result.stderr.lower())

    def test_set_preserves_unmodified_fields(self):
        """AC7: Fields not specified in the command are preserved unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80', source='user'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'status=done',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['title'], 'Task A')
            self.assertEqual(fields['score'], '0.80')
            self.assertEqual(fields['source'], 'user')
            self.assertEqual(fields['id'], '001')

    def test_set_preserves_body(self):
        """AC8: File body content below frontmatter is preserved unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            body_before = self._read_body(os.path.join(tmpdir, 'task-a.md'))
            result = run_status(tmpdir, '--set', 'task-a', 'status=done',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            body_after = self._read_body(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(body_before, body_after)

    def test_set_prints_updated_fields(self):
        """AC9: Updated fields are printed to stdout after write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            result = run_status(tmpdir, '--set', 'task-a', 'status=done',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('status: done', result.stdout)

    def test_set_incompatible_flags(self):
        """AC10: --set is incompatible with --next, --archived, --boot, --where."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            for flag in ['--next', '--archived', '--boot', '--where']:
                args = ['--set', 'task-a', 'status=done']
                if flag == '--where':
                    args.extend([flag, 'status = backlog'])
                elif flag == '--boot':
                    args.extend([flag, 'task-a'])
                else:
                    args.append(flag)
                result = run_status(tmpdir, *args, script_path=self.script_path)
                self.assertNotEqual(result.returncode, 0,
                    f'Expected non-zero exit for --set with {flag}')
                self.assertTrue(
                    'incompatible' in result.stderr.lower() or 'cannot' in result.stderr.lower(),
                    f'Expected incompatibility error for --set with {flag}, got: {result.stderr}')

    def test_set_timestamp_skip_if_already_set(self):
        """AC11: Bare timestamp auto-fill skips if field already has a value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content = textwrap.dedent("""\
                ---
                id: 001
                title: Task A
                status: implementation
                source:
                started: 2026-01-01T00:00:00Z
                completed:
                verdict:
                score: 0.80
                worktree:
                pr:
                ---

                Description.
                """)
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': content,
            })
            result = run_status(tmpdir, '--set', 'task-a', 'started',
                                script_path=self.script_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['started'], '2026-01-01T00:00:00Z')

    def test_set_uses_workflow_dir(self):
        """AC12: --set uses --workflow-dir to locate entity files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_pipeline(tmpdir, README_WITH_STAGES, {
                'task-a.md': entity('001', 'Task A', 'backlog', '0.80'),
            })
            result = subprocess.run(
                ['python3', self.script_path, '--workflow-dir', tmpdir,
                 '--set', 'task-a', 'status=done'],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = self._read_frontmatter(os.path.join(tmpdir, 'task-a.md'))
            self.assertEqual(fields['status'], 'done')


if __name__ == '__main__':
    unittest.main()
