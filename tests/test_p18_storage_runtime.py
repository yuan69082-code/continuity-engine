"""P18 host/control continuity around bounded storage refusal (isolated TEST)."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
from continuity_engine.storage.json_runtime_repository import RuntimeCheckpointBusy
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from tests.test_p18_runtime_process import runtime_diagnostic


class RuntimeStorageTests(unittest.TestCase):
    def setUp(self):
        # Keep the same bounded path budget as the existing native P18 fixture:
        # stable wake/session names approach Windows' traditional path limit.
        self.temp = tempfile.TemporaryDirectory(prefix="ps18-")
        self.root = Path(self.temp.name)
        self.records = []

    def fixture(self, **options):
        self.f = P18Fixture(self.root, **options)
        return self.f

    def observe(self, stage):
        # Capture before STOP, handle release and root cleanup. The reused
        # diagnostic exposes identities/statuses, never perception bodies.
        self.records.append({"stage": stage, "snapshot": runtime_diagnostic(self.f)})

    def tearDown(self):
        try:
            try:
                if hasattr(self, "f"):
                    self.observe("before-explicit-stop-and-cleanup")
                    self.f.host.control("STOP", command_id="storage-test-cleanup-stop",
                                        expected_revision=None, handle="p18-test-owner")
                    self.assertFalse(self.f.store.host_alive())
            finally:
                print(json.dumps({"test": self.id(), "evidence": self.records,
                                  "spawnedChildren": 0, "forcedCleanup": False}), flush=True)
        finally:
            self.temp.cleanup()

    def ready(self, f):
        f.advance(3600)
        self.assertTrue(f.host.tick())
        self.assertEqual(f.host.query()["activity"], "MAINTENANCE")
        f.advance(60)

    def bounded_tick(self, f):
        started = time.monotonic()
        self.assertTrue(f.host.tick())
        self.assertLess(time.monotonic() - started, 1.5)

    def no_work(self, f):
        self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (0, 0, 0))
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 0)

    def one_fact(self, f):
        self.assertEqual(f.state.revision, 2)
        self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (1, 1, 1))
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used, 320)

    def test_resource_wait_checkpoint_exhaustion_preserves_frozen_host_and_control(self):
        f = self.fixture(mode="contact", tokens=0)
        output = io.StringIO()
        with f.host.running():
            self.ready(f)
            before = f.store.path.read_bytes()
            frozen = f.clock.now()
            with f.store.path.open("rb"):
                try:
                    with contextlib.redirect_stderr(output):
                        self.bounded_tick(f)
                    self.assertEqual(f.store.path.read_bytes(), before)
                    self.assertTrue(f.store.host_alive())
                    self.assertEqual(f.host.query()["activity"], "MAINTENANCE")
                    self.no_work(f)
                finally:
                    self.observe("resource-checkpoint-long-reader-before-release")
            self.assertIn("RUNTIME_CHECKPOINT_BUSY", output.getvalue())
            self.assertEqual(f.clock.now(), frozen)
            self.assertTrue(f.host.tick())
            self.assertEqual(f.host.query()["activity"], "WAITING_RESOURCES")
            self.assertEqual(f.clock.now(), frozen)
            f.control("PAUSE")
            f.grant_test_budget(100000)
            self.assertTrue(f.host.tick())
            self.no_work(f)
            f.control("RESUME")
            self.assertTrue(f.host.tick())
            self.one_fact(f)
            f.control("STOP")
            self.assertFalse(f.host.tick())

    def test_paused_checkpoint_storage_busy_does_not_end_host(self):
        f = self.fixture(mode="contact")
        f.control("PAUSE")
        with f.host.running():
            before = f.store.path.read_bytes()
            with f.store.path.open("rb"):
                try:
                    self.bounded_tick(f)
                    self.assertEqual(f.store.path.read_bytes(), before)
                    self.assertTrue(f.store.host_alive())
                    self.no_work(f)
                finally:
                    self.observe("paused-long-reader-before-release")
            self.assertTrue(f.host.tick())
            self.assertEqual(f.host.query()["reason"], "OWNER_PAUSE")
            self.no_work(f)
            f.control("STOP")
            self.assertFalse(f.host.tick())

    def control_refusal(self, operation):
        f = self.fixture(mode="contact", need_delta=1)
        with f.host.running():
            before = f.store.path.read_bytes()
            revision = f.store.load()["revision"]
            identity = "storage-deferred-" + operation.lower()
            with f.store.path.open("rb"):
                try:
                    started = time.monotonic()
                    with self.assertRaises(RuntimeCheckpointBusy):
                        f.host.control(operation, command_id=identity,
                                       expected_revision=revision, handle="p18-test-owner")
                    self.assertLess(time.monotonic() - started, 1.5)
                    self.assertEqual(f.store.path.read_bytes(), before)
                    self.assertTrue(f.store.host_alive())
                    self.no_work(f)
                finally:
                    self.observe("uncommitted-" + operation.lower() + "-before-release")
            saved = f.host.control(operation, command_id=identity,
                                   expected_revision=revision, handle="p18-test-owner")
            self.assertEqual(saved["revision"], revision + 1)
            committed = f.store.path.read_bytes()
            replay = f.host.control(operation, command_id=identity,
                                    expected_revision=revision, handle="p18-test-owner")
            self.assertEqual(replay, saved)
            self.assertEqual(f.store.path.read_bytes(), committed)

            self.assertEqual(len(saved["commands"]), 1)
            if operation == "STOP":
                self.assertFalse(f.host.tick())
                with self.assertRaisesRegex(RuntimeBoundaryError, "STOP_IS_TERMINAL"):
                    f.control("RESUME")
                self.assertEqual(f.store.path.read_bytes(), committed)
            else:
                self.assertTrue(f.host.tick())
                self.assertEqual(f.host.query()["desired"], "PAUSED")
                self.no_work(f)
                f.control("STOP")

    def test_pause_storage_refusal_has_no_command_and_replays_once_after_release(self):
        self.control_refusal("PAUSE")

    def test_stop_storage_refusal_has_no_command_and_is_terminal_after_commit(self):
        self.control_refusal("STOP")

    def test_completed_effect_with_busy_observation_is_not_dispatched_again(self):
        f = self.fixture(mode="contact")
        held = []
        with f.host.running():
            self.ready(f)
            before = f.store.path.read_bytes()

            def fault(stage):
                if stage == "after_scheduler_completed" and not held:
                    held.append(f.store.path.open("rb"))

            f.fault = fault
            try:
                self.assertTrue(f.host.tick())
                self.assertEqual(len(held), 1)
                self.assertEqual(f.store.path.read_bytes(), before)
                self.one_fact(f)
                self.assertTrue(f.store.host_alive())
            finally:
                self.observe("effect-completed-checkpoint-held-before-release")
                f.fault = lambda stage: None
                for handle in held:
                    handle.close()
            # A fresh observation may consolidate the resulting Event. It must
            # not reissue the already-completed model/action at this same time.
            for _ in range(3):
                self.assertTrue(f.host.tick())
            self.one_fact(f)
            self.assertEqual(list(f.store.path.parent.glob("*.tmp")), [])
            f.control("STOP")

    def test_subject_state_long_reader_allows_maintenance_then_original_fact_recovery(self):
        f = self.fixture(mode="contact")
        target = f.core.subject_states._repository._path_for(f.state.subject_id)
        held = []
        with f.host.running():
            self.ready(f)

            def fault(stage):
                if stage == "after_native_effect" and not held:
                    held.append(target.open("rb"))

            f.fault = fault
            try:
                self.assertTrue(f.host.tick())
                self.assertEqual(len(held), 1)
                self.assertEqual(f.state.revision, 1)
                self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (1, 1, 1))
                sessions = f.work.thinking.get_sessions(f.state.subject_id)
                self.assertEqual(len(sessions), 1)
                original = sessions[0]
                self.assertTrue(original.completed_successfully)
                self.assertIsNone(original.state_update_id)
            finally:
                self.observe("subject-write-exhausted-before-reader-release")
                f.fault = lambda stage: None
                for handle in held:
                    handle.close()

            # Record an ordinary legal non-mutating Event between holds, then
            # keep only SubjectState replacement unavailable while maintenance
            # uses its existing separate Memory authority.
            f.base.event("storage-independent-maintenance", content="Isolated maintenance source.")
            self.assertEqual(f.state.revision, 1)
            with target.open("rb"):
                try:
                    f.advance(5)
                    self.assertTrue(f.host.tick())
                    self.assertTrue(any(m.memory_id == "memory:storage-independent-maintenance"
                                        for m in f.core.memory.list_memories(f.state.subject_id)))
                    self.assertEqual(f.host.query()["activity"], "MAINTENANCE")
                    self.assertTrue(f.store.host_alive())
                    self.assertEqual(f.state.revision, 1)
                    self.assertEqual((f.provider.calls, f.fake.effect_count, f.fake.credits), (1, 1, 1))
                finally:
                    self.observe("maintenance-progressed-during-subject-reader")
            f.advance(60)
            self.assertTrue(f.host.tick())
            self.one_fact(f)
            recovered = f.work.thinking.get_session(f.state.subject_id, original.think_id)
            self.assertIsNotNone(recovered.state_update_id)
            self.assertEqual(recovered.think_id, original.think_id)
            self.assertTrue(f.host.tick())
            self.one_fact(f)
            f.control("STOP")

    def test_checkpoint_committed_but_return_lost_replays_original_control(self):
        f = self.fixture(need_delta=1)
        original_replace = os.replace
        lost = []
        with f.host.running():
            revision = f.store.load()["revision"]

            def replace(source, target):
                result = original_replace(source, target)
                if Path(target) == f.store.path and not lost:
                    lost.append(True)
                    raise OSError(5, "TEST checkpoint committed before return loss")
                return result

            with patch("os.replace", side_effect=replace):
                with self.assertRaises(OSError):
                    f.host.control("PAUSE", command_id="committed-return-loss",
                                   expected_revision=revision, handle="p18-test-owner")
            self.assertEqual(lost, [True])
            committed = f.store.path.read_bytes()
            observed = f.store.load()
            self.assertEqual(observed["desired"], "PAUSED")
            self.assertEqual(observed["revision"], revision + 1)
            replay = f.host.control("PAUSE", command_id="committed-return-loss",
                                    expected_revision=revision, handle="p18-test-owner")
            self.assertEqual(replay, observed)
            self.assertEqual(f.store.path.read_bytes(), committed)
            self.assertEqual(len(observed["commands"]), 1)
            self.no_work(f)
            f.control("STOP")

class RuntimeStorageProcessTests(unittest.TestCase):
    def test_real_host_survives_exhausted_checkpoint_and_resumes_without_chat(self):
        from tests.test_p18_runtime_process import RuntimeProcessTests
        import threading
        harness=RuntimeProcessTests('test_resource_wait_host_lives_and_restores_without_message')
        harness.id=lambda:self.id()
        harness.setUp()
        self.addCleanup(harness.tearDown)
        f=P18Fixture(harness.root,tokens=0)
        f.advance(3600)
        process=harness.start()
        harness.until(lambda:f.store.load()['activity']=='MAINTENANCE',process=process)
        before=f.store.path.read_bytes()
        error_path=harness.processes[0][5]
        with f.store.path.open('rb'):
            try:
                f.advance(60)
                harness.until(lambda:'RUNTIME_CHECKPOINT_BUSY' in error_path.read_text(encoding='utf8'),process=process)
                threading.Event().wait(1.2)
                self.assertIsNone(process.poll())
                self.assertEqual(f.store.path.read_bytes(),before)
                self.assertTrue(harness.cli('query')['host_alive'])
                self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,0)
                self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            finally:harness.capture_diagnostic('long-storage-refusal-before-release')
        harness.until(lambda:f.store.load()['activity']=='WAITING_RESOURCES',process=process)
        harness.cli('pause')
        f.grant_test_budget(100000);f.advance(5)
        threading.Event().wait(1.2)
        self.assertIsNone(process.poll())
        self.assertEqual(f.state.revision,1)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,0)
        harness.cli('resume')
        harness.until(lambda:f.state.revision==2,process=process)
        self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,320)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
        harness.cli('stop');process.wait(timeout=10)
        self.assertEqual(process.returncode,0)
        restarted=harness.start();restarted.wait(timeout=10)
        self.assertEqual(restarted.returncode,0)
        self.assertEqual(f.store.load()['desired'],'STOPPED')
        self.assertEqual(f.state.revision,2)

