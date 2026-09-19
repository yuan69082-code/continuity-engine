"""P18 storage error evidence remains internal and complete in isolated TEST roots."""
from contextlib import nullcontext
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage import json_repository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_runtime_repository import (
    JsonRuntimeRepository, RuntimeCheckpointWriteDeferred,
)


def bound_refusal(source, target):
    return PermissionError(13, 'TEST native replacement refusal', str(source), 5, str(target))


class StorageExceptionEvidenceTests(unittest.TestCase):
    def subject(self):
        owned = tempfile.TemporaryDirectory(prefix='pe18s-')
        self.addCleanup(owned.cleanup)
        repository = JsonSubjectStateRepository(Path(owned.name).resolve())
        service = SubjectStateService(repository)
        service.create('exception-subject')
        return repository, service, repository._path_for('exception-subject')

    def runtime(self):
        owned = tempfile.TemporaryDirectory(prefix='pe18r-')
        self.addCleanup(owned.cleanup)
        repository = JsonRuntimeRepository(
            Path(owned.name).resolve(), subject_id='exception-subject', environment='TEST')
        repository.initialize()
        return repository

    def assert_evidence(self, error, required):
        active, visited, found = set(), set(), []

        def visit(current):
            if current is None:
                return
            self.assertNotIn(id(current), active, 'Storage failure must not create an exception cycle')
            if id(current) in visited:
                return
            active.add(id(current))
            found.append(current)
            visit(current.__cause__)
            visit(current.__context__)
            for child in getattr(current, 'exceptions', ()):
                visit(child)
            active.remove(id(current))
            visited.add(id(current))

        visit(error)
        for expected in required:
            self.assertTrue(any(value is expected for value in found),
                            f'Original {type(expected).__name__} evidence must remain reachable')
        formatted = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self.assertIn(str(error), formatted)
        self.assertIn('Traceback', formatted)
        return formatted

    def assert_native(self, error, source, target):
        self.assertIsInstance(error, PermissionError)
        self.assertEqual(error.errno, 13)
        self.assertEqual(error.winerror, 5)
        self.assertEqual(error.filename, str(source))
        self.assertEqual(error.filename2, str(target))

    def subject_failure(self, refuse_cleanup, *, explicit_cause=False, cleanup_cause=False):
        repository, service, target = self.subject()
        before = target.read_bytes()
        denial = RuntimeBoundaryError('TEST_CURRENT_AUTHORIZATION_REVOKED')
        authorization_cause = ValueError('TEST authorization source rejected')
        cleanup = PermissionError(13, 'TEST temporary cleanup refusal')
        cleanup_origin = OSError(5, 'TEST earlier cleanup cause')
        if cleanup_cause:
            cleanup.__cause__ = cleanup_origin
        calls, native = [], []

        def replace(source, destination):
            calls.append((source, destination))
            error = bound_refusal(source, destination)
            native.append(error)
            raise error

        def guard():
            if explicit_cause:
                raise denial from authorization_cause
            raise denial

        cleanup_patch = patch('os.unlink', side_effect=cleanup) if refuse_cleanup else nullcontext()
        with json_repository.state_write_retry_guard(guard), patch('os.replace', side_effect=replace), cleanup_patch:
            with self.assertRaises(RuntimeBoundaryError) as caught:
                service.record_interaction('exception-subject')
        self.assertIs(caught.exception, denial)
        self.assertEqual(len(calls), 1)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(service.get_update_history('exception-subject'), [])
        self.assertEqual(repository.load('exception-subject').revision, 0)
        self.assert_native(native[0], *calls[0])
        required = [denial, native[0]]
        if refuse_cleanup:
            required.append(cleanup)
        if explicit_cause:
            required.append(authorization_cause)
        if cleanup_cause:
            required.append(cleanup_origin)
        formatted = self.assert_evidence(caught.exception, required)
        if refuse_cleanup:
            self.assertIn('TEST temporary cleanup refusal', formatted)
        if not explicit_cause:
            self.assertIn('TEST native replacement refusal', formatted)
        if cleanup_cause:
            self.assertIs(cleanup.__cause__, cleanup_origin)
        self.assertEqual(len(list(target.parent.glob('*.tmp'))), int(refuse_cleanup))

    def runtime_failure(self, refuse_cleanup, *, cleanup_cause=False):
        repository = self.runtime()
        before = repository.path.read_bytes()
        previous = repository.load()
        cleanup = PermissionError(13, 'TEST temporary cleanup refusal')
        cleanup_origin = OSError(5, 'TEST earlier checkpoint cleanup cause')
        if cleanup_cause:
            cleanup.__cause__ = cleanup_origin
        calls, native = [], []
        with repository.transaction() as document:
            def replace(source, target):
                calls.append((source, target))
                document['generation'] += 1
                error = bound_refusal(source, target)
                native.append(error)
                raise error

            cleanup_patch = patch('os.unlink', side_effect=cleanup) if refuse_cleanup else nullcontext()
            with patch('os.replace', side_effect=replace), cleanup_patch:
                with self.assertRaises(RuntimeBoundaryError) as caught:
                    repository.save(document)
        self.assertEqual(str(caught.exception), 'RUNTIME_REVISION_CONFLICT')
        self.assertNotIsInstance(caught.exception, RuntimeCheckpointWriteDeferred)
        self.assertEqual(len(calls), 1)
        self.assertEqual(repository.path.read_bytes(), before)
        self.assertEqual(repository.load(), previous)
        self.assert_native(native[0], *calls[0])
        required = [caught.exception, native[0]]
        if refuse_cleanup:
            required.append(cleanup)
        if cleanup_cause:
            required.append(cleanup_origin)
        formatted = self.assert_evidence(caught.exception, required)
        self.assertIn('TEST native replacement refusal', formatted)
        if refuse_cleanup:
            self.assertIn('TEST temporary cleanup refusal', formatted)
        if cleanup_cause:
            self.assertIs(cleanup.__cause__, cleanup_origin)
        self.assertEqual(len(list(repository.path.parent.glob('*.tmp'))), int(refuse_cleanup))

    def test_subject_authorization_refusal_cleanup_success_keeps_native_error(self):
        self.subject_failure(False)

    def test_subject_authorization_refusal_cleanup_failure_keeps_native_error(self):
        self.subject_failure(True)

    def test_checkpoint_revision_refusal_cleanup_success_keeps_native_error(self):
        self.runtime_failure(False)

    def test_checkpoint_revision_refusal_cleanup_failure_keeps_native_error(self):
        self.runtime_failure(True)

    def test_subject_explicit_authorization_cause_and_native_context_both_remain(self):
        self.subject_failure(True, explicit_cause=True)

    def test_subject_cleanup_existing_cause_and_both_primary_branches_remain(self):
        self.subject_failure(True, explicit_cause=True, cleanup_cause=True)

    def test_checkpoint_cleanup_existing_cause_is_not_overwritten(self):
        self.runtime_failure(True, cleanup_cause=True)

    def deferred_failure(self, *, shared_cause):
        repository = self.runtime()
        before = repository.path.read_bytes()
        previous = repository.load()
        cleanup = PermissionError(13, 'TEST deferred cleanup refusal')
        cleanup_origin = OSError(5, 'TEST earlier deferred cleanup cause')
        if not shared_cause:
            cleanup.__cause__ = cleanup_origin
        calls, native = [], []

        def replace(source, target):
            calls.append((source, target))
            error = bound_refusal(source, target)
            native.append(error)
            if shared_cause:
                cleanup.__cause__ = error
            raise error

        with repository.transaction() as document, patch('os.replace', side_effect=replace), patch('os.unlink', side_effect=cleanup):
            with self.assertRaises(RuntimeCheckpointWriteDeferred) as caught:
                repository.save(document)
        self.assertEqual(str(caught.exception), 'RUNTIME_CHECKPOINT_WRITE_DEFERRED')
        self.assertGreater(len(calls), 1)
        self.assertEqual(len(set((str(a), str(b)) for a, b in calls)), 1)
        self.assertEqual(repository.path.read_bytes(), before)
        self.assertEqual(repository.load(), previous)
        self.assert_native(native[-1], *calls[-1])
        required = [caught.exception, native[-1], cleanup]
        if not shared_cause:
            required.append(cleanup_origin)
        formatted = self.assert_evidence(caught.exception, required)
        self.assertIn('TEST deferred cleanup refusal', formatted)
        self.assertIn('TEST native replacement refusal', formatted)
        self.assertIs(cleanup.__cause__, native[-1] if shared_cause else cleanup_origin)
        self.assertEqual(len(list(repository.path.parent.glob('*.tmp'))), 1)

    def test_deferred_native_error_and_cleanup_existing_cause_are_preserved(self):
        self.deferred_failure(shared_cause=False)

    def test_deferred_and_cleanup_shared_native_cause_does_not_create_cycle(self):
        self.deferred_failure(shared_cause=True)

    def test_successful_storage_commits_keep_original_revision_and_cleanup_semantics(self):
        repository, service, target = self.subject()
        guards = []
        with json_repository.state_write_retry_guard(lambda: guards.append(True)):
            service.record_interaction('exception-subject')
        self.assertEqual(guards, [])
        self.assertEqual(repository.load('exception-subject').revision, 1)
        self.assertEqual(len(service.get_update_history('exception-subject')), 1)
        self.assertEqual(list(target.parent.glob('*.tmp')), [])
        checkpoint = self.runtime()
        previous = checkpoint.load()
        with checkpoint.transaction() as document:
            document['reason'] = 'TEST_SUCCESS'
            checkpoint.save(document)
        current = checkpoint.load()
        self.assertEqual(current['revision'], previous['revision'] + 1)
        self.assertEqual(current['reason'], 'TEST_SUCCESS')
        for field in ('generation', 'owner', 'desired', 'commands'):
            self.assertEqual(current[field], previous[field])
        self.assertEqual(list(checkpoint.path.parent.glob('*.tmp')), [])
