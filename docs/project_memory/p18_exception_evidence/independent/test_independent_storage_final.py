"""Independent isolated TEST-file probes; never write Engine source or real data."""
from contextvars import copy_context
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage import json_repository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_runtime_repository import JsonRuntimeRepository


def bound_refusal(source, target):
    return PermissionError(13, 'TEST initial native refusal', str(source), 5, str(target))


def exception_graph(error):
    pending, seen, result = [error], set(), []
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        result.append(current)
        pending.extend((current.__cause__, current.__context__))
    return result


class IndependentStorageFinal(unittest.TestCase):
    def subject(self):
        owned = tempfile.TemporaryDirectory(prefix='is18-')
        self.addCleanup(owned.cleanup)
        repo = JsonSubjectStateRepository(Path(owned.name).resolve())
        service = SubjectStateService(repo)
        service.create('probe')
        return repo, service, repo._path_for('probe')

    def runtime(self):
        owned = tempfile.TemporaryDirectory(prefix='ir18-')
        self.addCleanup(owned.cleanup)
        repo = JsonRuntimeRepository(Path(owned.name).resolve(), subject_id='probe', environment='TEST')
        repo.initialize()
        return repo

    def subject_failure(self, refuse_cleanup):
        repo, service, target = self.subject()
        before = target.read_bytes()
        native = []
        denial = RuntimeBoundaryError('TEST_CURRENT_AUTHORIZATION_REVOKED')
        cleanup = PermissionError(13, 'TEST cleanup refusal')

        def replace(source, destination):
            error = bound_refusal(source, destination)
            native.append(error)
            raise error

        def guard():
            raise denial

        try:
            with json_repository.state_write_retry_guard(guard), patch('os.replace', side_effect=replace):
                if refuse_cleanup:
                    with patch('os.unlink', side_effect=cleanup):
                        service.record_interaction('probe')
                else:
                    service.record_interaction('probe')
        except RuntimeBoundaryError as error:
            caught = error
        else:
            self.fail('Current authorization must reject the commit')
        self.assertIs(caught, denial)
        self.assertEqual(len(native), 1)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(service.get_update_history('probe'), [])
        chain = exception_graph(caught)
        print(json.dumps(dict(case=self.id(), replaceCalls=len(native), targetUnchanged=True,
                              top=str(caught), chain=[str(e) for e in chain],
                              nativePreserved=native[0] in chain, cleanupPreserved=cleanup in chain)))
        if refuse_cleanup:
            self.assertIn(cleanup, chain)
        self.assertIn(native[0], chain, 'Guard failure plus cleanup must retain the initial native refusal')

    def runtime_failure(self, refuse_cleanup):
        repo = self.runtime()
        before = repo.path.read_bytes()
        native = []
        cleanup = PermissionError(13, 'TEST cleanup refusal')
        with repo.transaction() as document:
            def replace(source, destination):
                document['generation'] += 1
                error = bound_refusal(source, destination)
                native.append(error)
                raise error

            try:
                with patch('os.replace', side_effect=replace):
                    if refuse_cleanup:
                        with patch('os.unlink', side_effect=cleanup):
                            repo.save(document)
                    else:
                        repo.save(document)
            except RuntimeBoundaryError as error:
                caught = error
            else:
                self.fail('Changed prepared document must reject the commit')
        self.assertEqual(str(caught), 'RUNTIME_REVISION_CONFLICT')
        self.assertEqual(len(native), 1)
        self.assertEqual(repo.path.read_bytes(), before)
        chain = exception_graph(caught)
        print(json.dumps(dict(case=self.id(), replaceCalls=len(native), targetUnchanged=True,
                              top=str(caught), chain=[str(e) for e in chain],
                              nativePreserved=native[0] in chain, cleanupPreserved=cleanup in chain)))
        if refuse_cleanup:
            self.assertIn(cleanup, chain)
        self.assertIn(native[0], chain, 'Revision failure plus cleanup must retain the initial native refusal')

    def test_subject_guard_failure_without_cleanup_keeps_native_context(self):
        self.subject_failure(False)

    def test_subject_guard_failure_with_cleanup_keeps_native_context(self):
        self.subject_failure(True)

    def test_runtime_revision_failure_without_cleanup_keeps_native_context(self):
        self.runtime_failure(False)

    def test_runtime_revision_failure_with_cleanup_keeps_native_context(self):
        self.runtime_failure(True)

    def test_same_path_other_instance_cannot_inherit_transaction(self):
        repo = self.runtime()
        other = JsonRuntimeRepository(repo.root, subject_id='probe', environment='TEST')
        before = repo.path.read_bytes()
        with repo.transaction() as document, patch('os.replace', side_effect=bound_refusal) as replace:
            # side_effect must raise, not merely return an exception object.
            def refuse(source, target):
                raise bound_refusal(source, target)
            replace.side_effect = refuse
            with self.assertRaises(PermissionError):
                other.save(document)
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(repo.path.read_bytes(), before)

    def test_nested_copied_context_keeps_only_live_repository_eligibility(self):
        outer, inner = self.runtime(), self.runtime()
        before = {r.path: r.path.read_bytes() for r in (outer, inner)}
        calls = []
        def refuse(source, target):
            calls.append(str(target))
            raise bound_refusal(source, target)
        with outer.transaction():
            with inner.transaction():
                copied = copy_context()
            with patch('os.replace', side_effect=refuse):
                with self.assertRaises(PermissionError):
                    copied.run(inner.save, inner.load())
                self.assertEqual(len(calls), 1)
                calls.clear()
                from continuity_engine.storage.json_runtime_repository import RuntimeCheckpointBusy
                with self.assertRaises(RuntimeCheckpointBusy):
                    copied.run(outer.save, outer.load())
                self.assertGreater(len(calls), 1)
        for repo in (outer, inner):
            calls.clear()
            with patch('os.replace', side_effect=refuse), self.assertRaises(PermissionError):
                copied.run(repo.save, repo.load())
            self.assertEqual(len(calls), 1)
            self.assertEqual(repo.path.read_bytes(), before[repo.path])


if __name__ == '__main__':
    unittest.main(verbosity=2)
