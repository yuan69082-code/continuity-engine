"""Formal regressions for the eight independently reproduced pre-P12 defects."""
import concurrent.futures
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


from continuity_engine.domain.events import Event, EventClassification, StateSection, StateMutation, ChangeOperation
from continuity_engine.domain.errors import (LearningValidationError, PermissionValidationError, ResourceValidationError, StateEvolutionError)
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


class PreP12RegressionTests(unittest.TestCase):
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

    def _files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

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
        except PermissionValidationError as exc:
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
        except PermissionValidationError as exc:
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
        before = self._files()
        with self.assertRaises(ResourceValidationError):
            service.request_resources(request)
        self.assertEqual(self._files(), before)
        error = None
        try:
            service.record_actual_usage("subject", "same-session", 8)
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        evidence("resource_duplicate", token_used=service.get_resource_state("subject").token_used,
                 usage_records=len(service.get_usage_history("subject")), reconciliation_error=error)
        self.assertIsNone(error)
        self.assertEqual(len(service.get_usage_history("subject")), 1)
        self.assertEqual(service.get_resource_state("subject").token_used, 8)

    def _concurrent_events(self, *, same=False, mutating=False):
        repo = JsonSubjectStateRepository(self.root)
        other_repo = JsonSubjectStateRepository(self.root / ".")
        service = SubjectStateService(repo, clock=lambda: NOW)
        other_service = SubjectStateService(other_repo, clock=lambda: NOW)
        service.create("subject")
        first_at_write = threading.Event()
        second_at_write = threading.Event()
        original_first, original_second = repo._write_payload, other_repo._write_payload
        def first_write(path, data):
            first_at_write.set()
            # A write-only lock cannot prevent the second stale read. With a
            # transaction lock, the bounded wait expires and the first commits.
            second_at_write.wait(0.15)
            return original_first(path, data)
        def second_write(path, data):
            result = original_second(path, data)
            second_at_write.set()
            return result
        def event(identifier):
            return Event.create(event_id=identifier, occurred_at=NOW, source="test",
                event_type="state_change" if mutating else "observation",
                content="Synthetic event " + identifier,
                classification=EventClassification.STATE_CHANGE if mutating else EventClassification.FACT,
                impact_scope=[StateSection.CONTINUITY],
                mutations=[StateMutation(field_path="continuity.current_focus",
                    operation=ChangeOperation.SET, value=[identifier], reason="Explicit test evolution")]
                    if mutating else [], reason="Concurrent regression")
        first, second = event("event-one"), event("event-one" if same else "event-two")
        with patch.object(repo, "_write_payload", side_effect=first_write), \
             patch.object(other_repo, "_write_payload", side_effect=second_write):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                one = pool.submit(service.apply_event, "subject", first)
                self.assertTrue(first_at_write.wait(2))
                two = pool.submit(other_service.apply_event, "subject", second)
                results = []
                for future in (one, two):
                    try:
                        results.append(future.result(timeout=3))
                    except StateEvolutionError:
                        # Optimistic revision rejection is a valid concurrent outcome.
                        self.assertTrue(mutating)
        history = service.get_update_history("subject")
        stored = {u.event.event_id for u in history}
        successful = {r.update.event.event_id for r in results}
        self.assertTrue(successful.issubset(stored))
        self.assertTrue({r.update.update_id for r in results}.issubset({u.update_id for u in history}))
        self.assertGreaterEqual(len(results), 1)
        if not mutating:
            self.assertEqual(len(results), 2)
            self.assertEqual(len(history), 1 if same else 2)
            self.assertEqual(service.load("subject").revision, 0)
        else:
            self.assertEqual(service.load("subject").revision, len(history))
        return service, first

    def test_concurrent_events_are_not_silently_lost(self):
        self._concurrent_events()

    def test_concurrent_same_event_is_persisted_once(self):
        service, first = self._concurrent_events(same=True)
        self.assertTrue(service.apply_event("subject", first).idempotent_replay)
        self.assertEqual(len(service.get_update_history("subject")), 1)

    def test_concurrent_mutations_preserve_revision_conflict(self):
        service, _ = self._concurrent_events(mutating=True)
        with self.assertRaises(StateEvolutionError):
            service.apply_event("subject", Event.create(event_id="stale", occurred_at=NOW,
                source="test", event_type="observation", content="Stale request",
                classification=EventClassification.FACT, impact_scope=[StateSection.CONTINUITY],
                mutations=[], reason="Expected revision gate"), expected_revision=0)

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
        self.assertIsNone(error)
        self.assertEqual(len(restored_provider.facts()), 1)


    def test_permission_wildcard_scope_containment_and_zero_write_rejection(self):
        cases = [(["*"], ["memory_manager"], True),
                 (["memory_manager"], ["*"], False),
                 (["memory_manager"], ["memory_manager:project-only"], False),
                 (["memory_manager", "action_gate"], ["memory_manager"], True),
                 ([], ["*"], False),
                 (["memory:*"], ["memory:one"], False)]
        for i, (old, new, allowed) in enumerate(cases):
            with self.subTest(old=old, new=new):
                service = PermissionService(JsonPermissionRepository(self.root / str(i)), clock=lambda: NOW)
                service.create_permission("subject", permission_id="p", permission_type="information_access",
                    name="Bounded", description="Synthetic grant", scope=old, capabilities=["memory:request"],
                    source="user_authorization", reason="Explicit grant")
                before = self._files()
                if allowed:
                    service.restrict_permission("subject", "p", scope=new, reason="Narrow scope", source="user_authorization")
                    self.assertTrue(service.check_capability("subject", "memory:request", scope=new[0]))
                    self.assertFalse(service.check_capability("subject", "memory:request", scope="unrelated"))
                else:
                    with self.assertRaises(PermissionValidationError):
                        service.restrict_permission("subject", "p", scope=new, reason="Invalid restriction", source="user_authorization")
                    self.assertEqual(before, self._files())

    def test_permission_capability_only_escalation_is_rejected_without_write(self):
        service = self._permissions()
        before = self._files()
        with self.assertRaises(PermissionValidationError):
            service.restrict_permission("subject", "permission", capabilities=["memory:request", "action:execute"],
                reason="Invalid restriction", source="user_authorization")
        self.assertEqual(before, self._files())

    def test_permission_expiry_cannot_be_reactivated_by_restrict_but_explicit_grant_works(self):
        from continuity_engine.domain.permissions import PermissionStatus
        service = self._permissions()
        service.update_status("subject", "permission", PermissionStatus.EXPIRED, reason="Expired", source="user_authorization")
        before = self._files()
        with self.assertRaises(PermissionValidationError):
            service.restrict_permission("subject", "permission", reason="Invalid restrict", source="user_authorization")
        self.assertEqual(before, self._files())
        service.update_status("subject", "permission", PermissionStatus.ACTIVE, reason="Explicit renewed grant", source="user_authorization")
        self.assertTrue(service.check_capability("subject", "memory:request"))
        self.assertEqual(len(service.get_history("subject", "permission")), 3)

    def _budget_fixture(self):
        from tests.test_p02_model_capability import P02ModelCapabilityFixture
        from continuity_engine.domain.model_provider import ProviderModelProfile
        from continuity_engine.testing.fake_model_provider import FakeProviderScenario
        fixture = P02ModelCapabilityFixture()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        profile = ProviderModelProfile("repair-budget", 1, "fake-provider", "fake-model", True, 20, 20, 1)
        scenario = FakeProviderScenario.success("Synthetic answer", input_tokens=10, output_tokens=10)
        return fixture, profile, scenario

    def test_model_positive_reserved_budget_is_rechecked_after_another_request_consumes_it(self):
        from tests.test_p02_model_capability import p02_request
        from tests.test_p02_model_recovery import FailOnceAt
        fixture, profile, scenario = self._budget_fixture()
        app, _ = fixture.app(profile=profile, default=scenario)
        app.models._fault_injector = FailOnceAt("after_provider_dispatch_reserved")
        with self.assertRaises(RuntimeError):
            app.models.submit(p02_request(1))
        rebuilt, provider = fixture.app(profile=profile, default=scenario)
        rebuilt.models.submit(p02_request(2))
        with patch.object(provider, "execute", wraps=provider.execute) as executed:
            rebuilt.models.recover("p02-request-001")
        executed.assert_not_called()
        record = next(r for r in rebuilt.model_ledger.list_executions() if r.request_id == "p02-request-001")
        self.assertEqual(record.attempts[0].request.maximum_tokens, 20)
        self.assertFalse(record.attempts[0].fact.execution_occurred)
        self.assertEqual(len(provider.facts()), 1)

    def test_model_executed_fact_recovers_at_zero_current_budget_without_execute(self):
        from tests.test_p02_model_capability import p02_request
        from tests.test_p02_model_recovery import FailOnceAt
        fixture, profile, scenario = self._budget_fixture()
        app, _ = fixture.app(profile=profile, default=scenario)
        app.models._fault_injector = FailOnceAt("after_provider_returned_before_fact")
        with self.assertRaises(RuntimeError):
            app.models.submit(p02_request(1))
        rebuilt, provider = fixture.app(profile=profile, default=scenario)
        rebuilt.models.submit(p02_request(2))
        with patch.object(provider, "execute", wraps=provider.execute) as executed, \
             patch.object(provider, "query", wraps=provider.query) as queried:
            rebuilt.models.recover("p02-request-001")
        executed.assert_not_called()
        self.assertEqual(queried.call_count, 1)
        record = next(r for r in rebuilt.model_ledger.list_executions() if r.request_id == "p02-request-001")
        self.assertTrue(record.attempts[0].fact.execution_occurred)
        self.assertEqual(record.attempts[0].fact.total_tokens, 20)
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 2)

    def test_model_unknown_at_budget_gate_never_authorizes_execute(self):
        from tests.test_p02_model_capability import p02_request
        from tests.test_p02_model_recovery import FailOnceAt
        from continuity_engine.domain.model_provider import ProviderQueryStatus, ProviderQueryResult
        fixture, profile, scenario = self._budget_fixture()
        app, _ = fixture.app(profile=profile, default=scenario)
        app.models._fault_injector = FailOnceAt("after_provider_dispatch_reserved")
        with self.assertRaises(RuntimeError):
            app.models.submit(p02_request(1))
        rebuilt, provider = fixture.app(profile=profile, default=scenario)
        before = rebuilt.model_ledger.list_executions()[0].to_dict()
        with patch.object(provider, "query", return_value=ProviderQueryResult(ProviderQueryStatus.UNKNOWN)), \
             patch.object(provider, "execute", wraps=provider.execute) as executed:
            rebuilt.models.recover("p02-request-001")
        executed.assert_not_called()
        self.assertEqual(before, rebuilt.model_ledger.list_executions()[0].to_dict())

    def test_scheduler_conflicting_query_has_backoff_without_new_attempt(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        f.service.submit(f.create_task(task_id="conflict"))
        f.adapter.conflict_on_dispatch = True
        f.service.tick(f.subject_id, "TEST")
        f.adapter.conflict_on_query = True
        f.clock.advance(timedelta(seconds=60))
        result = f.service.tick(f.subject_id, "TEST")
        self.assertEqual(result.reason_code, "RECEIPT_BINDING_CONFLICT")
        self.assertGreater(result.task.next_attempt_at, f.clock.now())
        before = self._files()
        f.service.tick(f.subject_id, "TEST")
        self.assertEqual(f.adapter.query_count, 1)
        self.assertEqual(f.adapter.dispatch_count, 1)
        self.assertEqual(result.task.attempt_count, 1)
        self.assertEqual(before, self._files())

    def test_scheduler_pending_queries_and_healthy_stream_progress_after_restart(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        f.service.submit(f.create_task(task_id="unknown"))
        f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        f.service.tick(f.subject_id, "TEST")
        queries = 0
        for i in range(8):
            f = f.restart()
            f.clock.advance(timedelta(seconds=60))
            f.service.submit(f.create_task(task_id=f"healthy-{i}", priority=100))
            result = f.service.tick(f.subject_id, "TEST")
            self.assertEqual(result.task.task_id, f"healthy-{i}")
            self.assertEqual(result.status.value, "COMPLETED")
            self.assertEqual(f.adapter.dispatch_count, 1)
            self.assertEqual(f.adapter.query_count, 1)
            queries += f.adapter.query_count
        unknown = f.service.get("unknown", subject_id=f.subject_id, environment="TEST")
        self.assertEqual(unknown.attempt_count, 1)
        self.assertEqual(unknown.state.value, "UNKNOWN")
        self.assertEqual(queries, 8)

    def test_scheduler_verification_is_fair_among_multiple_unknown_tasks(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW)
        for i in range(3):
            f.service.submit(f.create_task(task_id=f"unknown-{i}"))
            f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
            f.service.tick(f.subject_id, "TEST")
        for _ in range(3):
            f.clock.advance(timedelta(seconds=60))
            f.service.tick(f.subject_id, "TEST")
        self.assertEqual({q.task_id for q in f.adapter.query_requests}, {f"unknown-{i}" for i in range(3)})
        self.assertEqual(f.adapter.dispatch_count, 3)

    def _resource_request(self, **changes):
        fields = dict(request_id="one", subject_id="subject", session_id="one-session",
            session_type=ResourceSessionType.OTHER, estimated_tokens=10, estimated_compute=1,
            model_name="test", reason="Single request", requested_at=NOW)
        fields.update(changes)
        return ResourceRequest.create(**fields)

    def test_resource_duplicate_and_conflict_reject_after_restart_then_settle(self):
        service = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
        service.create_resource_state("subject", token_budget=1000, compute_budget=100, current_mode=RuntimeMode.CONTINUOUS)
        service.request_resources(self._resource_request())
        rebuilt = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
        before = self._files()
        for request in (self._resource_request(), self._resource_request(estimated_tokens=20),
                        self._resource_request(session_id="different"), self._resource_request(request_id="different")):
            with self.subTest(request=request.to_dict()):
                with self.assertRaises(ResourceValidationError):
                    rebuilt.request_resources(request)
                self.assertEqual(before, self._files())
        rebuilt.record_actual_usage("subject", "one-session", 8)
        self.assertEqual(rebuilt.get_resource_state("subject").token_used, 8)
        self.assertEqual(len(rebuilt.get_usage_history("subject")), 1)

    def test_resource_denied_request_may_use_new_identity_when_resources_become_available(self):
        service = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
        service.create_resource_state("subject", token_budget=1000, compute_budget=100, current_mode=RuntimeMode.CONTINUOUS)
        denied = service.request_resources(self._resource_request(estimated_tokens=10000))
        self.assertFalse(denied.decision.allowed)
        before = self._files()
        with self.assertRaises(ResourceValidationError):
            service.request_resources(self._resource_request(estimated_tokens=10000))
        self.assertEqual(before, self._files())
        self.assertTrue(service.request_resources(self._resource_request(request_id="new-authorization")).decision.allowed)
        service.record_actual_usage("subject", "one-session", 8)

    def _validated_learning(self):
        learning = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        state = SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW).create("subject")
        ids = []
        for i in range(3):
            candidate = learning.create_candidate("subject", source_event_id=f"event-{i}", source_memory_id=None,
                related_state_revision=0, observation="Explicit synthetic evaluation", hypothesis="Concise expression",
                proposed_change=StateMutation(field_path="identity.expression_preferences", operation=ChangeOperation.APPEND,
                    value="concise", reason="Explicit evidence"), confidence=0.6, original_experience={"event": i},
                reason="Independent candidate", source="user_evaluation")
            ids.append(candidate.learning_event.learning_id)
        learning.validate_learning("subject", ids[0], ids[1:], reason="Three roots", source="review")
        return learning, state, ids

    def _solidify(self, service, state, identifier, **changes):
        fields = dict(trait_name="Concise", trait_description="Synthetic preference", reason="Confirmed evidence",
                      source="review", confirmed=True, expected_revision=state.revision)
        fields.update(changes)
        return service.solidify_learning("subject", identifier, state, **fields)

    def test_learning_reduced_support_confidence_cannot_reuse_old_validation(self):
        learning, state, ids = self._validated_learning()
        learning.adjust_confidence("subject", ids[1], -0.6, reason="Evidence weakened", source="review")
        before = self._files()
        with self.assertRaises(LearningValidationError):
            self._solidify(learning, state, ids[0])
        self.assertEqual(before, self._files())

    def test_learning_current_sufficient_confidence_is_not_overstated(self):
        learning, state, ids = self._validated_learning()
        learning.adjust_confidence("subject", ids[1], -0.15, reason="Evidence weakened", source="review")
        result = self._solidify(learning, state, ids[0])
        self.assertEqual(result.trait.confidence, 0.75)
        self.assertEqual(result.learning_event.confidence, 0.75)
        self.assertEqual(result.event.metadata["learning_confidence"], 0.75)

    def test_learning_support_root_overlap_and_count_are_rechecked(self):
        learning, state, ids = self._validated_learning()
        repository = learning._repository
        original = repository.load_learning_event
        for changed_roots in (["event:event-0"], []):
            def altered(subject, identifier):
                value = original(subject, identifier)
                if identifier == ids[1]:
                    value.root_evidence_ids = changed_roots
                return value
            with self.subTest(roots=changed_roots), patch.object(repository, "load_learning_event", side_effect=altered):
                before = self._files()
                with self.assertRaises(LearningValidationError):
                    self._solidify(learning, state, ids[0])
                self.assertEqual(before, self._files())

    def test_learning_valid_support_survives_restart_and_requires_explicit_evolution(self):
        learning, state, ids = self._validated_learning()
        rebuilt = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        before = state.to_dict()
        result = self._solidify(rebuilt, state, ids[0])
        self.assertEqual(result.trait.evidence_count, 3)
        self.assertEqual(before, SubjectStateService(JsonSubjectStateRepository(self.root)).load("subject").to_dict())
        self.assertIsNotNone(result.event)
        self.assertEqual(len(rebuilt.get_history("subject", ids[0])), 3)
        with self.assertRaises(LearningValidationError):
            self._solidify(rebuilt, state, ids[0])

    def test_learning_confirmation_gate_remains_before_writes(self):
        learning, state, ids = self._validated_learning()
        before = self._files()
        with self.assertRaises(LearningValidationError):
            self._solidify(learning, state, ids[0], confirmed=False)
        self.assertEqual(before, self._files())

    def test_memory_full_duplicate_does_not_increase_roots_or_confidence(self):
        repo = JsonMemoryRepository(self.root, environment="TEST")
        service = MemoryConsolidationService(repo, clock=lambda: NOW)
        first = service.consolidate(self._memory("first", ["event:one"]))
        candidate = self._memory("alias", ["event:one"])
        candidate.confidence = 0.99
        result = service.consolidate(candidate)
        self.assertEqual(result.unique_evidence_added, 0)
        self.assertEqual(result.memory.confidence, first.memory.confidence)
        self.assertTrue(result.idempotent_replay)

    def test_memory_partial_overlap_preserves_history_provenance_and_conflict_rejection(self):
        from continuity_engine.domain.errors import MemoryEvidenceConflictError
        repo = JsonMemoryRepository(self.root, environment="TEST")
        service = MemoryConsolidationService(repo, clock=lambda: NOW)
        first = service.consolidate(self._memory("first", ["event:one"]))
        candidate = self._memory("partial", ["event:one", "event:two"])
        second = service.consolidate(candidate)
        self.assertEqual(set(second.memory.source_event_ids), {"one", "two"})
        self.assertEqual(second.memory.revision, first.memory.revision + 1)
        self.assertEqual(second.unique_evidence_added, 1)
        before = self._files()
        self.assertTrue(service.consolidate(candidate).idempotent_replay)
        self.assertEqual(before, self._files())

        conflict = self._memory("conflict", ["event:two", "event:three"])
        conflict.content = "Contradictory synthetic content"
        with self.assertRaises(MemoryEvidenceConflictError):
            service.consolidate(conflict)
        self.assertEqual(before, self._files())

    def test_memory_partial_alias_uses_previous_revision_and_new_direct_evidence(self):
        from continuity_engine.domain.errors import MemoryPersistenceError
        repo = JsonMemoryRepository(self.root, environment="TEST")
        service = MemoryConsolidationService(repo, clock=lambda: NOW)
        service.consolidate(self._memory("first", ["event:one"]))
        partial = self._memory("partial", ["event:one", "event:two"])
        partial.source_event_ids = ["two"]
        partial.source_memory_ids = ["first"]
        result = service.consolidate(partial)
        self.assertEqual(result.unique_evidence_added, 1)
        self.assertEqual(set(result.memory.root_evidence_ids), {"event:one", "event:two"})
        self.assertNotIn("first", result.memory.source_memory_ids)
        self.assertEqual(len(repo.memory_history("subject", "first")), 2)
        self.assertTrue(service.consolidate(partial).idempotent_replay)
        forged = self._memory("forged", ["event:one", "event:forged"])
        forged.source_event_ids = []
        forged.source_memory_ids = ["first"]
        before = self._files()
        with self.assertRaises(MemoryPersistenceError):
            service.consolidate(forged)
        self.assertEqual(before, self._files())

    def test_scheduler_foreign_cycle_rejected_without_resource_wake_or_receipt_write(self):
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW, enable_awakening=True)
        states = SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW)
        states.create("other")
        f.resource_manager.create_resource_state("other", token_budget=1000, compute_budget=100)
        cycle = f.awakening_service.create_manual_cycle("other")
        task = f.create_task(task_id="bad-cycle")
        task.cycle_id = cycle.cycle_id
        f.service.submit(task)
        before = self._files()
        with patch.object(f.resource_manager, "request_wake", wraps=f.resource_manager.request_wake) as resources:
            result = f.service.tick(f.subject_id, "TEST")
        resources.assert_not_called()
        self.assertEqual(result.status.value, "VERIFICATION_PENDING")
        self.assertEqual(result.reason_code, "DISPATCH_BINDING_CONFLICT")
        after = self._files()
        self.assertEqual({p:v for p,v in before.items() if not p.startswith("scheduler/")},
                         {p:v for p,v in after.items() if not p.startswith("scheduler/")})
        self.assertEqual(f.wake_count, 0)
        self.assertEqual(f.awakening_repository.list_sessions("other"), [])

    def test_scheduler_test_delivery_rejects_request_binding_changes_before_effects(self):
        from dataclasses import replace
        from continuity_engine.domain.scheduling import SchedulerIdentityConflictError
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW, enable_awakening=True)
        f.service.submit(f.create_task(task_id="bound"))
        f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        f.service.tick(f.subject_id, "TEST")
        request = f.adapter.dispatch_requests[0]
        for changes in ({"subject_id":"other"}, {"environment":"PRODUCTION"},
                        {"cycle_id":"foreign"}, {"attempt_id":"foreign-attempt"}, {"task_id":"foreign-task"}):
            with self.subTest(changes=changes):
                before = self._files()
                with self.assertRaises(SchedulerIdentityConflictError):
                    f.adapter._on_delivered(replace(request, **changes))
                self.assertEqual(before, self._files())
        self.assertEqual(f.wake_count, 0)

    def test_scheduler_existing_session_cycle_mismatch_rejects_before_resources(self):
        from continuity_engine.domain.scheduling import SchedulerIdentityConflictError
        f = P11SchedulerFixture.create(self.root, frozen_at=NOW, enable_awakening=True)
        f.service.submit(f.create_task(task_id="bound"))
        f.adapter.queue_dispatch(NotificationStatus.UNKNOWN)
        f.service.tick(f.subject_id, "TEST")
        request = f.adapter.dispatch_requests[0]
        other = f.awakening_service.create_manual_cycle(f.subject_id)
        f.awakening_service.wake_manual(other.cycle_id, detail="Separate synthetic wake", session_id=request.attempt_id)
        before = self._files()
        with self.assertRaises(SchedulerIdentityConflictError):
            f.adapter._on_delivered(request)
        self.assertEqual(before, self._files())


if __name__ == "__main__":
    unittest.main(verbosity=2)
