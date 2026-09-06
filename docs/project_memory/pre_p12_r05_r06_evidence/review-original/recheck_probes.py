"""Independent post-repair checks; all engine data is confined to Temp fixtures.

Keep the original 13 applicable tests unchanged through inheritance. Replace
only the old in-lock barrier test and the resource-replay-only assertion.
Additional cases exercise concurrency and unchanged-evidence compatibility.
"""
import concurrent.futures
import importlib.util
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "original_review", Path(__file__).parents[1] / "engine-pre-p12-20260905" / "review_probes.py"
)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)

from continuity_engine.domain.errors import EventIdentityConflictError, ResourceValidationError


class RecheckProbes(original.EngineReviewProbes):
    def _event_pair(self, mode):
        repos = [original.JsonSubjectStateRepository(self.root) for _ in range(2)]
        services = [original.SubjectStateService(r, clock=lambda: original.NOW) for r in repos]
        services[0].create("subject")
        paused, release, second_started, second_done = (threading.Event() for _ in range(4))
        real_write = repos[0]._write_payload

        def delayed_write(path, data):
            paused.set()
            if not release.wait(3):
                raise AssertionError("Review harness did not release the first writer")
            return real_write(path, data)

        def event(identifier, text):
            return original.Event.create(event_id=identifier, occurred_at=original.NOW,
                source="review", event_type="observation", content=text,
                classification=original.EventClassification.FACT,
                impact_scope=[original.StateSection.CONTINUITY], mutations=[], reason="Concurrent probe")

        first = event("one", "First observation")
        second = event("two", "Second observation") if mode == "different" else (
            first if mode == "same" else event("one", "Conflicting observation"))

        def second_call():
            second_started.set()
            try:
                return services[1].apply_event("subject", second)
            finally:
                second_done.set()

        with patch.object(repos[0], "_write_payload", side_effect=delayed_write):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(services[0].apply_event, "subject", first)
                try:
                    self.assertTrue(paused.wait(2))
                    b = pool.submit(second_call)
                    self.assertTrue(second_started.wait(2))
                    second_done.wait(0.15)
                finally:
                    release.set()
                results = [a.result(timeout=3)]
                if mode == "conflict":
                    with self.assertRaises(EventIdentityConflictError):
                        b.result(timeout=3)
                else:
                    results.append(b.result(timeout=3))
        saved = services[0].get_update_history("subject")
        self.assertEqual(len(saved), 2 if mode == "different" else 1)
        self.assertEqual(len(results), 1 if mode == "conflict" else 2)
        self.assertTrue({r.update.update_id for r in results}.issubset({r.update_id for r in saved}))
        original.evidence("recheck_events", mode=mode, successful=len(results), persisted=len(saved))

    def test_concurrent_events_are_not_silently_lost(self):
        self._event_pair("different")

    def test_extra_same_event_returns_the_persisted_identity(self):
        self._event_pair("same")

    def test_extra_conflicting_event_identity_is_rejected(self):
        self._event_pair("conflict")

    def _resource_request(self, *, tokens=10):
        return original.ResourceRequest.create(request_id="same-request", subject_id="subject",
            session_id="same-session", session_type=original.ResourceSessionType.OTHER,
            estimated_tokens=tokens, estimated_compute=1, model_name="test",
            reason="One operation", requested_at=original.NOW)

    def _resource_managers(self):
        repos = [original.JsonResourceRepository(self.root) for _ in range(2)]
        managers = [original.ResourceManager(r, clock=lambda: original.NOW) for r in repos]
        managers[0].create_resource_state("subject", token_budget=1000, compute_budget=100,
            current_mode=original.RuntimeMode.CONTINUOUS)
        return repos, managers

    def test_repeated_resource_request_remains_reconcilable(self):
        repos, managers = self._resource_managers()
        managers[0].request_resources(self._resource_request())
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaises(ResourceValidationError):
            managers[1].request_resources(self._resource_request())
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        managers[1].record_actual_usage("subject", "same-session", 8)
        self.assertEqual(managers[1].get_resource_state("subject").token_used, 8)
        self.assertEqual(len(repos[1].list_usage("subject")), 1)

    def _parallel_resources(self, first_tokens, second_tokens, *, allowed_first=False):
        repos, managers = self._resource_managers()
        at_policy = threading.Barrier(2)
        first_finished = threading.Event()
        real = [m._policy.evaluate for m in managers]

        def evaluate(index, *args, **kwargs):
            at_policy.wait(timeout=3)
            if allowed_first and index == 1 and not first_finished.wait(3):
                raise AssertionError("First allocation did not finish")
            return real[index](*args, **kwargs)

        def request(index, tokens):
            try:
                result = managers[index].request_resources(self._resource_request(tokens=tokens))
                return "allocated" if result.decision.allowed else "denied"
            except ResourceValidationError:
                return "duplicate-rejected"
            finally:
                if index == 0:
                    first_finished.set()

        with patch.object(managers[0]._policy, "evaluate", side_effect=lambda *a, **k: evaluate(0, *a, **k)), \
             patch.object(managers[1]._policy, "evaluate", side_effect=lambda *a, **k: evaluate(1, *a, **k)):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(request, 0, first_tokens), pool.submit(request, 1, second_tokens)]
                outcomes = [f.result(timeout=5) for f in futures]
        decisions = repos[0].list_decisions("subject")
        original.evidence("parallel_resource_identity", tokens=[first_tokens, second_tokens],
            outcomes=outcomes, decision_count=len(decisions), request_ids=[d.request_id for d in decisions],
            charged=managers[0].get_resource_state("subject").token_used)
        self.assertEqual(len(decisions), 1, "One stable request identity acquired multiple decisions")
        self.assertEqual(outcomes.count("duplicate-rejected"), 1)

    def test_extra_concurrent_allowed_resource_requests_allocate_once(self):
        self._parallel_resources(10, 10)

    def test_extra_concurrent_denied_resource_requests_reject_duplicate_identity(self):
        self._parallel_resources(10000, 10000)

    def test_extra_concurrent_conflicting_resource_request_cannot_append_denial(self):
        self._parallel_resources(10, 10000, allowed_first=True)

    def test_extra_freshly_validated_learning_with_unchanged_support_can_solidify(self):
        learning = original.LearningService(original.JsonLearningRepository(self.root), clock=lambda: original.NOW)
        state = original.SubjectStateService(original.JsonSubjectStateRepository(self.root), clock=lambda: original.NOW).create("subject")
        candidates = []
        for i, confidence in enumerate((0.95, 0.2, 0.2)):
            candidates.append(learning.create_candidate("subject", source_event_id=f"source-{i}",
                source_memory_id=None, related_state_revision=state.revision, observation="Explicit evaluation",
                hypothesis="Concise preference", proposed_change=original.StateMutation(
                    field_path="identity.expression_preferences", operation=original.ChangeOperation.APPEND,
                    value="concise", reason="Consistent evidence"), confidence=confidence,
                original_experience={"source": i}, reason="Independent evidence", source="review").learning_event)
        validated = learning.validate_learning("subject", candidates[0].learning_id,
            [c.learning_id for c in candidates[1:]], reason="Validate current evidence", source="review")
        self.assertEqual(validated.learning_event.validation_status.value, "VALIDATED")
        error, result = None, None
        try:
            result = learning.solidify_learning("subject", candidates[0].learning_id, state,
                trait_name="Concise", trait_description="Concise expression", confirmed=True,
                expected_revision=state.revision, reason="Confirm unchanged validation", source="review")
        except original.LearningValidationError as exc:
            error = str(exc)
        original.evidence("unchanged_learning_support", validated_confidence=validated.learning_event.confidence,
            evidence_changed=False, error=error, trait_count=len(learning.list_traits("subject")))
        self.assertIsNone(error, "Fresh validation and immediate solidification disagree without evidence changes")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
