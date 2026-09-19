"""Extra bounded exception-preservation probes using only isolated TEST files."""
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage import json_repository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_runtime_repository import JsonRuntimeRepository


class IndependentExceptionEdges(unittest.TestCase):
    def root(self):
        owned = tempfile.TemporaryDirectory(prefix='ie18-')
        self.addCleanup(owned.cleanup)
        return Path(owned.name).resolve()

    def evidence(self, primary, required):
        active, seen, found = set(), set(), []
        def visit(error):
            if error is None:
                return
            self.assertNotIn(id(error), active, 'Repair must not introduce a cycle')
            if id(error) in seen:
                return
            active.add(id(error))
            found.append(error)
            visit(error.__cause__)
            visit(error.__context__)
            active.remove(id(error))
            seen.add(id(error))
        visit(primary)
        for error in required:
            self.assertTrue(any(value is error for value in found))
        rendered = ''.join(traceback.format_exception(primary))
        self.assertIn(str(primary), rendered)
        self.assertIn('TEST cleanup refusal', rendered)

    def native_only(self, runtime):
        if runtime:
            repository = JsonRuntimeRepository(self.root(), subject_id='probe', environment='TEST')
            repository.initialize()
            target = repository.path
            document = repository.load()
            action = lambda: repository.save(document)  # no transaction: no retry eligibility
        else:
            repository = JsonSubjectStateRepository(self.root())
            service = SubjectStateService(repository)
            service.create('probe')
            target = repository._path_for('probe')
            action = lambda: service.record_interaction('probe')  # no retry guard
        before = target.read_bytes()
        failures, calls = [], []
        cleanup = PermissionError(13, 'TEST cleanup refusal')
        cleanup_cause = OSError(5, 'TEST cleanup original cause')
        cleanup.__cause__ = cleanup_cause
        def replace(source, destination):
            calls.append((str(source), str(destination)))
            native = PermissionError(13, 'TEST native refusal', str(source), 5, str(destination))
            failures.append(native)
            raise native
        with patch('os.replace', side_effect=replace), patch('os.unlink', side_effect=cleanup):
            with self.assertRaises(PermissionError) as caught:
                action()
        self.assertIs(caught.exception, failures[0])
        self.assertEqual(len(calls), 1)
        self.assertEqual((caught.exception.errno, caught.exception.winerror), (13, 5))
        self.assertEqual((caught.exception.filename, caught.exception.filename2), calls[0])
        self.assertEqual(target.read_bytes(), before)
        self.evidence(caught.exception, [failures[0], cleanup, cleanup_cause])

    def test_unguarded_subject_retains_native_top_and_cleanup_history(self):
        self.native_only(False)

    def test_checkpoint_without_transaction_retains_native_top_and_cleanup_history(self):
        self.native_only(True)

    def test_from_none_keeps_hidden_native_and_cleanup_cause_without_cycle(self):
        repository = JsonSubjectStateRepository(self.root())
        service = SubjectStateService(repository)
        service.create('probe')
        target = repository._path_for('probe')
        before = target.read_bytes()
        native = []
        rejection = RuntimeBoundaryError('TEST rejected from none')
        cleanup = PermissionError(13, 'TEST cleanup refusal')
        cleanup_cause = OSError(5, 'TEST cleanup original cause')
        cleanup.__cause__ = cleanup_cause
        def guard():
            raise rejection from None
        def replace(source, destination):
            error = PermissionError(13, 'TEST native refusal', str(source), 5, str(destination))
            native.append(error)
            raise error
        with json_repository.state_write_retry_guard(guard), patch('os.replace', side_effect=replace), patch('os.unlink', side_effect=cleanup):
            with self.assertRaises(RuntimeBoundaryError) as caught:
                service.record_interaction('probe')
        self.assertIs(caught.exception, rejection)
        self.assertEqual(len(native), 1)
        self.assertEqual(target.read_bytes(), before)
        self.evidence(caught.exception, [native[0], rejection, cleanup, cleanup_cause])
        self.assertEqual(service.get_update_history('probe'), [])

    def test_presave_io_failure_is_not_changed_to_cleanup_error_or_commit(self):
        repository = JsonSubjectStateRepository(self.root())
        service = SubjectStateService(repository)
        service.create('probe')
        target = repository._path_for('probe')
        before = target.read_bytes()
        primary = OSError(5, 'TEST fsync failure')
        cleanup = PermissionError(13, 'TEST cleanup refusal')
        with patch('os.fsync', side_effect=primary), patch('os.replace') as replaced, patch('os.unlink', side_effect=cleanup):
            with self.assertRaises(OSError) as caught:
                service.record_interaction('probe')
        self.assertIs(caught.exception, primary)
        self.assertEqual(replaced.call_count, 0)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(service.get_update_history('probe'), [])
        self.evidence(caught.exception, [primary, cleanup])


if __name__ == '__main__':
    unittest.main(verbosity=2)
