"""P18 explicitly authorized same-commit retries; isolated TEST files only.

These tests add the accepted bounded-attempt policy. They do not replace the
archived observations of the earlier one-attempt policy.
"""
import contextlib
from contextvars import copy_context
import copy
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage import json_repository
from continuity_engine.storage import json_runtime_repository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_runtime_repository import (
    JsonRuntimeRepository, RuntimeCheckpointBusy,
)


def bound_refusal(source, target):
    return PermissionError(13, 'TEST native-shaped refusal', str(source), 5, str(target))


class StorageRetryTests(unittest.TestCase):
    def test_copied_context_after_transaction_exit_cannot_authorize_retry(self):
        from contextvars import copy_context
        repository=self.runtime()
        before=repository.path.read_bytes()
        with repository.transaction() as document:
            copied=copy_context()
        calls=[]
        def replace(source,target):
            calls.append(True)
            raise bound_refusal(source,target)
        with patch('os.replace',side_effect=replace):
            with self.assertRaises(PermissionError):copied.run(repository.save,document)
        self.assertEqual(calls,[True])
        self.assertEqual(repository.path.read_bytes(),before)
        self.no_temporary(repository.path)

    def subject(self):
        owned = tempfile.TemporaryDirectory(prefix='p18-storage-subject-')
        self.addCleanup(owned.cleanup)
        repository = JsonSubjectStateRepository(Path(owned.name).resolve())
        service = SubjectStateService(repository)
        service.create('retry-subject')
        return repository, service, repository._path_for('retry-subject')

    def runtime(self):
        owned = tempfile.TemporaryDirectory(prefix='p18-storage-runtime-')
        self.addCleanup(owned.cleanup)
        repository = JsonRuntimeRepository(Path(owned.name).resolve(),
            subject_id='retry-subject', environment='TEST')
        repository.initialize()
        return repository

    def no_temporary(self, path):
        self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_subject_bound_sustained_refusal_is_bounded_and_preserves_record(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        guards, calls, failures = [], [], []
        def replace(source, destination):
            calls.append((str(source), str(destination)))
            error = bound_refusal(source, destination)
            failures.append(error)
            raise error
        started = time.monotonic()
        with json_repository.state_write_retry_guard(lambda: guards.append(True)), patch('os.replace', side_effect=replace):
            with self.assertRaises(PermissionError) as caught:
                service.record_interaction('retry-subject')
        self.assertGreater(len(calls), 1)
        self.assertGreater(len(guards), 0)
        self.assertEqual(len(set(calls)), 1, 'retry must reuse the same prepared file')
        self.assertIs(caught.exception, failures[-1])
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(len(service.get_update_history('retry-subject')), 0)
        self.no_temporary(target)

    def test_runtime_bound_sustained_refusal_defers_without_claiming_commit(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        original = repository.load()
        calls, failures = [], []
        def replace(source, target):
            calls.append((str(source), str(target)))
            error = bound_refusal(source, target)
            failures.append(error)
            raise error
        started = time.monotonic()
        with repository.transaction() as document:
            document['reason'] = 'TEST_OBSERVATION'
            with patch('os.replace', side_effect=replace), self.assertRaises(RuntimeCheckpointBusy) as caught:
                repository.save(document)
        self.assertEqual(str(caught.exception), 'RUNTIME_CHECKPOINT_WRITE_DEFERRED')
        self.assertIs(caught.exception.__cause__, failures[-1])
        self.assertGreater(len(calls), 1)
        self.assertEqual(len(set(calls)), 1)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(repository.path.read_bytes(), before)
        self.assertEqual(repository.load(), original)
        self.no_temporary(repository.path)

    def test_subject_unbound_fixed_error_keeps_one_attempt_and_zero_guard(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        guards = []
        error = PermissionError(13, 'TEST unbound refusal')
        error.winerror = 5
        with json_repository.state_write_retry_guard(lambda: guards.append(True)), patch('os.replace', side_effect=error) as replace:
            with self.assertRaises(PermissionError) as caught:
                service.record_interaction('retry-subject')
        self.assertIs(caught.exception, error)
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(guards, [])
        self.assertEqual(target.read_bytes(), before)
        self.no_temporary(target)

    def test_runtime_unbound_fixed_error_is_not_a_deferred_commit(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        error = PermissionError(13, 'TEST unbound refusal')
        error.winerror = 5
        with repository.transaction() as document, patch('os.replace', side_effect=error) as replace:
            with self.assertRaises(PermissionError) as caught:
                repository.save(document)
        self.assertIs(caught.exception, error)
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(repository.path.read_bytes(), before)
        self.no_temporary(repository.path)

    def test_subject_no_explicit_authorization_keeps_one_bound_attempt(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        def replace(source, destination):
            raise bound_refusal(source, destination)
        with patch('os.replace', side_effect=replace) as replaced:
            with self.assertRaises(PermissionError):
                service.record_interaction('retry-subject')
        self.assertEqual(replaced.call_count, 1)
        self.assertEqual(target.read_bytes(), before)
        self.no_temporary(target)

    def test_runtime_save_outside_transaction_does_not_inherit_retry(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        guards = []
        def replace(source, target):
            raise bound_refusal(source, target)
        with json_repository.state_write_retry_guard(lambda: guards.append(True)), patch('os.replace', side_effect=replace) as replaced:
            with self.assertRaises(PermissionError):
                repository.save(repository.load())
        self.assertEqual(replaced.call_count, 1)
        self.assertEqual(guards, [])
        self.assertEqual(repository.path.read_bytes(), before)
        self.no_temporary(repository.path)

    def test_subject_released_before_classification_commits_only_once(self):
        repository, service, target = self.subject()
        original = os.replace
        calls, native_failures = [], []
        def replace(source, destination):
            calls.append(True)
            if len(calls) == 1:
                with target.open('rb'):
                    try:
                        original(source, destination)
                    except OSError as error:
                        native_failures.append(error)
                self.assertEqual(len(native_failures), 1)
                raise native_failures[0]
            return original(source, destination)
        with json_repository.state_write_retry_guard(lambda: None), patch('os.replace', side_effect=replace):
            service.record_interaction('retry-subject')
        self.assertEqual(len(calls), 2)
        self.assertEqual(getattr(native_failures[0], 'winerror', None), 5)
        self.assertEqual(repository.load('retry-subject').revision, 1)
        self.assertEqual(len(service.get_update_history('retry-subject')), 1)
        self.no_temporary(target)

    def test_runtime_released_before_classification_keeps_transaction_binding(self):
        repository = self.runtime()
        before = repository.load()
        original = os.replace
        calls, native_failures = [], []
        def replace(source, target):
            calls.append(True)
            if len(calls) == 1:
                with repository.path.open('rb'):
                    try:
                        original(source, target)
                    except OSError as error:
                        native_failures.append(error)
                self.assertEqual(len(native_failures), 1)
                raise native_failures[0]
            return original(source, target)
        with repository.transaction() as document, patch('os.replace', side_effect=replace):
            document['reason'] = 'TEST_OBSERVATION'
            repository.save(document)
        after = repository.load()
        self.assertEqual(len(calls), 2)
        self.assertEqual(after['revision'], before['revision'] + 1)
        for field in ('owner', 'generation', 'desired', 'commands'):
            self.assertEqual(after[field], before[field])
        self.no_temporary(repository.path)

    def test_subject_changed_target_or_temporary_aborts_before_second_replace(self):
        for changed in ('target-content', 'target-identity', 'temporary-content', 'temporary-identity'):
            with self.subTest(changed=changed):
                repository, service, target = self.subject()
                before = target.read_bytes()
                altered = []
                original = os.replace
                def replace(source, destination):
                    path = target if changed.startswith('target') else Path(source)
                    if changed.endswith('content'):
                        path.write_bytes(path.read_bytes() + b'\n')
                    else:
                        replacement = path.with_name(path.name + '.test-alternative')
                        replacement.write_bytes(path.read_bytes())
                        original(replacement, path)
                    altered.append(path.read_bytes())
                    raise bound_refusal(source, destination)
                with json_repository.state_write_retry_guard(lambda: None), patch('os.replace', side_effect=replace) as replaced:
                    with self.assertRaises(StateEvolutionError):
                        service.record_interaction('retry-subject')
                self.assertEqual(replaced.call_count, 1)
                self.assertEqual(target.read_bytes(), altered[0] if changed.startswith('target') else before)
                self.no_temporary(target)

    def test_runtime_changed_prepared_document_aborts_before_second_replace(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        with repository.transaction() as document:
            def replace(source, target):
                document['generation'] += 1
                raise bound_refusal(source, target)
            with patch('os.replace', side_effect=replace) as replaced:
                with self.assertRaisesRegex(RuntimeBoundaryError, 'RUNTIME_REVISION_CONFLICT'):
                    repository.save(document)
        self.assertEqual(replaced.call_count, 1)
        self.assertEqual(repository.path.read_bytes(), before)
        self.no_temporary(repository.path)

    def test_runtime_newer_committed_control_cannot_be_overwritten(self):
        repository = self.runtime()
        stale = copy.deepcopy(repository.load())
        with repository.transaction() as current:
            current['reason'] = 'NEWER_OBSERVATION'
            repository.save(current)
        newer = repository.path.read_bytes()
        with repository.transaction(), patch('os.replace') as replaced:
            with self.assertRaisesRegex(RuntimeBoundaryError, 'RUNTIME_REVISION_CONFLICT'):
                repository.save(stale)
        self.assertEqual(replaced.call_count, 0)
        self.assertEqual(repository.path.read_bytes(), newer)
        self.no_temporary(repository.path)

    def test_current_authorization_failure_is_not_retried_or_swallowed(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        rejection = RuntimeBoundaryError('TEST_CURRENT_AUTHORIZATION_REVOKED')
        def guard():
            raise rejection
        def replace(source, destination):
            raise bound_refusal(source, destination)
        with json_repository.state_write_retry_guard(guard), patch('os.replace', side_effect=replace) as replaced:
            with self.assertRaises(RuntimeBoundaryError) as caught:
                service.record_interaction('retry-subject')
        self.assertIs(caught.exception, rejection)
        self.assertEqual(replaced.call_count, 1)
        self.assertEqual(target.read_bytes(), before)
        self.no_temporary(target)

    def test_native_readonly_target_remains_refused_and_readonly(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        old_mode = target.stat().st_mode
        original = os.replace
        calls = []
        os.chmod(target, stat.S_IREAD)
        try:
            def replace(source, destination):
                calls.append(True)
                return original(source, destination)
            with json_repository.state_write_retry_guard(lambda: None), patch('os.replace', side_effect=replace):
                with self.assertRaises(PermissionError):
                    service.record_interaction('retry-subject')
            self.assertEqual(calls, [True])
            self.assertTrue(target.stat().st_file_attributes & 1)
            self.assertEqual(target.read_bytes(), before)
            self.no_temporary(target)
        finally:
            # Only restore this test's attribute change after the assertion.
            os.chmod(target, old_mode)

    def test_success_followed_by_return_loss_never_replaces_a_second_time(self):
        for kind in ('subject', 'runtime'):
            with self.subTest(kind=kind):
                original = os.replace
                errors = []
                def replace(source, target):
                    original(source, target)
                    error = bound_refusal(source, target)
                    errors.append(error)
                    raise error
                if kind == 'subject':
                    repository, service, path = self.subject()
                    with json_repository.state_write_retry_guard(lambda: None), patch('os.replace', side_effect=replace) as replaced:
                        with self.assertRaises((OSError, StateEvolutionError)):
                            service.record_interaction('retry-subject')
                    self.assertEqual(repository.load('retry-subject').revision, 1)
                    self.assertEqual(len(service.get_update_history('retry-subject')), 1)
                else:
                    repository = self.runtime()
                    path = repository.path
                    before = repository.load()
                    with repository.transaction() as document, patch('os.replace', side_effect=replace) as replaced:
                        with self.assertRaises((OSError, StateEvolutionError, RuntimeBoundaryError)):
                            repository.save(document)
                    self.assertEqual(repository.load()['revision'], before['revision'] + 1)
                self.assertEqual(replaced.call_count, 1)
                self.assertEqual(len(errors), 1)
                self.no_temporary(path)

    def test_budget_is_one_deadline_not_renewed_by_each_native_refusal(self):
        repository, service, target = self.subject()
        before = target.read_bytes()
        clock = [0.0]
        calls = []
        def monotonic():
            clock[0] += 0.04
            return clock[0]
        def replace(source, destination):
            calls.append(True)
            if len(calls) > 10:
                raise AssertionError('same-commit deadline was repeatedly renewed')
            raise bound_refusal(source, destination)
        with json_repository.state_write_retry_guard(lambda: None), patch.object(json_repository.time, 'monotonic', side_effect=monotonic), patch('os.replace', side_effect=replace):
            with self.assertRaises(PermissionError):
                service.record_interaction('retry-subject')
        self.assertGreater(len(calls), 1)
        self.assertLessEqual(len(calls), 4)
        self.assertEqual(target.read_bytes(), before)
        self.no_temporary(target)

    def test_prepared_file_change_before_replace_helper_is_not_adopted(self):
        for kind in ('subject', 'runtime'):
            for changed in ('content', 'identity'):
                with self.subTest(kind=kind, changed=changed):
                    helper = json_repository._replace_payload
                    original = os.replace
                    modified = []
                    def altered(temporary, target, previous, **kwargs):
                        temporary = Path(temporary)
                        if changed == 'content':
                            temporary.write_bytes(temporary.read_bytes() + b'\n')
                        else:
                            replacement = temporary.with_name(temporary.name + '.test-alternative')
                            replacement.write_bytes(temporary.read_bytes())
                            original(replacement, temporary)
                        modified.append(True)
                        return helper(temporary, target, previous, **kwargs)
                    if kind == 'subject':
                        repository, service, target = self.subject()
                        before = target.read_bytes()
                        with json_repository.state_write_retry_guard(lambda: None), patch.object(json_repository, '_replace_payload', side_effect=altered):
                            with self.assertRaises(StateEvolutionError):
                                service.record_interaction('retry-subject')
                    else:
                        repository = self.runtime()
                        target = repository.path
                        before = target.read_bytes()
                        with repository.transaction() as document, patch.object(json_runtime_repository, '_replace_payload', side_effect=altered):
                            with self.assertRaises((StateEvolutionError, RuntimeBoundaryError)):
                                repository.save(document)
                    self.assertEqual(modified, [True])
                    self.assertEqual(target.read_bytes(), before)
                    self.no_temporary(target)

    def test_copied_context_on_another_thread_does_not_convey_transaction_retry(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        calls, errors = [], []
        def replace(source, target):
            calls.append((str(source), str(target)))
            raise bound_refusal(source, target)
        with repository.transaction() as document:
            copied = copy_context()
            proposed = copy.deepcopy(document)
            def save():
                try:
                    copied.run(repository.save, proposed)
                except BaseException as error:
                    errors.append(error)
            with patch('os.replace', side_effect=replace):
                worker = threading.Thread(target=save, name='p18-test-copied-context')
                worker.start()
                worker.join(5)
                self.assertFalse(worker.is_alive(), 'bounded test worker must finish')
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PermissionError)
        self.assertEqual(repository.path.read_bytes(), before)
        self.no_temporary(repository.path)

    def test_runtime_cleanup_error_preserves_original_native_error_chain(self):
        repository = self.runtime()
        before = repository.path.read_bytes()
        refusals = []
        cleanup = PermissionError(13, 'TEST cleanup refusal')
        def replace(source, target):
            error = bound_refusal(source, target)
            refusals.append(error)
            raise error
        with repository.transaction() as document, patch('os.replace', side_effect=replace), patch('os.unlink', side_effect=cleanup):
            with self.assertRaises(RuntimeCheckpointBusy) as caught:
                repository.save(document)
        self.assertGreater(len(refusals), 1)
        pending, chain = [caught.exception], []
        seen = set()
        while pending:
            error = pending.pop()
            if error is None or id(error) in seen:
                continue
            seen.add(id(error))
            chain.append(error)
            pending.extend((error.__cause__, error.__context__))
        self.assertIn(cleanup, chain)
        self.assertIn(refusals[-1], chain, 'cleanup must not erase the native primary failure')
        self.assertEqual(str(caught.exception), 'RUNTIME_CHECKPOINT_WRITE_DEFERRED')
        self.assertEqual(repository.path.read_bytes(), before)
        self.assertEqual(len(list(repository.path.parent.glob('*.tmp'))), 1)
