"""R05/R06 independent recheck regressions, using only isolated local data."""
import concurrent.futures
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.errors import LearningValidationError, ResourceValidationError
from continuity_engine.domain.events import ChangeOperation, StateMutation
from continuity_engine.domain.learning import LearningValidationStatus
from continuity_engine.domain.resources import ResourceRequest, ResourceSessionType, RuntimeMode
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class IsolatedDataCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="r05-r06-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}


class ResourceTransactionTests(IsolatedDataCase):
    def request(self, tokens, request_id="request", session_id="session"):
        return ResourceRequest.create(request_id=request_id, subject_id="subject",
            session_id=session_id, session_type=ResourceSessionType.OTHER,
            estimated_tokens=tokens, estimated_compute=1, model_name="test",
            reason="Independent resource request", requested_at=NOW)

    def parallel_requests(self, first_tokens, second_tokens, *, second_id="request"):
        repositories = [JsonResourceRepository(self.root) for _ in range(2)]
        managers = [ResourceManager(r, clock=lambda: NOW) for r in repositories]
        managers[0].create_resource_state("subject", token_budget=1000,
            compute_budget=100, current_mode=RuntimeMode.CONTINUOUS)
        # Both requests must pass the service's unlocked precheck. The first
        # durable result is then fixed so its exact bytes can be compared.
        reached_policy = threading.Barrier(2)
        first_finished = threading.Event()
        policies = [m._policy.evaluate for m in managers]
        after_first = []

        def evaluate(index, *args, **kwargs):
            reached_policy.wait(timeout=5)
            if index == 1:
                self.assertTrue(first_finished.wait(5), "first request did not finish")
            return policies[index](*args, **kwargs)

        def run(index, tokens, identity):
            try:
                result = managers[index].request_resources(self.request(tokens, identity))
                return "allowed" if result.decision.allowed else "denied"
            except ResourceValidationError:
                return "identity-rejected"
            finally:
                if index == 0:
                    after_first.append(self.files())
                    first_finished.set()

        with patch.object(managers[0]._policy, "evaluate", side_effect=lambda *a, **k: evaluate(0, *a, **k)), \
             patch.object(managers[1]._policy, "evaluate", side_effect=lambda *a, **k: evaluate(1, *a, **k)):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(run, 0, first_tokens, "request")
                second = pool.submit(run, 1, second_tokens, second_id)
                outcomes = [first.result(timeout=8), second.result(timeout=8)]
        self.assertEqual(outcomes, ["allowed" if first_tokens <= 1000 else "denied", "identity-rejected"])
        self.assertEqual(after_first[0], self.files(), "conflict appended or rewrote durable data")
        self.assertEqual(len(repositories[0].list_decisions("subject")), 1)
        self.assertEqual(len(repositories[0].list_usage("subject")), int(first_tokens <= 1000))
        self.assertEqual(managers[0].get_resource_state("subject").token_used,
                         first_tokens if first_tokens <= 1000 else 0)
        if first_tokens <= 1000:
            restarted = ResourceManager(JsonResourceRepository(self.root), clock=lambda: NOW)
            restarted.record_actual_usage("subject", "session", 8)
            self.assertEqual(restarted.get_resource_state("subject").token_used, 8)
            self.assertEqual(len(restarted.get_usage_history("subject")), 1)

    def test_concurrent_denied_duplicate_preserves_first_result(self):
        self.parallel_requests(10000, 10000)

    def test_concurrent_allowed_then_conflicting_denial_preserves_first_result(self):
        self.parallel_requests(10, 10000)

    def test_concurrent_denied_then_conflicting_allowance_preserves_first_result(self):
        self.parallel_requests(10000, 10)

    def test_concurrent_allowed_duplicate_charges_once_then_settles(self):
        self.parallel_requests(10, 10)

    def test_concurrent_new_request_cannot_deny_an_allocated_session(self):
        self.parallel_requests(10, 10000, second_id="new-request")

    def test_denials_allow_new_identity_then_allocation_and_settlement(self):
        repository = JsonResourceRepository(self.root)
        manager = ResourceManager(repository, clock=lambda: NOW)
        manager.create_resource_state("subject", token_budget=1000,
            compute_budget=100, current_mode=RuntimeMode.CONTINUOUS)
        self.assertFalse(manager.request_resources(self.request(10000)).decision.allowed)
        self.assertFalse(manager.request_resources(self.request(20000, "retry-denied")).decision.allowed)
        self.assertEqual(manager.get_resource_state("subject").token_used, 0)
        self.assertEqual(len(repository.list_usage("subject")), 0)
        self.assertTrue(manager.request_resources(self.request(10, "retry-allowed")).decision.allowed)
        manager.record_actual_usage("subject", "session", 8)
        self.assertEqual(manager.get_resource_state("subject").token_used, 8)
        self.assertEqual(len(repository.list_decisions("subject")), 3)
        self.assertEqual(len(repository.list_usage("subject")), 1)


class LearningConfidenceTests(IsolatedDataCase):
    def validated(self, confidences=(0.95, 0.2, 0.2)):
        self.states = SubjectStateService(JsonSubjectStateRepository(self.root), clock=lambda: NOW)
        self.state = self.states.create("subject")
        self.learning = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        self.ids = []
        for index, confidence in enumerate(confidences):
            candidate = self.learning.create_candidate("subject", source_event_id=f"source-{index}",
                source_memory_id=None, related_state_revision=self.state.revision,
                observation="Explicit synthetic evaluation", hypothesis="Concise preference",
                proposed_change=StateMutation(field_path="identity.expression_preferences",
                    operation=ChangeOperation.APPEND, value="concise", reason="Consistent evidence"),
                confidence=confidence, original_experience={"source": index},
                reason="Independent evidence", source="review").learning_event
            self.ids.append(candidate.learning_id)
        return self.learning.validate_learning("subject", self.ids[0], self.ids[1:],
            reason="Validate current evidence", source="review").learning_event

    def solidify(self, confirmed=True):
        return self.learning.solidify_learning("subject", self.ids[0], self.state,
            trait_name="Concise", trait_description="Concise expression", confirmed=confirmed,
            expected_revision=self.state.revision, reason="Confirm evidence", source="review")

    def assert_confidence(self, expected):
        history = [r.to_dict() for r in self.learning.get_history("subject", self.ids[0])]
        result = self.solidify()
        self.assertEqual(result.learning_event.confidence, expected)
        self.assertEqual(result.trait.confidence, expected)
        self.assertEqual(result.event.metadata["learning_confidence"], expected)
        self.assertEqual(result.trait.evidence_count, 3)
        self.assertEqual(history, [r.to_dict() for r in self.learning.get_history("subject", self.ids[0])][:-1])
        self.assertEqual(self.states.load("subject").to_dict(), self.state.to_dict())
        return result

    def test_unchanged_high_target_validation_can_immediately_solidify(self):
        validated = self.validated()
        self.assertEqual(validated.validation_status, LearningValidationStatus.VALIDATED)
        self.assertEqual(validated.confidence, 0.95)
        self.assert_confidence(0.95)

    def test_unchanged_high_target_validation_survives_restart(self):
        self.validated()
        self.learning = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        self.assert_confidence(0.95)

    def test_aggregate_does_not_corroborate_itself_again(self):
        self.assertEqual(self.validated((0.6, 0.6, 0.6)).confidence, 0.8)
        self.assert_confidence(0.8)
        before = self.files()
        with self.assertRaises(LearningValidationError):
            self.solidify()
        self.assertEqual(before, self.files())

    def test_weaker_but_sufficient_current_support_is_saved(self):
        self.validated((0.6, 0.6, 0.6))
        self.learning.adjust_confidence("subject", self.ids[1], -0.15, reason="Weaker evidence", source="review")
        self.assert_confidence(0.75)

    def test_current_target_confidence_reduction_is_respected(self):
        self.validated()
        self.learning.adjust_confidence("subject", self.ids[0], -0.15, reason="Lower target confidence", source="review")
        self.assert_confidence(0.95 - 0.15)

    def test_high_own_confidence_retains_existing_policy_with_weaker_support(self):
        self.validated()
        self.learning.adjust_confidence("subject", self.ids[1], -0.1, reason="Weaker evidence", source="review")
        self.assert_confidence(0.95)

    def test_insufficient_current_confidence_rejects_without_writes(self):
        self.validated((0.6, 0.6, 0.6))
        self.learning.adjust_confidence("subject", self.ids[1], -0.6, reason="Evidence weakened", source="review")
        before = self.files()
        with self.assertRaises(LearningValidationError):
            self.solidify()
        self.assertEqual(before, self.files())

    def test_high_own_confidence_cannot_replace_rejected_support(self):
        self.validated()
        self.learning.reject_learning("subject", self.ids[1], reason="Rejected evidence", source="review")
        before = self.files()
        with self.assertRaises(LearningValidationError):
            self.solidify()
        self.assertEqual(before, self.files())

    def test_high_own_confidence_still_rechecks_support_and_roots(self):
        self.validated()
        repository = self.learning._repository
        original = repository.load_learning_event
        for defect in ("revoked", "overlap", "missing-root", "content", "duplicate-id", "insufficient-ids"):
            def altered(subject, identifier):
                result = original(subject, identifier)
                if identifier == self.ids[1]:
                    if defect == "revoked":
                        result.validation_status = LearningValidationStatus.REVOKED
                    elif defect == "overlap":
                        result.root_evidence_ids = ["event:source-0"]
                    elif defect == "missing-root":
                        result.root_evidence_ids = []
                    elif defect == "content":
                        result.proposed_change.value = "verbose"
                if identifier == self.ids[0]:
                    if defect == "duplicate-id":
                        result.evidence_learning_ids = [self.ids[0], self.ids[1], self.ids[1]]
                    elif defect == "insufficient-ids":
                        result.evidence_learning_ids = self.ids[:2]
                return result
            with self.subTest(defect=defect), patch.object(repository, "load_learning_event", side_effect=altered):
                before = self.files()
                with self.assertRaises(LearningValidationError):
                    self.solidify()
                self.assertEqual(before, self.files())

    def test_explicit_confirmation_still_required(self):
        self.validated()
        before = self.files()
        with self.assertRaises(LearningValidationError):
            self.solidify(confirmed=False)
        self.assertEqual(before, self.files())


if __name__ == "__main__":
    unittest.main()
