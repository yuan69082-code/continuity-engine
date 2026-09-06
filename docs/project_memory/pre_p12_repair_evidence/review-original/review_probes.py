"""Read-only engine review: isolated temporary data, no engine source changes.

Run with PYTHONPATH pointing to the reviewed engine src. These tests assert
desired invariants; failures document independently reproduced defects.
"""
import concurrent.futures
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import continuity_engine
sys.path.insert(0, str(Path(continuity_engine.__file__).resolve().parents[2]))

from continuity_engine.domain.events import Event, EventClassification, StateSection, StateMutation, ChangeOperation
from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.services.learning_service import LearningService
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.domain.scheduling import NotificationStatus
from continuity_engine.domain.resources import ResourceRequest, ResourceSessionType, RuntimeMode
from continuity_engine.domain.memory import MemoryRecord, MemoryKind, MemoryEvidenceType, MemoryTimeRange, MemoryVisibility
from continuity_engine.services.memory_consolidation_service import MemoryConsolidationService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.testing.p11_scheduler_fixture import P11SchedulerFixture

NOW = datetime(2026, 9, 5, 8, tzinfo=timezone.utc)


def evidence(case, **observed):
    print(json.dumps({"case": case, **observed}, ensure_ascii=False), flush=True)


class EngineReviewProbes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="engine-review-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_scheduler_receipt_conflict_does_not_starve_other_task(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        f.service.submit(f.create_task(task_id="bad-receipt"))
        f.service.submit(f.create_task(task_id="healthy"))
        f.adapter.conflict_on_dispatch = True
        first = f.service.tick(f.subject_id, "TEST")
        f.adapter.conflict_on_dispatch = False
        f.adapter.conflict_on_query = True
        results = []
        for _ in range(5):
            f.clock.advance(timedelta(seconds=60))
            result = f.service.tick(f.subject_id, "TEST")
            results.append(result.reason_code)
        healthy = f.service.get("healthy", subject_id=f.subject_id, environment="TEST")
        evidence("scheduler_conflict_starvation", first=first.reason_code,
                 subsequent=results, healthy_state=healthy.state.value,
                 dispatches=f.adapter.dispatch_count, queries=f.adapter.query_count)
        self.assertEqual(healthy.state.value, "COMPLETED")

    def test_scheduler_unknown_does_not_starve_at_normal_poll_interval(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        f.service.submit(f.create_task(task_id="unknown"))
        f.service.submit(f.create_task(task_id="healthy"))
        f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        f.service.tick(f.subject_id, "TEST")
        for _ in range(5):
            f.clock.advance(timedelta(seconds=30))
            f.service.tick(f.subject_id, "TEST")
        healthy = f.service.get("healthy", subject_id=f.subject_id, environment="TEST")
        evidence("scheduler_unknown_starvation", healthy_state=healthy.state.value,
                 dispatches=f.adapter.dispatch_count, queries=f.adapter.query_count)
        self.assertEqual(healthy.state.value, "COMPLETED")

    def _permissions(self):
        service = PermissionService(JsonPermissionRepository(self.root), clock=lambda: NOW)
        service.create_permission("subject", permission_id="permission",
            permission_type="information_access", name="Memory", description="Read memory",
            scope=["memory_manager"], capabilities=["memory:request"],
            source="user_authorization", reason="Original bounded grant")
        return service

    def test_restriction_does_not_expand_capabilities(self):
        service = self._permissions()
        try:
            service.restrict_permission("subject", "permission", scope=["*"],
                capabilities=["memory:request", "action:execute"],
                reason="Restrict original grant", source="user_authorization")
        except Exception as exc:
            evidence("permission_expand", rejected=type(exc).__name__)
            return
        allowed = service.check_capability("subject", "action:execute", scope="*")
        evidence("permission_expand", added_capability_allowed=allowed,
                 status=service.get_permission("subject", "permission").status.value)
        self.assertFalse(allowed)

    def test_restriction_does_not_reactivate_revoked_permission(self):
        service = self._permissions()
        service.revoke_permission("subject", "permission", reason="Withdraw grant",
                                  source="user_authorization")
        self.assertFalse(service.check_capability("subject", "memory:request"))
        try:
            service.restrict_permission("subject", "permission",
                reason="Restrict withdrawn grant", source="user_authorization")
        except Exception as exc:
            evidence("permission_revocation", rejected=type(exc).__name__)
            return
        allowed = service.check_capability("subject", "memory:request")
        evidence("permission_revocation", capability_reactivated=allowed,
                 status=service.get_permission("subject", "permission").status.value)
        self.assertFalse(allowed)

    def test_repeated_resource_request_remains_reconcilable(self):
        service = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
        service.create_resource_state("subject", token_budget=1000, compute_budget=100,
                                      current_mode=RuntimeMode.CONTINUOUS)
        request = ResourceRequest.create(request_id="same-request", subject_id="subject",
            session_id="same-session", session_type=ResourceSessionType.OTHER,
            estimated_tokens=10, estimated_compute=1, model_name="test",
            reason="One operation", requested_at=NOW)
        service.request_resources(request)
        service.request_resources(request)
        error = None
        try:
            service.record_actual_usage("subject", "same-session", 8)
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        evidence("resource_duplicate", token_used=service.get_resource_state("subject").token_used,
                 usage_records=len(service.get_usage_history("subject")), reconciliation_error=error)
        self.assertIsNone(error)
        self.assertEqual(len(service.get_usage_history("subject")), 1)

    def test_concurrent_events_are_not_silently_lost(self):
        repo = JsonSubjectStateRepository(self.root)
        service = SubjectStateService(repo, clock=lambda: NOW)
        service.create("subject")
        barrier = threading.Barrier(2, timeout=10)
        original_write = repo._write_payload
        def interleaved_write(path, data):
            barrier.wait()
            return original_write(path, data)
        events = [Event.create(event_id="event-" + str(i), occurred_at=NOW,
            source="test", event_type="observation", content="Objective observation " + str(i),
            classification=EventClassification.FACT, impact_scope=[StateSection.CONTINUITY], mutations=[],
            reason="Concurrent event") for i in range(2)]
        with patch.object(repo, "_write_payload", side_effect=interleaved_write):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(service.apply_event, "subject", e) for e in events]
                outcomes = []
                for future in futures:
                    try:
                        result = future.result(timeout=15)
                        outcomes.append(result.update.event.event_id)
                    except Exception as exc:
                        outcomes.append(type(exc).__name__)
        stored = [u.event.event_id for u in service.get_update_history("subject")]
        evidence("concurrent_event_loss", successful_returns=outcomes, persisted_events=stored)
        successful = [x for x in outcomes if x.startswith("event-")]
        self.assertTrue(set(successful).issubset(stored))

    def _memory(self, memory_id, roots):
        occurred = NOW - timedelta(hours=1)
        return MemoryRecord(memory_id=memory_id, subject_id="subject", environment="TEST",
            kind=MemoryKind.RELATIONAL, evidence_type=MemoryEvidenceType.EXPERIENTIAL,
            content="The relationship was reconciled.", root_evidence_ids=roots,
            source_event_ids=[x.removeprefix("event:") for x in roots],
            occurred_at=occurred, observed_at=occurred, recorded_at=occurred,
            consolidated_at=NOW, confidence=0.8, importance=0.8, activation=0,
            scope="relationship:current", time_range=MemoryTimeRange(occurred, occurred),
            tags=["synthetic"], visibility=MemoryVisibility.ENGINE_PRIVATE,
            relation_relevance=0.9, emotional_weight=0.4,
            consolidation_id="consolidation:" + memory_id)

    def test_memory_partial_overlap_preserves_new_evidence(self):
        repo = JsonMemoryRepository(self.root, environment="TEST")
        service = MemoryConsolidationService(repo, clock=lambda: NOW)
        service.consolidate(self._memory("first", ["event:one"]))
        incoming = self._memory("next", ["event:one", "event:two"])
        try:
            result = service.consolidate(incoming)
        except Exception as exc:
            loaded = repo.load_memory("subject", "first")
            evidence("memory_partial_overlap", input_roots=incoming.root_evidence_ids,
                     persisted_roots=loaded.root_evidence_ids,
                     error=type(exc).__name__ + ": " + str(exc))
            self.fail("Valid overlapping evidence cannot be consolidated: " + str(exc))
        loaded = repo.load_memory("subject", "first")
        replay = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: NOW
        ).consolidate(incoming)
        evidence("memory_partial_overlap", input_roots=incoming.root_evidence_ids,
                 persisted_roots=loaded.root_evidence_ids,
                 added=result.unique_evidence_added, replay_roots=replay.memory.root_evidence_ids)
        self.assertEqual(set(loaded.root_evidence_ids), {"event:one", "event:two"})
        self.assertEqual(result.unique_evidence_added, 1)

    def test_control_memory_disjoint_roots_merge(self):
        repo = JsonMemoryRepository(self.root, environment="TEST")
        service = MemoryConsolidationService(repo, clock=lambda: NOW)
        service.consolidate(self._memory("first", ["event:one"]))
        result = service.consolidate(self._memory("next", ["event:two"]))
        self.assertEqual(set(result.memory.root_evidence_ids), {"event:one", "event:two"})
        self.assertEqual(result.unique_evidence_added, 1)

    def test_control_sequential_events_preserved(self):
        service = SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW)
        service.create("subject")
        for i in range(2):
            service.apply_event("subject", Event.create(event_id="sequential-" + str(i),
                occurred_at=NOW, source="test", event_type="observation", content="Observation",
                classification=EventClassification.FACT, impact_scope=[StateSection.CONTINUITY],
                mutations=[], reason="Sequential control"))
        self.assertEqual(len(service.get_update_history("subject")), 2)

    def test_control_real_restriction_removes_capability(self):
        service = self._permissions()
        service.restrict_permission("subject", "permission", capabilities=[],
            reason="Remove capability", source="user_authorization")
        self.assertFalse(service.check_capability("subject", "memory:request"))

    def test_control_resource_once_reconciles(self):
        service = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
        service.create_resource_state("subject", token_budget=1000, compute_budget=100,
                                      current_mode=RuntimeMode.CONTINUOUS)
        request = ResourceRequest.create(request_id="request", subject_id="subject",
            session_id="session", session_type=ResourceSessionType.OTHER,
            estimated_tokens=10, estimated_compute=1, model_name="test",
            reason="One operation", requested_at=NOW)
        service.request_resources(request)
        service.record_actual_usage("subject", "session", 8)
        self.assertEqual(service.get_resource_state("subject").token_used, 8)

    def test_control_scheduler_unknown_allows_immediate_next_tick(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        f.service.submit(f.create_task(task_id="unknown"))
        f.service.submit(f.create_task(task_id="healthy"))
        f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        f.service.tick(f.subject_id, "TEST")
        result = f.service.tick(f.subject_id, "TEST")
        self.assertEqual(result.task.task_id, "healthy")
        self.assertEqual(result.status.value, "COMPLETED")

    def test_scheduler_foreign_cycle_does_not_wake_another_subject(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW, enable_awakening=True)
        other = "other-subject"
        SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW).create(other)
        f.resource_manager.create_resource_state(other, token_budget=10000, compute_budget=1000)
        cycle = f.awakening_service.create_manual_cycle(other)
        task = f.create_task(task_id="foreign-cycle")
        task.cycle_id = cycle.cycle_id
        f.service.submit(task)
        result = f.service.tick(f.subject_id, "TEST")
        foreign = f.awakening_repository.list_sessions(other)
        evidence("scheduler_foreign_cycle", task_subject=f.subject_id,
                 actual_cycle_subject=other, result=result.status.value,
                 task_subject_wakes=f.wake_count, foreign_subject_wakes=len(foreign),
                 foreign_tokens=f.resource_manager.get_resource_state(other).token_used)
        self.assertEqual(len(foreign), 0)

    def test_learning_rechecks_rejected_support_before_solidifying(self):
        learning = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        states = SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW)
        state = states.create("subject")
        candidates = []
        for i in range(3):
            candidates.append(learning.create_candidate("subject", source_event_id=f"event-{i}",
                source_memory_id=None, related_state_revision=0, observation="Concise replies help",
                hypothesis="Prefer concise replies", proposed_change=StateMutation(
                    field_path="identity.expression_preferences", operation=ChangeOperation.APPEND,
                    value="prefers concise responses", reason="Independent supporting observation"),
                confidence=0.6, original_experience={"event": i}, reason="Candidate evidence",
                source="explicit_evaluation").learning_event)
        learning.validate_learning("subject", candidates[0].learning_id,
            [candidates[1].learning_id, candidates[2].learning_id],
            reason="Three sources", source="review")
        learning.reject_learning("subject", candidates[1].learning_id,
            reason="Supporting experience was wrong", source="review")
        rejected = False
        result = None
        try:
            result = learning.solidify_learning("subject", candidates[0].learning_id, state,
                trait_name="Concise", trait_description="Concise preference",
                reason="Attempt with withdrawn evidence", source="review",
                confirmed=True, expected_revision=state.revision)
        except LearningValidationError:
            rejected = True
        evidence("learning_rejected_support", rejected=rejected,
                 source_status=learning.get_learning_event("subject", candidates[1].learning_id).validation_status.value,
                 traits=len(learning.list_traits("subject")),
                 claimed_evidence=result.trait.evidence_count if result else None,
                 evolution_event_produced=result.event is not None if result else False)
        self.assertTrue(rejected)
        self.assertEqual(len(learning.list_traits("subject")), 0)

    def test_model_zero_budget_still_blocks_execute_after_crash(self):
        from tests.test_p02_model_capability import P02ModelCapabilityFixture, p02_request
        from tests.test_p02_model_recovery import FailOnceAt
        from continuity_engine.domain.model_provider import ProviderModelProfile
        from continuity_engine.testing.fake_model_provider import FakeProviderScenario
        fixture = P02ModelCapabilityFixture()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        profile = ProviderModelProfile("review-budget", 1, "fake-provider", "fake-model", True, 20, 20, 1)
        scenario = FakeProviderScenario.success("Within budget", input_tokens=10, output_tokens=10)
        app, provider = fixture.app(profile=profile, default=scenario)
        app.models.submit(p02_request(1))
        self.assertEqual(len(provider.facts()), 1)
        fault = FailOnceAt("after_provider_dispatch_reserved")
        app.models._fault_injector = fault
        with self.assertRaises(RuntimeError):
            app.models.submit(p02_request(2))
        self.assertTrue(fault.triggered)
        restored, restored_provider = fixture.app(profile=profile, default=scenario)
        error = None
        with patch.object(restored_provider, "execute", wraps=restored_provider.execute) as executed:
            try:
                restored.models.recover("p02-request-002")
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
            calls = executed.call_count
            limits = [c.args[0].maximum_tokens for c in executed.call_args_list]
        evidence("model_zero_budget_recovery", provider_execute_calls=calls,
                 limits=limits, provider_facts=len(restored_provider.facts()), error=error)
        self.assertEqual(calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
