from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.models import EmotionState
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification, EventReference, EventRelationType
from continuity_engine.domain.context_composition import ContextBudget, ContextAuthority
from continuity_engine.domain.context_routing import RetrievalBudget
from continuity_engine.domain.errors import IntegrationExecutionError, StateEvolutionError
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.p09_core_fixture import P09Fixture, P09_TIME
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.models import SandboxOperationError


class P09BoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_memory_contradiction_action_and_emotion_subgates_do_no_component_work(self):
        f = P09Fixture(self.root, gates=ContinuityCoreGates(memory=False, contradictions=False,
                                                          actions=False, emotion_decay=False))
        before = {p: p.read_bytes() for p in (f.adapter.path,
            f.core.memory._path(f.runtime.descriptor.subject_id),
            f.core.detector._repository._path(f.runtime.descriptor.subject_id))}
        with patch.object(f.core.memory, "list_memories", side_effect=AssertionError("memory read")), \
             patch.object(f.core.detector, "detect", side_effect=AssertionError("detector read")), \
             patch.object(f.adapter, "query", side_effect=AssertionError("action read")), \
             patch.object(EmotionState, "effective_at", side_effect=AssertionError("emotion read")):
            self.assertIsInstance(f.submit(), FirstRoundSuccessResult)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_disabled_master_gate_never_calls_core_components(self):
        f = P09Fixture(self.root, gates=ContinuityCoreGates(enabled=False))
        with patch.object(f.core, "prepare", side_effect=AssertionError("core work")), \
             patch.object(f.core.router, "route", side_effect=AssertionError("route read")), \
             patch.object(f.core, "after_action", side_effect=AssertionError("action work")):
            first = f.submit()
        self.assertIsInstance(first, FirstRoundSuccessResult)

    def test_independent_router_and_composer_budgets_preserve_missing_notices(self):
        f = P09Fixture(self.root, retrieval_budget=RetrievalBudget(total_candidate_limit=30),
                       context_budget=ContextBudget(core_fragment_limit=6, token_limit=700))
        for i in range(10):
            f.event(f"budget-{i}", content="continuity secret-canary-C1 " + str(i))
        request = f.request()
        f.submit(request)
        c = f.context(request)
        self.assertLessEqual(c.route.trace.budget_used, 30)
        self.assertLessEqual(c.composition.trace.tokens_used, 700)
        self.assertLessEqual(len(c.composition.snapshot.fragments), 6)
        self.assertGreater(c.composition.trace.excluded_count, 0)
        self.assertTrue(c.composition.snapshot.missing_notices)
        self.assertNotIn("secret-canary-C1", json.dumps(f.core.last_trace))
        self.assertFalse(f.core.last_trace["direct_state_write_allowed"])

    def test_insufficient_protected_context_budget_never_starts_thinking(self):
        f = P09Fixture(self.root, context_budget=ContextBudget(token_limit=1))
        with self.assertRaises(IntegrationExecutionError):
            f.submit()
        self.assertEqual((f.provider.calls, f.adapter.execute_calls), (0, 0))

    def test_reference_permission_loss_blocks_thinking_and_new_execution(self):
        f = P09Fixture(self.root)
        request = f.request()
        def crash(stage, operation):
            if stage == "after_perception_checkpoint_saved":
                raise RuntimeError("checkpoint stop")
        f.app.adapter._service._fault_injector = crash
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        f.permission.references_allowed = False
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual((f.provider.calls, f.adapter.execute_calls), (0, 0))

    def test_confirmation_recoverability_reality_and_resource_fail_closed(self):
        from continuity_engine.domain.action import ResourceLimits
        f = P09Fixture(self.root)
        for field in ("confirmation_allowed", "recovery_ready", "reality_ready"):
            with self.subTest(field=field):
                setattr(f.constraints, field, False)
                with self.assertRaises(IntegrationExecutionError):
                    f.submit()
                self.assertEqual(f.adapter.execute_calls, 0)
                setattr(f.constraints, field, True)
        f.core.limits = ResourceLimits(maximum_estimated_cost=0)
        with self.assertRaises(IntegrationExecutionError):
            f.submit()
        self.assertEqual(f.adapter.execute_calls, 0)

    def test_cross_subject_and_environment_contexts_fail_closed(self):
        f = P09Fixture(self.root)
        request = f.request()
        f.submit(request)
        context = f.context(request)
        f.core.subject_id = "different-subject"
        self.assertFalse(f.core.current(context))
        f.core.subject_id = context.composition.snapshot.subject_id
        f.core.environment = "RESEARCH"
        self.assertFalse(f.core.current(context))
        self.assertEqual(f.adapter.execute_calls, 1)

    def test_source_revision_and_hash_changes_invalidate_summary_and_context(self):
        f = P09Fixture(self.root, context_budget=ContextBudget(token_limit=2048))
        f.event("source-1")
        f.event("source-2")
        request = f.request()
        f.submit(request)
        context = f.context(request)
        subject = f.runtime.descriptor.subject_id
        memory = f.core.memory.load_memory(subject, "memory:source-1")
        f.core.memory.save_memory(replace(memory, revision=memory.revision + 1,
            memory_version=memory.memory_version + 1, importance=0.9))
        self.assertFalse(f.core.current(context))
        checked = f.core.composer.compose(context.route, budget=context.composition.snapshot.budget)
        self.assertTrue(any("DRIFT" in n.reason_code or "INVALID" in n.reason_code
                            for n in checked.snapshot.missing_notices))
        self.assertFalse(any(x.stable_source_id == "memory:source-1" for x in checked.snapshot.fragments))

    def test_emotion_persists_only_through_fixture_evolution_and_reads_do_not_write(self):
        f = P09Fixture(self.root)
        values = dict(current_state="alert", intensity=0.8, updated_at=P09_TIME.isoformat(),
                      confidence=0.9, baseline=0.2)
        mutations = tuple(StateMutation("emotion_state." + field, ChangeOperation.SET, value,
            "Explicit P01 state fixture emotion input.") for field, value in values.items())
        f.event("emotion-fixture", classification=EventClassification.STATE_CHANGE, mutations=mutations)
        revision = f.runtime.subject_state().revision
        f.runtime.clock.advance(timedelta(days=1))
        before = tree_inventory_hash(f.runtime.data_root / "subject-state")
        request = f.request()
        f.submit(request)
        self.assertEqual(f.context(request).effective_emotion["intensity"], 0.5)
        self.assertEqual(f.runtime.subject_state().emotion_state.intensity, 0.8)
        self.assertEqual(f.runtime.subject_state().revision, revision)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root / "subject-state"), before)

    def test_invalid_emotion_does_not_partially_commit_evolution(self):
        f = P09Fixture(self.root)
        before = tree_inventory_hash(f.runtime.data_root)
        with self.assertRaisesRegex(StateEvolutionError, "finite ratio"):
            f.event("invalid-emotion", classification=EventClassification.STATE_CHANGE, mutations=(
                StateMutation("emotion_state.intensity", ChangeOperation.SET, 2.0, "invalid fixture"),))
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_snapshot_fails_closed_when_c1_component_is_missing_or_unmapped(self):
        f = P09Fixture(self.root)
        f.submit()
        path = f.core.memory._path(f.runtime.descriptor.subject_id)
        original = path.read_bytes()
        path.unlink()  # Only this test's disposable memory file.
        with self.assertRaises(SandboxOperationError):
            f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,
                                      expected_revision=f.runtime.subject_state().revision)
        path.write_bytes(original)
        (f.runtime.data_root / "unmapped-c1.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SandboxOperationError):
            f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,
                                      expected_revision=f.runtime.subject_state().revision)

    def test_source_revocation_invalidates_memory_even_without_raw_timeline_candidate(self):
        f = P09Fixture(self.root, context_budget=ContextBudget(token_limit=2048))
        # A legitimate memory-only routing configuration must still recheck roots.
        f.core.router._bindings = [b for b in f.core.router._bindings if b.source.source_id != "engine.timeline"]
        f.event("ancestor")
        request = f.request()
        f.submit(request)
        context = f.context(request)
        self.assertTrue(any(x.stable_source_id == "memory:ancestor" for x in context.composition.snapshot.fragments))
        f.event("ancestor-revoked", classification=EventClassification.REVOCATION, references=(
            EventReference(target_event_id="ancestor", target_subject_id=f.runtime.descriptor.subject_id,
                           relation_type=EventRelationType.REVOKES),))
        self.assertFalse(f.core.current(context))


if __name__ == "__main__":
    unittest.main()
