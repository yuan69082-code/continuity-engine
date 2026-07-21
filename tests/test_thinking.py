import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.awakening import WakeAction
from continuity_engine.domain.errors import ThinkingExecutionError, ThinkingValidationError
from continuity_engine.domain.events import ChangeOperation, StateMutation, StateSection
from continuity_engine.domain.memory import MemoryCandidate
from continuity_engine.domain.perception import PerceptionResult
from continuity_engine.domain.thinking import (
    ThinkingDepth,
    ThinkingResult,
    TokenBudget,
)
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.services.wake_perception_thinking_service import (
    WakePerceptionThinkingService,
)
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


class CandidateRetriever:
    def __init__(self, candidates=None) -> None:
        self.candidates = list(candidates or [])

    def retrieve(self, request):
        return list(self.candidates)


class DiscardingInfluenceRecorder:
    def record_influence(self, record) -> None:
        pass


class FixedTokenBudgetManager:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests = []
        self.usage_records = []

    def allocate(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("token budget unavailable")
        return TokenBudget(
            maximum_tokens=10_000,
            remaining_tokens=8_000,
            session_tokens=1_000,
            depth=request.depth,
        )

    def record_usage(self, think_id, actual_tokens):
        self.usage_records.append((think_id, actual_tokens))
        raise AssertionError("usage accounting must not run in this stage")


class WritingThinkingProvider:
    provider_id = "test-writing-provider"

    def __init__(self) -> None:
        self.calls = []

    def think(self, context, budget):
        self.calls.append((context, budget))
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary="A new implementation thought was formed.",
            rationale_summary=(
                "The selected memory and current state both concern unfinished continuity work."
            ),
            generated_new_thought=True,
            update_subject_state=True,
            request_more_memory=False,
            should_wait=False,
            suggest_future_user_contact=False,
            token_budget=budget,
            proposed_mutations=[
                StateMutation(
                    field_path="intentions.emerging_thoughts",
                    operation=ChangeOperation.APPEND,
                    value="preserve Wake-to-Think causality",
                    reason="The internal review identified a continuity requirement.",
                )
            ],
        )


class WaitingThinkingProvider:
    provider_id = "test-waiting-provider"

    def __init__(self) -> None:
        self.calls = 0

    def think(self, context, budget):
        self.calls += 1
        return ThinkingResult.create(
            provider_id=self.provider_id,
            result_summary="No safe state change is needed yet.",
            rationale_summary="The available context is insufficient for a state mutation.",
            generated_new_thought=False,
            update_subject_state=False,
            request_more_memory=True,
            additional_memory_query="Retrieve more context about the unfinished work.",
            should_wait=True,
            suggest_future_user_contact=True,
            token_budget=budget,
        )


class FailingThinkingProvider:
    provider_id = "test-failing-provider"

    def __init__(self) -> None:
        self.calls = 0

    def think(self, context, budget):
        self.calls += 1
        raise RuntimeError("thinking provider unavailable")


class ThinkingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)

    def build_flow(self, directory, provider, budgets, *, with_memory=True):
        states = SubjectStateService(
            JsonSubjectStateRepository(directory),
            clock=lambda: self.now,
        )
        states.create("subject-1")
        candidates = []
        if with_memory:
            candidates.append(
                MemoryCandidate(
                    memory_id="memory-for-thinking",
                    subject_id="subject-1",
                    content="There is unfinished continuity engine work.",
                    source="external-memory-adapter",
                    occurred_at=self.now - timedelta(days=1),
                    provider_relevance=0.9,
                    related_scope=[StateSection.CONTINUITY],
                )
            )
        memory = MemoryService(
            CandidateRetriever(candidates),
            DiscardingInfluenceRecorder(),
            clock=lambda: self.now,
        )
        awakening = AwakeningService(
            states,
            memory,
            JsonAwakeningRepository(directory),
            clock=lambda: self.now,
        )
        thinking_repository = JsonThinkingRepository(directory)
        thinking = ThinkingService(
            provider,
            budgets,
            states,
            thinking_repository,
            clock=lambda: self.now,
        )
        flow = WakePerceptionThinkingService(
            awakening,
            PerceptionService(),
            thinking,
            clock=lambda: self.now,
        )
        cycle = awakening.create_manual_cycle("subject-1")
        return states, awakening, thinking_repository, flow, cycle

    def test_wake_think_result_and_state_writeback_complete_full_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = WritingThinkingProvider()
            budgets = FixedTokenBudgetManager()
            states, _, repository, flow, cycle = self.build_flow(
                directory, provider, budgets
            )

            result = flow.wake_manual(
                cycle.cycle_id,
                detail="Run the internal thinking framework.",
                depth=ThinkingDepth.NORMAL,
            )

            self.assertEqual(result.awakening.session.decision.action, WakeAction.THINK)
            self.assertIsInstance(result.perception, PerceptionResult)
            self.assertIsNotNone(result.thinking)
            thinking = result.thinking
            assert thinking is not None
            self.assertTrue(thinking.session.completed_successfully)
            self.assertTrue(thinking.session.state_written_back)
            self.assertIsNone(thinking.session.actual_token_consumption)
            self.assertEqual(thinking.session.token_budget.maximum_tokens, 10_000)
            self.assertEqual(thinking.session.token_budget.remaining_tokens, 8_000)
            self.assertEqual(thinking.session.token_budget.session_tokens, 1_000)
            self.assertEqual(thinking.session.token_budget.depth, ThinkingDepth.NORMAL)
            self.assertEqual(len(provider.calls), 1)
            self.assertIs(provider.calls[0][0], result.perception)
            self.assertEqual(len(budgets.requests), 1)
            self.assertEqual(budgets.usage_records, [])

            restored_state = states.load("subject-1")
            self.assertEqual(restored_state.revision, 1)
            self.assertEqual(
                restored_state.intentions.emerging_thoughts,
                ["preserve Wake-to-Think causality"],
            )
            self.assertEqual(thinking.state_update.update_id, thinking.session.state_update_id)
            self.assertEqual(
                thinking.state_update.event.metadata["think_id"],
                thinking.session.think_id,
            )
            self.assertEqual(
                thinking.state_update.event.metadata["perception_id"],
                result.perception.perception_id,
            )
            self.assertEqual(
                thinking.session.observation.perception_id,
                result.perception.perception_id,
            )
            self.assertIn(
                result.perception.summary,
                thinking.session.thinking_reason,
            )

            restored_session = JsonThinkingRepository(directory).load_think_session(
                "subject-1", thinking.session.think_id
            )
            self.assertEqual(restored_session.to_dict(), thinking.session.to_dict())
            self.assertEqual(repository.list_think_sessions("subject-1"), [thinking.session])

    def test_non_think_wake_does_not_create_think_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = WaitingThinkingProvider()
            budgets = FixedTokenBudgetManager()
            _, _, repository, flow, cycle = self.build_flow(
                directory,
                provider,
                budgets,
                with_memory=False,
            )

            result = flow.wake_manual(cycle.cycle_id, detail="Quiet internal check.")

            self.assertEqual(result.awakening.session.decision.action, WakeAction.SLEEP)
            self.assertIsInstance(result.perception, PerceptionResult)
            self.assertIsNone(result.thinking)
            self.assertEqual(provider.calls, 0)
            self.assertEqual(budgets.requests, [])
            self.assertEqual(repository.list_think_sessions("subject-1"), [])

    def test_standard_result_can_request_memory_wait_and_future_contact_without_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = WaitingThinkingProvider()
            budgets = FixedTokenBudgetManager()
            states, _, _, flow, cycle = self.build_flow(directory, provider, budgets)

            result = flow.wake_manual(cycle.cycle_id, detail="Review selected memory.")

            thinking = result.thinking
            assert thinking is not None
            output = thinking.session.result
            self.assertTrue(output.request_more_memory)
            self.assertTrue(output.should_wait)
            self.assertTrue(output.suggest_future_user_contact)
            self.assertFalse(output.update_subject_state)
            self.assertFalse(thinking.session.state_written_back)
            self.assertEqual(states.load("subject-1").revision, 0)

    def test_provider_failure_is_summarized_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = FailingThinkingProvider()
            budgets = FixedTokenBudgetManager()
            _, _, repository, flow, cycle = self.build_flow(directory, provider, budgets)

            with self.assertRaises(ThinkingExecutionError) as captured:
                flow.wake_manual(cycle.cycle_id, detail="Attempt internal thinking.")

            sessions = repository.list_think_sessions("subject-1")
            self.assertEqual(len(sessions), 1)
            session = sessions[0]
            self.assertEqual(session.think_id, captured.exception.think_id)
            self.assertFalse(session.completed_successfully)
            self.assertFalse(session.state_written_back)
            self.assertIsNone(session.actual_token_consumption)
            self.assertTrue(session.result.should_wait)
            self.assertIn("thinking provider unavailable", session.error)
            self.assertNotIn("chain_of_thought", session.to_dict())

    def test_budget_failure_still_creates_failed_think_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = WaitingThinkingProvider()
            budgets = FixedTokenBudgetManager(fail=True)
            _, _, repository, flow, cycle = self.build_flow(directory, provider, budgets)

            with self.assertRaises(ThinkingExecutionError):
                flow.wake_manual(cycle.cycle_id, detail="Attempt budgeted thinking.")

            sessions = repository.list_think_sessions("subject-1")
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].token_budget.session_tokens, 0)
            self.assertIn("token budget unavailable", sessions[0].error)
            self.assertEqual(provider.calls, 0)

    def test_thinking_result_cannot_write_identity_or_emotion_state(self) -> None:
        budget = TokenBudget(1_000, 1_000, 500, ThinkingDepth.LOW)

        with self.assertRaises(ThinkingValidationError):
            ThinkingResult.create(
                provider_id="test-provider",
                result_summary="Disallowed identity mutation.",
                rationale_summary="Identity learning is outside this stage.",
                generated_new_thought=True,
                update_subject_state=True,
                request_more_memory=False,
                should_wait=False,
                suggest_future_user_contact=False,
                token_budget=budget,
                proposed_mutations=[
                    StateMutation(
                        field_path="identity.self_concept",
                        operation=ChangeOperation.SET,
                        value="changed identity",
                        reason="This must be rejected in the current stage.",
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
