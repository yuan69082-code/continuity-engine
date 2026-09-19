"""P18 R2: definite pre-call deferral and genuine unknown have different recovery."""
from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

from continuity_engine.domain.errors import ThinkingValidationError
from continuity_engine.domain.thinking import ThinkSession
from continuity_engine.domain.scheduling import SchedulerTaskState
from continuity_engine.testing.p18_runtime_fixture import P18Fixture


class RuntimeResumeTests(unittest.TestCase):
    def fixture(self, **options):
        temp = tempfile.TemporaryDirectory(prefix='p18-r2-')
        self.addCleanup(temp.cleanup)
        return P18Fixture(Path(temp.name), **options)

    def ready(self, f):
        f.advance(3600); f.host.tick(); f.advance(60)

    def pause_before_call(self, f):
        hits = []
        def hook(stage):
            if stage == 'before_provider' and not hits:
                hits.append(stage); f.control('PAUSE')
        f.host.hook = hook; f.host.tick(); f.host.hook = None
        self.assertEqual(hits, ['before_provider'])

    def resume(self, f):
        f.control('RESUME')
        for _ in range(5):
            f.advance(10); f.host.tick()

    def test_first_call_pause_resumes_same_session_without_extra_reservation(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            sessions = f.work.thinking.get_sessions(f.state.subject_id)
            old_id = sessions[0].think_id
            used = f.resources.get_resource_state(f.state.subject_id).token_used
            self.assertEqual(f.provider.calls, 0)
            for _ in range(3):
                f.advance(10); f.host.tick()
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.fake.effect_count, 0)
            self.resume(f)
            self.assertEqual(f.state.revision, 2)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.work.thinking.get_sessions(f.state.subject_id)[0].think_id, old_id)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, used)
            usage = [u for u in f.resources.get_usage_history(f.state.subject_id) if u.session_id == old_id]
            self.assertEqual(len(usage), 1)
            self.assertEqual(usage[0].actual_tokens, usage[0].estimated_tokens)

    def test_second_cycle_pause_resumes_without_replaying_first(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); f.host.tick()
            self.assertEqual(f.state.revision, 2)
            f.control('PAUSE'); f.advance(3600); f.host.tick()
            f.control('RESUME'); f.host.tick(); f.advance(60)
            self.pause_before_call(f)
            self.assertEqual(f.provider.calls, 1)
            self.resume(f)
            self.assertEqual(f.state.revision, 3)
            self.assertEqual(f.provider.calls, 2)

    def test_reopened_pre_call_deferral_resumes(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            old_id = f.work.thinking.get_sessions(f.state.subject_id)[0].think_id
        reopened = P18Fixture(f.root, initialize=False)
        with reopened.host.running():
            self.resume(reopened)
            self.assertEqual(reopened.state.revision, 2)
            self.assertEqual(reopened.provider.calls, 1)
            self.assertEqual(reopened.work.thinking.get_sessions(reopened.state.subject_id)[0].think_id, old_id)

    def test_entered_provider_failure_is_not_repeated(self):
        f = self.fixture()
        def fail():
            raise RuntimeError('TEST failure after Provider entry')
        with f.host.running():
            self.ready(f); f.provider.hook = fail; f.host.tick(); f.provider.hook = None
            f.control('PAUSE'); self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 1)
            self.assertEqual(f.fake.effect_count, 0)
            self.assertEqual(f.host.query()['activity'], 'WAITING_VERIFICATION')

    def test_stop_does_not_revive_deferred_session(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f); f.control('STOP')
            self.assertFalse(f.host.tick())
        reopened = P18Fixture(f.root, initialize=False)
        with reopened.host.running():
            self.assertFalse(reopened.host.tick())
            self.assertEqual(reopened.provider.calls, 0)
            self.assertEqual(reopened.state.revision, 1)

    def test_long_pause_reassesses_expired_input_with_explicit_predecessor(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            old = f.work.thinking.get_sessions(f.state.subject_id)[0]
            original = old.perception_snapshot.to_dict()
            task = next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id, environment='TEST')
                        if t.task_id.startswith('cognition:'))
            f.advance(900)
            self.assertFalse(f.core.current(old.perception_snapshot.continuity_context))
            self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)
            retained = f.work.thinking.get_session(f.state.subject_id, old.think_id)
            self.assertEqual(retained.perception_snapshot.to_dict(), original)
            self.assertEqual(retained.provider_execution['events'][-1]['phase'], 'ABANDONED')
            self.assertEqual(f.scheduler.get(task.task_id, subject_id=f.state.subject_id, environment='TEST').state,
                             SchedulerTaskState.CANCELLED)
            from continuity_engine.domain.action_planning import digest
            successor = 'cognition:' + digest(['reassess', task.task_id, old.think_id,
                                               retained.provider_execution])[7:]
            self.assertEqual(f.scheduler.get(successor, subject_id=f.state.subject_id, environment='TEST').state,
                             SchedulerTaskState.COMPLETED)
            usage = next(u for u in f.resources.get_usage_history(f.state.subject_id) if u.session_id == old.think_id)
            self.assertEqual(usage.actual_tokens, 0)
            # Both real Wake opportunities cost 64; the abandoned Thinking
            # reservation settles to zero, the new Thinking uses 256.
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 64 + 64 + 256)

    def test_current_context_revoked_does_not_call_or_apply_state(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            f.base.permission.references_allowed = False
            self.resume(f)
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.state.revision, 1)
            self.assertEqual(f.fake.effect_count, 0)

    def test_current_budget_reduction_defers_then_restores_same_reservation(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            f.grant_test_budget(0); self.resume(f)
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 320)
            f.grant_test_budget(100000)
            for _ in range(4): f.advance(10); f.host.tick()
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 320)

    def test_reserved_exact_budget_remains_usable_without_second_charge(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            f.grant_test_budget(320)  # Existing reservation, zero unreserved remainder.
            self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 320)
            self.assertEqual(f.state.revision, 2)

    def test_provider_availability_rechecked_before_prepared_resume(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            f.online = False; self.resume(f)
            self.assertEqual(f.provider.calls, 0)
            f.online = True
            for _ in range(4): f.advance(10); f.host.tick()
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)

    def test_pre_call_history_is_append_only_and_bound(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            session = f.work.thinking.get_sessions(f.state.subject_id)[0]
            record = session.to_dict()
            self.assertTrue(session.provider_not_started)
            self.assertEqual([r['phase'] for r in session.provider_execution['events']], ['PREPARED', 'PREPARED'])
            for mutate in ('drop', 'history', 'binding'):
                changed = copy.deepcopy(record)
                if mutate == 'drop': changed.pop('provider_execution')
                elif mutate == 'history': changed['provider_execution']['events'].pop()
                else: changed['provider_execution']['binding_hash'] = '0' * 64
                path = f.work.thinking._repository._path(session.subject_id, session.think_id)
                before = path.read_bytes()
                with self.assertRaises(ThinkingValidationError):
                    f.work.thinking._repository.save_think_session(ThinkSession.from_dict(changed))
                self.assertEqual(path.read_bytes(), before)
            self.resume(f)
            restored = f.work.thinking.get_session(session.subject_id, session.think_id)
            self.assertEqual(restored.provider_execution['events'][:2], record['provider_execution']['events'])
            self.assertEqual([r['phase'] for r in restored.provider_execution['events']][-2:], ['ENTERED', 'RETURNED'])

    def test_legacy_failed_error_string_is_not_nonexecution_proof(self):
        f = self.fixture()
        def fail(): raise RuntimeError('TEST after call')
        with f.host.running():
            self.ready(f); f.provider.hook = fail; f.host.tick(); f.provider.hook = None
            session = f.work.thinking.get_sessions(f.state.subject_id)[0]
            raw = session.to_dict(); raw.pop('provider_execution')
            raw['error'] = 'RUNTIME_CONTROL_PAUSED_OR_STOPPED'
            # Isolated old-format fixture: deliberately lacks new stage evidence.
            path = f.work.thinking._repository._path(session.subject_id, session.think_id)
            path.write_text(json.dumps(raw), encoding='utf8')
            f.control('PAUSE'); self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 1)
            self.assertEqual(f.host.query()['activity'], 'WAITING_VERIFICATION')
            self.assertEqual(json.loads(path.read_text(encoding='utf8')), raw)

    def test_crash_after_durable_entry_stays_unknown_even_if_call_not_observed(self):
        f = self.fixture()
        class Crash(BaseException): pass
        original = f.work.thinking._repository.save_think_session
        def crash(session):
            original(session)
            if session.provider_execution and session.provider_execution['events'][-1]['phase'] == 'ENTERED':
                raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():
                self.ready(f); f.work.thinking._repository.save_think_session = crash; f.host.tick()
        reopened = P18Fixture(f.root, initialize=False)
        with reopened.host.running():
            for _ in range(4): reopened.advance(10); reopened.host.tick()
            self.assertEqual(reopened.provider.calls, 0)
            self.assertEqual(reopened.state.revision, 1)
            self.assertEqual(reopened.host.query()['activity'], 'WAITING_VERIFICATION')

    def test_real_child_resumes_durable_pre_call_phase(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
        code = '''
import json,sys
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
f=P18Fixture(sys.argv[1],initialize=False)
with f.host.running():
    f.control('RESUME')
    for _ in range(5): f.advance(10); f.host.tick()
    print(json.dumps(dict(revision=f.state.revision,calls=f.provider.calls,used=f.resources.get_resource_state(f.state.subject_id).token_used)))
    f.control('STOP')
'''
        command = [sys.executable, '-c', code, str(f.root)]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf8', timeout=30,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print(json.dumps(dict(test=self.id(), command=command, exitCode=result.returncode,
                              stdout=result.stdout, stderr=result.stderr, childrenReaped=True, forcedCleanup=False)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(revision=2, calls=1, used=320))
        self.assertEqual(f.host.query()['desired'], 'STOPPED')

    def test_repeated_control_deferral_keeps_one_dispatch_and_history(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            for _ in range(4):
                f.control('RESUME'); f.advance(10); self.pause_before_call(f)
            self.assertEqual(f.provider.calls, 0)
            task = next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id, environment='TEST')
                        if t.task_id.startswith('cognition:'))
            self.assertEqual(task.attempt_count, 1)
            self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)

    def test_revoke_during_resume_final_guard_blocks_new_call(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            def revoke(stage):
                if stage == 'before_provider': f.base.permission.references_allowed = False
            f.host.hook = revoke; self.resume(f); f.host.hook = None
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.fake.effect_count, 0)
            self.assertEqual(f.state.revision, 1)
            f.base.permission.references_allowed = True
            for _ in range(5): f.advance(10); f.host.tick()
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)

    def test_cancelled_pre_call_work_is_not_reassessed(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            task = next(t for t in f.scheduler.list_tasks(subject_id=f.state.subject_id, environment='TEST')
                        if t.task_id.startswith('cognition:'))
            f.scheduler.cancel(task.task_id, subject_id=f.state.subject_id, environment='TEST')
            self.resume(f)
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.scheduler.get(task.task_id, subject_id=f.state.subject_id, environment='TEST').state,
                             SchedulerTaskState.CANCELLED)
            self.assertEqual(len(f.work.thinking.get_sessions(f.state.subject_id)), 1)

    def test_crash_with_only_prepared_evidence_resumes_without_replacing_input(self):
        f = self.fixture()
        class Crash(BaseException): pass
        def crash(stage):
            if stage == 'before_provider': raise Crash()
        with self.assertRaises(Crash):
            with f.host.running():
                self.ready(f); f.host.hook = crash; f.host.tick()
        old = f.work.thinking.get_sessions(f.state.subject_id)[0]
        reopened = P18Fixture(f.root, initialize=False)
        with reopened.host.running():
            for _ in range(3): reopened.advance(10); reopened.host.tick()
            self.assertEqual(reopened.state.revision, 2)
            self.assertEqual(reopened.provider.calls, 1)
            new = reopened.work.thinking.get_session(old.subject_id, old.think_id)
            self.assertEqual(new.perception_snapshot, old.perception_snapshot)

    def test_pre_stop_diagnostic_is_read_only_and_has_native_stage(self):
        from test_p18_runtime_process import runtime_diagnostic
        import hashlib
        def inventory(root):
            # Windows denies reading the held byte-range owner lock. Compare
            # all non-lock data files, including newly created paths.
            return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob('*') if p.is_file() and p.suffix != '.lock'}
        f = self.fixture()
        with f.host.running():
            self.ready(f); self.pause_before_call(f)
            before = inventory(f.root)
            snapshot = runtime_diagnostic(f)
            print(json.dumps(dict(test=self.id(), stage='paused-before-stop', snapshot=snapshot)))
            self.assertEqual(inventory(f.root), before)
            self.assertNotIn('native_diagnostic', snapshot)
            self.assertEqual(snapshot['thinking'][0]['phase'], 'PREPARED')
            self.assertTrue(snapshot['thinking'][0]['context_current'])
            self.assertEqual(snapshot['capabilities'], dict(requests=[], attempts=[]))

    def test_test_diagnostics_do_not_print_provider_exception_material(self):
        import contextlib
        import io
        f = self.fixture()
        marker = 'SYNTHETIC_R2_DIAGNOSTIC_SECRET'
        def fail(): raise RuntimeError(marker)
        with f.host.running():
            self.ready(f); f.provider.hook = fail
            output = io.StringIO()
            with contextlib.redirect_stderr(output): f.host.tick()
            self.assertNotIn(marker, output.getvalue())
            self.assertIn('native-exception-before-cleanup', output.getvalue())
            self.assertEqual(f.provider.calls, 1)

    def test_f1_bounded_pause_after_first_evolution_and_clock_before_resume_call(self):
        from test_p18_runtime_process import runtime_diagnostic
        f = self.fixture()
        with f.host.running():
            try:
                self.ready(f)
                hits = []
                def pause(stage):
                    if stage == 'after_native_evolution' and not hits:
                        hits.append(stage); f.control('PAUSE')
                f.fault = pause; f.host.tick(); f.fault = lambda stage: None
                self.assertEqual(f.state.revision, 2)
                f.advance(3600); f.host.tick(); f.control('RESUME')
                for _ in range(3): f.advance(60); f.host.tick()
                self.assertGreater(f.state.revision, 2)
            finally:
                print(json.dumps(dict(test=self.id(), stage='bounded-f1-before-stop', snapshot=runtime_diagnostic(f))))

    def test_control_deferral_inside_budget_port_does_not_create_failed_session(self):
        f = self.fixture()
        with f.host.running():
            self.ready(f)
            hit = []
            def pause(stage):
                if stage == 'before_budget' and not hit:
                    hit.append(stage); f.control('PAUSE')
            f.host.hook = pause; f.host.tick(); f.host.hook = None
            self.assertEqual(hit, ['before_budget'])
            self.assertEqual(f.provider.calls, 0)
            self.assertEqual(f.work.thinking.get_sessions(f.state.subject_id), [])
            self.resume(f)
            self.assertEqual(f.provider.calls, 1)
            self.assertEqual(f.state.revision, 2)

if __name__ == '__main__':
    unittest.main()
