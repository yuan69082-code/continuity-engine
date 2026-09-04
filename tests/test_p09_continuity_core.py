from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from continuity_engine.domain.models import EmotionState
from continuity_engine.domain.capability import IntegrationThinkingMode, CapabilityRequiredEnvelope
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.events import EventClassification, EventReference, EventRelationType
from continuity_engine.domain.memory import MemoryStatus
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.p09_core_fixture import P09Fixture, P09_TIME
from continuity_engine.testing.persistence import tree_inventory_hash


class P09CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_normal_engine_entry_passes_composition_to_thinking_and_direct(self):
        f = P09Fixture(self.root)
        request = f.request()
        result = f.submit(request)
        self.assertIsInstance(result, FirstRoundSuccessResult)
        self.assertIsNotNone(f.provider.inputs[0].continuity_context)
        self.assertEqual(f.provider.inputs[0].continuity_context, f.context(request))
        self.assertIsNone(f.core.last_action.plan)
        self.assertEqual(f.adapter.execute_calls, 1)
        self.assertEqual(f.runtime.subject_state().revision, 1)

    def test_elapsed_emotion_is_deterministic_read_only_and_clock_rollback_safe(self):
        emotion = EmotionState(current_state="alert", intensity=0.8,
            updated_at=P09_TIME.isoformat(), confidence=0.9, baseline=0.2)
        before = emotion.to_dict()
        self.assertEqual(emotion.effective_at(P09_TIME + timedelta(days=1))["intensity"], 0.5)
        self.assertEqual(emotion.effective_at(P09_TIME - timedelta(days=1))["intensity"], 0.8)
        self.assertEqual(emotion.to_dict(), before)

    def test_completed_request_restart_preserves_results_and_effect(self):
        f = P09Fixture(self.root)
        request = f.request()
        first = f.submit(request)
        before = tree_inventory_hash(f.runtime.data_root)
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
        self.assertEqual(f.adapter.execute_calls, 0)
        self.assertEqual(f.provider.calls, 0)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_disabled_core_keeps_legacy_path_and_zero_component_reads(self):
        f = P09Fixture(self.root, gates=ContinuityCoreGates(enabled=False))
        before = f.adapter.path.read_bytes()
        result = f.submit()
        self.assertIsInstance(result, FirstRoundSuccessResult)
        self.assertIsNone(f.provider.inputs[0].continuity_context)
        self.assertEqual(f.permission.calls, 0)
        self.assertEqual(f.adapter.execute_calls, 0)
        self.assertEqual(f.adapter.path.read_bytes(), before)

    def test_information_need_is_direct_and_complex_intent_uses_planner(self):
        for mode, planned, steps in (("information", False, 1), ("complex", True, 2)):
            with self.subTest(mode=mode):
                f = P09Fixture(self.root / mode[:1], mode=mode)
                self.assertIsInstance(f.submit(), FirstRoundSuccessResult)
                self.assertEqual(f.core.last_action.plan is not None, planned)
                self.assertEqual(len(f.core.last_action.requests), steps)
                self.assertEqual(f.core.last_action.requests[0].choice.trigger, "INFORMATION_NEED")

    def test_capability_model_input_contains_the_composed_context(self):
        f = P09Fixture(self.root, thinking_mode=IntegrationThinkingMode.CAPABILITY)
        request = f.request()
        result = f.submit(request)
        self.assertIsInstance(result, CapabilityRequiredEnvelope, result.to_dict())
        summary = result.capability_request.input.perception_summary
        self.assertIn('"authority":"confirmed_state"', summary)
        self.assertIn('"direct_state_write_allowed":false', summary)
        self.assertLessEqual(len(summary), 4096)

    def test_snapshot_covers_c1_persistence_and_branch_replays_without_effect(self):
        f = P09Fixture(self.root)
        request = f.request()
        result = f.submit(request)
        snapshot = f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,
            expected_revision=f.runtime.subject_state().revision)
        branch = f.manager.create_branch(f.runtime.descriptor.sandbox_id, snapshot.snapshot_id)
        before = tree_inventory_hash(f.runtime.data_root)
        runtime = f.manager.open_runtime(f.runtime.descriptor.sandbox_id, branch_id=branch)
        fork = P09Fixture(self.root, runtime=runtime, manager=f.manager)
        self.assertEqual(fork.submit(request).to_dict(), result.to_dict())
        self.assertEqual(fork.adapter.execute_calls, 0)
        self.assertIsInstance(fork.submit(), FirstRoundSuccessResult)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_expired_context_stops_new_thinking_from_checkpoint(self):
        f = P09Fixture(self.root)
        request = f.request()
        def crash(stage, operation):
            if stage == "after_perception_checkpoint_saved":
                raise RuntimeError("injected checkpoint interruption")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        f.runtime.clock.advance(timedelta(minutes=11))
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.provider.calls, 0)
        self.assertEqual(f.adapter.execute_calls, 0)

    def test_turning_action_gate_on_does_not_add_effect_to_completed_disabled_round(self):
        f = P09Fixture(self.root, gates=ContinuityCoreGates(actions=False))
        request = f.request()
        first = f.submit(request)
        f.gates = ContinuityCoreGates()
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
        self.assertEqual(f.adapter.execute_calls, 0)

    def test_completed_c1_cannot_skip_receipt_verification_by_disabling_feature(self):
        f = P09Fixture(self.root)
        request = f.request()
        f.submit(request)
        f.gates = ContinuityCoreGates(enabled=False)
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)

    def test_late_duplicate_out_of_order_events_reach_memory_and_context(self):
        f = P09Fixture(self.root, context_budget=ContextBudget(token_limit=2048))
        f.event("recent", occurred_at=P09_TIME - timedelta(hours=1))
        f.event("late", occurred_at=P09_TIME - timedelta(days=1))
        replay = f.event("late", occurred_at=P09_TIME - timedelta(days=1))
        self.assertTrue(replay.idempotent_replay)
        request = f.request()
        self.assertIsInstance(f.submit(request), FirstRoundSuccessResult)
        timeline = f.core.timeline.rebuild(f.runtime.descriptor.subject_id)
        ids = [e.event.event_id for e in timeline.entries]
        self.assertLess(ids.index("late"), ids.index("recent"))
        memory = f.core.memory.load_memory(f.runtime.descriptor.subject_id, "memory:late")
        self.assertEqual(memory.occurred_at, P09_TIME - timedelta(days=1))
        self.assertEqual(memory.recorded_at, P09_TIME)
        self.assertEqual(memory.root_evidence_ids, ["event:late"])
        self.assertTrue(any("late" in fragment.provenance_roots[0]
                            for fragment in f.context(request).composition.snapshot.fragments))

    def test_revocation_propagates_to_summary_and_old_context(self):
        f = P09Fixture(self.root)
        f.event("old")
        f.runtime.clock.advance(timedelta(seconds=1))
        f.event("other")
        request = f.request()
        f.submit(request)
        old = f.context(request)
        subject = f.runtime.descriptor.subject_id
        summaries = f.core.memory.list_summaries(subject)
        self.assertTrue(summaries)
        f.event("revoke", classification=EventClassification.REVOCATION,
            references=(EventReference(target_event_id="old", target_subject_id=subject,
                                       relation_type=EventRelationType.REVOKES),))
        new_request = f.request()
        f.submit(new_request)
        self.assertEqual(f.core.memory.load_memory(subject, "memory:old").status, MemoryStatus.REVOKED)
        self.assertFalse(f.core.current(old))
        new = f.context(new_request).composition.snapshot
        self.assertFalse(any(x.stable_source_id == "memory:old" for x in new.fragments))

    def test_model_context_remains_usable_after_events_and_consolidation(self):
        f = P09Fixture(self.root, thinking_mode=IntegrationThinkingMode.CAPABILITY)
        f.event("model-event-1")
        f.event("model-event-2")
        self.assertIsInstance(f.submit(), CapabilityRequiredEnvelope)

    def test_event_backlog_is_bounded_visible_and_drained_without_silent_loss(self):
        f = P09Fixture(self.root)
        for i in range(65):
            f.event(f"burst-{i:03d}")
        first = f.request()
        f.submit(first)
        self.assertEqual(f.context(first).pending_event_count, 2)  # 65 + Genesis, budget 64.
        self.assertEqual(len(f.core.memory.list_memories(f.runtime.descriptor.subject_id)), 64)
        self.assertIsNotNone(f.core.memory.load_memory(f.runtime.descriptor.subject_id, "memory:burst-000"))
        second = f.request()
        f.submit(second)
        self.assertEqual(f.context(second).pending_event_count, 0)
        self.assertEqual(len(f.core.memory.list_memories(f.runtime.descriptor.subject_id)), 66)


if __name__ == "__main__":
    unittest.main()
