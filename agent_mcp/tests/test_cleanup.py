import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import orchestration
from task import Task


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.task = Task('e' * 32, 123)
        self.directory = self.root / 'executions' / self.task.task_id
        self.directory.mkdir(parents=True)
        self.record = self.directory / 'task.json'
        self.metadata = {
            'id': self.task.task_id, 'pid': self.task.pid, 'state': 'completed',
            'sandbox': f'agent-{self.task.task_id}', 'delivery_directory': '/home/agent/delivery',
        }
        orchestration.save_record(self.record, self.metadata)
        (self.directory / 'checkout').mkdir()
        (self.directory / 'checkout' / 'source.py').write_text('pass')
        (self.directory / 'delivery').mkdir()
        (self.directory / 'delivery' / 'worker.patch').write_text('patch')
        (self.directory / 'agent.log').write_text('finished')
        self.addCleanup(patch.stopall)
        patch.object(orchestration, 'REPOSITORY', self.root).start()
        patch.object(orchestration, 'pid_running', return_value=False).start()
        self.sandbox = patch.object(orchestration, 'sbx', return_value='').start()

    def test_cleanup_preserves_artifacts_and_is_repeatable(self):
        result = orchestration.cleanup(self.task)
        self.assertTrue(result.sandbox_removed)
        self.assertFalse(result.artifacts_deleted)
        self.assertFalse((self.directory / 'checkout').exists())
        self.assertTrue((self.directory / 'delivery' / 'worker.patch').is_file())
        self.assertTrue((self.directory / 'agent.log').is_file())
        self.assertEqual(orchestration.cleanup(self.task), result)
        self.sandbox.assert_called_once_with('rm', '--force', self.metadata['sandbox'])
        self.assertTrue(orchestration.executions()[0].cleaned)

    def test_explicit_full_deletion(self):
        result = orchestration.cleanup(self.task, delete_artifacts=True)
        self.assertTrue(result.artifacts_deleted)
        self.assertIsNone(result.delivery_directory)
        self.assertFalse(self.directory.exists())
        self.assertEqual(orchestration.executions(), [])

    def test_active_and_collecting_executions_are_refused(self):
        for state in ('preparing', 'collecting'):
            self.metadata['state'] = state
            orchestration.save_record(self.record, self.metadata)
            with self.assertRaisesRegex(ValueError, 'active'):
                orchestration.cleanup(self.task)
        self.metadata['state'] = 'launched'
        orchestration.save_record(self.record, self.metadata)
        with patch.object(orchestration, 'pid_running', return_value=True):
            with self.assertRaisesRegex(ValueError, 'active'):
                orchestration.cleanup(self.task)
        self.sandbox.assert_not_called()
        self.assertTrue((self.directory / 'checkout').is_dir())

    def test_delivery_failure_prevents_removal(self):
        with patch.object(orchestration, 'collect_delivery', side_effect=RuntimeError('copy failed')):
            with self.assertRaisesRegex(RuntimeError, 'copy failed'):
                orchestration.cleanup(self.task)
        self.sandbox.assert_not_called()
        self.assertTrue((self.directory / 'checkout').is_dir())
        self.assertIn('copy failed', json.loads(self.record.read_text())['cleanup']['error'])

    def test_retry_resumes_after_sandbox_removal(self):
        with patch.object(orchestration.shutil, 'rmtree', side_effect=OSError('busy')):
            with self.assertRaisesRegex(OSError, 'busy'):
                orchestration.cleanup(self.task)
        self.assertTrue(json.loads(self.record.read_text())['cleanup']['sandbox_removed'])
        orchestration.cleanup(self.task)
        self.sandbox.assert_called_once()
        self.assertFalse((self.directory / 'checkout').exists())

    def test_failed_setup_without_pid_and_corrupt_record_listing(self):
        self.metadata.pop('pid')
        self.metadata.pop('delivery_directory')
        self.metadata['state'] = 'failed'
        orchestration.save_record(self.record, self.metadata)
        self.assertIsNone(orchestration.executions()[0].pid)
        orchestration.cleanup(self.task.task_id)
        self.record.write_text('broken JSON')
        summary = orchestration.executions()[0]
        self.assertEqual(summary.state, 'unknown')
        self.assertIsNotNone(summary.error)

    def test_invalid_handle_cannot_remove_resources(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            orchestration.cleanup(Task(self.task.task_id, 456))
        with self.assertRaisesRegex(ValueError, 'Invalid task ID'):
            orchestration.cleanup('../escape')
        self.sandbox.assert_not_called()
