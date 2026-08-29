from __future__ import annotations

import copy
import json
import socket
import tempfile
import unittest
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.capability import (
    CapabilityFailedEnvelope,
    CapabilityRequiredEnvelope,
    CapabilityStatus,
)
from continuity_engine.domain.errors import (
    IntegrationPersistenceError,
    ModelProviderConflictError,
    ModelProviderNotFoundError,
    ModelProviderValidationError,
)
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from continuity_engine.domain.integration_results import FirstRoundErrorCode, FirstRoundErrorEnvelope
from continuity_engine.domain.model_provider import (
    REAL_PROVIDER_USAGE_DEFERRED,
    ProviderExecutionFact,
    ProviderExecutionStatus,
    ProviderModelProfile,
    ProviderQueryResult,
    ProviderQueryStatus,
)
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.interfaces.local_integration_app import initialize_local_integration
from continuity_engine.interfaces.local_model_capability_app import (
    build_local_model_capability_app,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_request_hash,
)
from continuity_engine.services.model_profile_policy import (
    ConfiguredModelProfilePolicy,
)
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository
from continuity_engine.testing.fake_model_provider import (
    FakeProviderScenario,
    ScriptedFakeModelProvider,
)
from tests.test_contract_test_adapter import first_round_request


class ResolvingModelProvider:
    """Test-only Provider that can resolve one ambiguous attempt by query."""

    def __init__(
        self,
        *,
        initial_status: ProviderExecutionStatus = ProviderExecutionStatus.UNKNOWN,
        query_status: ProviderQueryStatus = ProviderQueryStatus.FOUND,
    ) -> None:
        self.initial_status = initial_status
        self.query_status = query_status
        self.execute_count = 0
        self.query_count = 0

    def execute(self, request):
        self.execute_count += 1
        if self.execute_count == 1:
            status = self.initial_status
            started = parse_capability_datetime(request.created_at) + timedelta(seconds=1)
            return ProviderExecutionFact(
                execution_id=request.execution_id,
                attempt_id=request.attempt_id,
                request_fingerprint=request.request_fingerprint,
                provider_id=request.profile.provider_id,
                model_name=request.profile.model_name,
                status=status,
                response_candidate=None,
                input_tokens=0,
                output_tokens=0,
                finish_reason=None,
                error_code=status.value,
                retry_class="query",
                started_at=format_contract_datetime(started),
                completed_at=format_contract_datetime(started + timedelta(seconds=1)),
                execution_occurred=True,
            )
        return self._success(request, "Controlled retry completed.")

    def query(self, request):
        self.query_count += 1
        if self.query_status is ProviderQueryStatus.FOUND:
            return ProviderQueryResult(
                ProviderQueryStatus.FOUND,
                self._success(request, "Query resolved the original attempt."),
            )
        return ProviderQueryResult(self.query_status)

    @staticmethod
    def _success(request, candidate: str) -> ProviderExecutionFact:
        started = parse_capability_datetime(request.created_at) + timedelta(seconds=1)
        return ProviderExecutionFact(
            execution_id=request.execution_id,
            attempt_id=request.attempt_id,
            request_fingerprint=request.request_fingerprint,
            provider_id=request.profile.provider_id,
            model_name=request.profile.model_name,
            status=ProviderExecutionStatus.SUCCEEDED,
            response_candidate=candidate,
            input_tokens=6,
            output_tokens=4,
            finish_reason="stop",
            error_code=None,
            retry_class=None,
            started_at=format_contract_datetime(started),
            completed_at=format_contract_datetime(started + timedelta(seconds=2)),
            execution_occurred=True,
        )


def p02_request(
    ordinal: int,
    content: str = "hello",
) -> dict[str, object]:
    payload = first_round_request(
        content,
        request_id=f"p02-request-{ordinal:03d}",
    )
    conversation = payload["conversation"]
    assert isinstance(conversation, dict)
    conversation.update(
        {
            "messageId": f"p02-message-{ordinal:03d}",
            "messageVersionId": f"p02-message-version-{ordinal:03d}",
        }
    )
    package = payload["platformFactPackage"]
    assert isinstance(package, dict)
    fact = package["facts"][0]
    assert isinstance(fact, dict)
    fact.update(
        {
            "factId": f"p02-fact-{ordinal:03d}",
            "messageId": conversation["messageId"],
            "messageVersionId": conversation["messageVersionId"],
        }
    )
    observation = payload["observations"][0]
    assert isinstance(observation, dict)
    observation.update(
        {
            "observationId": f"p02-observation-{ordinal:03d}",
            "sourceEventId": f"p02-source-event-{ordinal:03d}",
        }
    )
    reference = observation["messageVersionRef"]
    assert isinstance(reference, dict)
    reference.update(conversation)
    package["observationRefs"] = [observation["observationId"]]
    payload["requestHash"] = calculate_request_hash(payload)
    return payload


class P02ModelCapabilityFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data = self.root / "engine-data"
        self.provider_root = self.root / "provider-fixture"
        fixture = SubjectBindingFixture.first_round()
        binding_file = self.root / "binding.json"
        binding_file.write_text(json.dumps(fixture.to_dict()), encoding="utf-8")
        initialize_local_integration(
            data_dir=self.data,
            binding_file=binding_file,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
            cycle_id="p02-cycle-001",
        )
        self.profile = ProviderModelProfile(
            profile_id="p02-local-profile",
            profile_version=1,
            provider_id="Alibaba Cloud Model Studio",
            model_name="qwen-flash-2025-07-28",
            enabled=True,
            per_execution_token_limit=1024,
            daily_token_limit=10240,
            success_test_credit=1,
            fallback_enabled=False,
        )
        self.clock = lambda: datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def policy(self, profile: ProviderModelProfile | None = None):
        selected = profile or self.profile
        return ConfiguredModelProfilePolicy(
            (selected,),
            selected_profile_id=selected.profile_id,
        )

    def app(
        self,
        *,
        scenarios: dict[str, tuple[FakeProviderScenario, ...]] | None = None,
        profile: ProviderModelProfile | None = None,
        default: FakeProviderScenario | None = None,
    ):
        provider = ScriptedFakeModelProvider(
            self.provider_root,
            scenarios=scenarios,
            default_scenario=default,
        )
        app = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy(profile),
            clock=self.clock,
        )
        return app, provider

    def resolving_app(
        self,
        *,
        initial_status: ProviderExecutionStatus = ProviderExecutionStatus.UNKNOWN,
        query_status: ProviderQueryStatus = ProviderQueryStatus.FOUND,
    ):
        provider = ResolvingModelProvider(
            initial_status=initial_status,
            query_status=query_status,
        )
        app = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy(),
            clock=self.clock,
        )
        return app, provider

    def assert_usage_tamper_rejected(
        self,
        changes: (
            dict[str, object]
            | Callable[[dict[str, object]], dict[str, object]]
        ),
    ) -> None:
        app, _ = self.app(
            default=FakeProviderScenario.success(
                "Persist one auditable usage fact.",
                input_tokens=6,
                output_tokens=4,
            )
        )
        app.models.submit(p02_request(1))
        document = json.loads(app.model_ledger.path.read_text(encoding="utf-8"))
        usage_entry = document["usageEntries"][0]
        assert isinstance(usage_entry, dict)
        resolved_changes = changes(usage_entry.copy()) if callable(changes) else changes
        usage_entry.update(resolved_changes)
        app.model_ledger.path.write_text(
            json.dumps(document, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        with self.assertRaises(IntegrationPersistenceError):
            app.model_ledger.list_usage()


class P02ModelCapabilityTests(P02ModelCapabilityFixture):
    def test_confirmed_profile_is_configurable_metadata_not_permanent_vendor_binding(
        self,
    ) -> None:
        app, _ = self.app()
        result = app.models.submit(p02_request(1))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(record.profile.provider_id, "Alibaba Cloud Model Studio")
        self.assertEqual(record.profile.model_name, "qwen-flash-2025-07-28")
        self.assertEqual(record.profile.per_execution_token_limit, 1024)
        self.assertEqual(record.profile.daily_token_limit, 10240)
        self.assertFalse(record.profile.fallback_enabled)

    def test_unknown_disabled_and_fallback_profiles_fail_closed(self) -> None:
        unknown = ConfiguredModelProfilePolicy(
            (self.profile,), selected_profile_id="missing"
        )
        with self.assertRaises(ModelProviderNotFoundError):
            unknown.select()
        disabled = ProviderModelProfile(
            "disabled", 1, "replaceable", "model", False, 1024, 10240, 1
        )
        with self.assertRaises(ModelProviderValidationError):
            self.policy(disabled).select()
        fallback = ProviderModelProfile(
            "fallback", 1, "replaceable", "model", True, 1024, 10240, 1, True
        )
        with self.assertRaises(ModelProviderValidationError):
            self.policy(fallback).select()

    def test_success_uses_original_think_session_action_and_reply_composer(self) -> None:
        app, _ = self.app(default=FakeProviderScenario.success("P02 expression"))
        result = app.models.submit(p02_request(1))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        assert isinstance(result, FirstRoundSuccessResult)
        record = app.model_ledger.list_executions()[0]
        operation = app.integration.ledger.load_operation(result.request_id)
        assert operation is not None and operation.domain is not None
        sessions = JsonThinkingRepository(self.data).list_think_sessions("subject-001")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            sessions[0].think_id,
            operation.domain.think_session_id,
        )
        self.assertEqual(sessions[0].capability_request_id, record.capability_request_id)
        self.assertEqual(sessions[0].provider_id, "engine-host-neutral-model-capability")
        self.assertEqual(result.response.content, "P02 expression")
        self.assertIn("thinking_resume", app.integration.adapter.service.last_call_log)
        self.assertIn("action", app.integration.adapter.service.last_call_log)

    def test_success_persists_one_execution_usage_and_synthetic_credit(self) -> None:
        app, provider = self.app()
        app.models.submit(p02_request(1))
        record = app.model_ledger.list_executions()[0]
        usage = app.model_ledger.list_usage()
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].test_credits, 1)
        self.assertTrue(usage[0].synthetic)
        self.assertEqual(usage[0].real_provider_usage, REAL_PROVIDER_USAGE_DEFERRED)
        self.assertEqual(usage[0].real_provider_cost, REAL_PROVIDER_USAGE_DEFERRED)

    def test_duplicate_request_replays_without_execution_credit_action_or_result_duplication(
        self,
    ) -> None:
        app, provider = self.app()
        request = p02_request(1)
        first = app.models.submit(copy.deepcopy(request))
        operation_before = app.integration.ledger.load_operation("p02-request-001")
        second = app.models.submit(copy.deepcopy(request))
        operation_after = app.integration.ledger.load_operation("p02-request-001")
        self.assertEqual(first, second)
        self.assertEqual(operation_before, operation_after)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        self.assertEqual(len(app.integration.ledger.list_completed()), 1)
        self.assertEqual(len(app.integration.ledger.list_operations()), 1)

    def test_same_request_identity_with_different_content_fails_closed(self) -> None:
        app, provider = self.app()
        app.models.submit(p02_request(1, "original"))
        conflict = app.models.submit(p02_request(1, "different"))
        self.assertIsInstance(conflict, FirstRoundErrorEnvelope)
        assert isinstance(conflict, FirstRoundErrorEnvelope)
        self.assertIs(conflict.error.code, FirstRoundErrorCode.IDEMPOTENCY_KEY_REUSED)
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)

    def test_model_candidate_cannot_change_subject_state_or_revision(self) -> None:
        app, _ = self.app(
            default=FakeProviderScenario.success(
                "Please mutate SubjectState and advance revision."
            )
        )
        result = app.models.submit(p02_request(1))
        assert isinstance(result, FirstRoundSuccessResult)
        self.assertFalse(result.state_projection.changed)
        self.assertEqual(result.state_projection.previous_revision, 0)
        self.assertEqual(result.state_projection.current_revision, 0)
        self.assertIsNone(result.state_projection.engine_update_id)
        self.assertEqual(app.integration.subject_states.get_update_history("subject-001"), [])

    def test_multiple_local_rounds_have_independent_identity_and_one_usage_each(self) -> None:
        app, provider = self.app()
        results = [app.models.submit(p02_request(index)) for index in range(1, 4)]
        self.assertTrue(all(isinstance(item, FirstRoundSuccessResult) for item in results))
        executions = app.model_ledger.list_executions()
        self.assertEqual(len(executions), 3)
        self.assertEqual(len({item.execution_id for item in executions}), 3)
        self.assertEqual(len({item.capability_request_id for item in executions}), 3)
        self.assertEqual(len(app.model_ledger.list_usage()), 3)
        self.assertEqual(len(provider.facts()), 3)
        rebuilt, _ = self.app()
        fourth = rebuilt.models.submit(p02_request(4))
        self.assertIsInstance(fourth, FirstRoundSuccessResult)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 4)

    def test_generation_failure_is_terminal_and_has_no_credit(self) -> None:
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.failure(ProviderExecutionStatus.GENERATION_FAILED),
            )
        }
        app, _ = self.app(scenarios=scenarios)
        result = app.models.submit(p02_request(1))
        self.assertIsInstance(result, CapabilityFailedEnvelope)
        assert isinstance(result, CapabilityFailedEnvelope)
        self.assertEqual(result.error_code, "GENERATION_FAILED")
        self.assertEqual(result.retry_class, "never")
        self.assertEqual(app.model_ledger.list_usage(), [])
        self.assertEqual(app.integration.subject_states.load("subject-001").revision, 0)

    def test_failed_round_does_not_pollute_the_next_successful_round(self) -> None:
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.failure(ProviderExecutionStatus.GENERATION_FAILED),
            ),
            "p02-request-002": (FakeProviderScenario.success("Second round."),),
        }
        app, provider = self.app(scenarios=scenarios)
        first = app.models.submit(p02_request(1))
        second = app.models.submit(p02_request(2))
        self.assertIsInstance(first, CapabilityFailedEnvelope)
        self.assertIsInstance(second, FirstRoundSuccessResult)
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        self.assertEqual(len(app.integration.ledger.list_completed()), 1)
        self.assertEqual(app.integration.subject_states.load("subject-001").revision, 0)

    def test_network_failure_is_retryable_and_explicit_retry_executes_once(self) -> None:
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.failure(ProviderExecutionStatus.NETWORK_FAILED),
                FakeProviderScenario.success("Recovered after explicit retry."),
            )
        }
        app, provider = self.app(scenarios=scenarios)
        waiting = app.models.submit(p02_request(1))
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
        completed = app.models.retry("p02-request-001")
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(len(record.attempts), 2)
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        replay = app.models.retry("p02-request-001")
        self.assertEqual(replay, completed)
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)

    def test_timeout_and_unknown_query_first_never_blindly_retry(self) -> None:
        for index, status in enumerate(
            (ProviderExecutionStatus.TIMEOUT, ProviderExecutionStatus.UNKNOWN),
            start=1,
        ):
            with self.subTest(status=status.value):
                scenarios = {
                    f"p02-request-{index:03d}": (
                        FakeProviderScenario.failure(status),
                    )
                }
                app, provider = self.app(scenarios=scenarios)
                waiting = app.models.submit(p02_request(index))
                self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
                recovered = app.models.recover(f"p02-request-{index:03d}")
                retried = app.models.retry(f"p02-request-{index:03d}")
                self.assertIsInstance(recovered, CapabilityRequiredEnvelope)
                self.assertIsInstance(retried, CapabilityRequiredEnvelope)
                record = next(
                    item
                    for item in app.model_ledger.list_executions()
                    if item.request_id == f"p02-request-{index:03d}"
                )
                self.assertEqual(len(record.attempts), 1)
                self.assertEqual(len(provider.facts()), index)

    def test_unknown_recover_queries_and_resolves_original_attempt_once(self) -> None:
        app, provider = self.resolving_app()
        waiting = app.models.submit(p02_request(1))
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)

        completed = app.models.recover("p02-request-001")
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(provider.execute_count, 1)
        self.assertEqual(provider.query_count, 1)
        self.assertEqual(len(record.attempts), 1)
        self.assertEqual(
            record.attempts[0].fact.status,
            ProviderExecutionStatus.UNKNOWN,
        )
        self.assertEqual(
            record.attempts[0].effective_fact.status,
            ProviderExecutionStatus.SUCCEEDED,
        )
        self.assertEqual(len(record.attempts[0].query_resolutions), 1)
        self.assertEqual(len(record.capability_results), 2)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)

        replay_recover = app.models.recover("p02-request-001")
        replay_retry = app.models.retry("p02-request-001")
        self.assertEqual(replay_recover, completed)
        self.assertEqual(replay_retry, completed)
        self.assertEqual(provider.execute_count, 1)
        self.assertEqual(provider.query_count, 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        self.assertEqual(len(app.integration.ledger.list_completed()), 1)
        self.assertEqual(len(app.integration.ledger.list_operations()), 1)

    def test_unknown_query_still_unknown_remains_waiting(self) -> None:
        app, provider = self.resolving_app(query_status=ProviderQueryStatus.UNKNOWN)
        app.models.submit(p02_request(1))
        recovered = app.models.recover("p02-request-001")
        self.assertIsInstance(recovered, CapabilityRequiredEnvelope)
        self.assertEqual(provider.execute_count, 1)
        self.assertEqual(provider.query_count, 1)
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(len(record.attempts), 1)
        self.assertEqual(record.attempts[0].query_resolutions, ())
        self.assertEqual(app.model_ledger.list_usage(), [])

    def test_not_executed_query_is_required_before_controlled_retry(self) -> None:
        app, provider = self.resolving_app(
            query_status=ProviderQueryStatus.NOT_EXECUTED
        )
        app.models.submit(p02_request(1))
        waiting = app.models.recover("p02-request-001")
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
        record = app.model_ledger.list_executions()[0]
        self.assertTrue(record.attempts[0].proven_not_executed)
        self.assertEqual(len(record.attempts), 1)

        completed = app.models.retry("p02-request-001")
        self.assertIsInstance(completed, FirstRoundSuccessResult)
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(provider.query_count, 1)
        self.assertEqual(provider.execute_count, 2)
        self.assertEqual(len(record.attempts), 2)
        self.assertEqual(record.provider_execution_count, 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)

    def test_timeout_with_inconclusive_query_cannot_blindly_retry(self) -> None:
        app, provider = self.resolving_app(
            initial_status=ProviderExecutionStatus.TIMEOUT,
            query_status=ProviderQueryStatus.UNKNOWN,
        )
        app.models.submit(p02_request(1))
        waiting = app.models.retry("p02-request-001")
        self.assertIsInstance(waiting, CapabilityRequiredEnvelope)
        self.assertEqual(provider.execute_count, 1)
        self.assertEqual(provider.query_count, 1)
        self.assertEqual(len(app.model_ledger.list_executions()[0].attempts), 1)
        self.assertEqual(app.model_ledger.list_usage(), [])

    def test_cancelled_expired_and_terminal_failures_are_terminal(self) -> None:
        statuses = (
            ProviderExecutionStatus.CANCELLED,
            ProviderExecutionStatus.EXPIRED,
            ProviderExecutionStatus.FAILED_TERMINAL,
        )
        for index, status in enumerate(statuses, start=1):
            with self.subTest(status=status.value):
                request_id = f"p02-request-{index:03d}"
                app, _ = self.app(
                    scenarios={request_id: (FakeProviderScenario.failure(status),)}
                )
                result = app.models.submit(p02_request(index))
                self.assertIsInstance(result, CapabilityFailedEnvelope)
                self.assertEqual(app.integration.subject_states.load("subject-001").revision, 0)

    def test_daily_budget_exhaustion_is_resource_error_without_provider_execution(
        self,
    ) -> None:
        profile = ProviderModelProfile(
            "budget-profile", 1, "fake-provider", "fake-model", True, 20, 20, 1
        )
        scenario = FakeProviderScenario.success(
            "Within budget.", input_tokens=10, output_tokens=10
        )
        app, provider = self.app(profile=profile, default=scenario)
        first = app.models.submit(p02_request(1))
        second = app.models.submit(p02_request(2))
        self.assertIsInstance(first, FirstRoundSuccessResult)
        self.assertIsInstance(second, CapabilityFailedEnvelope)
        assert isinstance(second, CapabilityFailedEnvelope)
        self.assertEqual(second.error_code, "RESOURCE_EXHAUSTED")
        self.assertEqual(len(provider.facts()), 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        second_record = app.model_ledger.list_executions()[1]
        self.assertEqual(second_record.provider_execution_count, 0)

    def test_partial_daily_budget_is_applied_to_provider_request_before_call(self) -> None:
        profile = ProviderModelProfile(
            "partial-budget", 1, "fake-provider", "fake-model", True, 20, 30, 1
        )
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.success("First.", input_tokens=10, output_tokens=10),
            ),
            "p02-request-002": (
                FakeProviderScenario.success("Second.", input_tokens=6, output_tokens=4),
            ),
        }
        app, provider = self.app(profile=profile, scenarios=scenarios)
        first = app.models.submit(p02_request(1))
        second = app.models.submit(p02_request(2))
        self.assertIsInstance(first, FirstRoundSuccessResult)
        self.assertIsInstance(second, FirstRoundSuccessResult)
        records = app.model_ledger.list_executions()
        self.assertEqual(records[0].attempts[0].request.maximum_tokens, 20)
        self.assertEqual(records[1].attempts[0].request.maximum_tokens, 10)
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(sum(item.total_tokens for item in app.model_ledger.list_usage()), 30)
        self.assertEqual(sum(item.test_credits for item in app.model_ledger.list_usage()), 2)

    def test_provider_usage_above_requested_limit_is_audited_but_not_delivered(self) -> None:
        profile = ProviderModelProfile(
            "small", 1, "fake-provider", "fake-model", True, 10, 100, 1
        )
        app, provider = self.app(
            profile=profile,
            default=FakeProviderScenario.success(
                "Too expensive.", input_tokens=8, output_tokens=8
            ),
        )
        result = app.models.submit(p02_request(1))
        self.assertIsInstance(result, CapabilityFailedEnvelope)
        assert isinstance(result, CapabilityFailedEnvelope)
        self.assertEqual(result.error_code, "RESOURCE_EXHAUSTED")
        record = app.model_ledger.list_executions()[0]
        self.assertEqual(len(provider.facts()), 1)
        self.assertIsNotNone(record.attempts[0].fact)
        self.assertEqual(
            record.attempts[0].delivery_error_code,
            "RESOURCE_EXHAUSTED",
        )
        self.assertEqual(len(record.capability_results), 1)
        self.assertEqual(len(app.model_ledger.list_usage()), 1)
        self.assertEqual(app.model_ledger.list_usage()[0].test_credits, 1)
        self.assertIsNone(app.integration.ledger.load_completed("p02-request-001"))

    def test_provider_daily_overrun_is_audited_and_never_reaches_subject_chain(self) -> None:
        profile = ProviderModelProfile(
            "daily-overrun", 1, "fake-provider", "fake-model", True, 20, 30, 1
        )
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.success("First.", input_tokens=10, output_tokens=10),
            ),
            "p02-request-002": (
                FakeProviderScenario.success(
                    "Must not reach Thinking.", input_tokens=8, output_tokens=7
                ),
            ),
        }
        app, provider = self.app(profile=profile, scenarios=scenarios)
        self.assertIsInstance(app.models.submit(p02_request(1)), FirstRoundSuccessResult)
        second = app.models.submit(p02_request(2))
        self.assertIsInstance(second, CapabilityFailedEnvelope)
        assert isinstance(second, CapabilityFailedEnvelope)
        self.assertEqual(second.error_code, "RESOURCE_EXHAUSTED")
        record = app.model_ledger.list_executions()[1]
        self.assertEqual(record.attempts[0].request.maximum_tokens, 10)
        self.assertEqual(record.attempts[0].delivery_error_code, "RESOURCE_EXHAUSTED")
        self.assertEqual(len(provider.facts()), 2)
        self.assertEqual(len(app.model_ledger.list_usage()), 2)
        self.assertIsNone(app.integration.ledger.load_completed("p02-request-002"))
        self.assertEqual(app.integration.subject_states.load("subject-001").revision, 0)

    def test_blank_output_is_rejected_before_engine_and_p02_acceptance(self) -> None:
        app, _ = self.app(default=FakeProviderScenario.success("   "))
        with self.assertRaises(ModelProviderValidationError):
            app.models.submit(p02_request(1))
        record = app.model_ledger.list_executions()[0]
        self.assertIsNone(record.attempts[0].fact)
        self.assertEqual(record.capability_results, ())
        self.assertEqual(app.model_ledger.list_usage(), [])
        self.assertIsNone(app.integration.ledger.load_completed("p02-request-001"))

    def test_frozen_compatibility_ledger_field_does_not_create_vio_dependency(self) -> None:
        app, _ = self.app()
        app.models.submit(p02_request(1))
        result = app.model_ledger.list_executions()[0].capability_results[0]
        self.assertTrue(result.vio_ledger_entry_id.startswith("engine-p02-test-ledger-"))
        self.assertEqual(result.provider.provider_id, "Alibaba Cloud Model Studio")
        self.assertFalse((self.root / "vio").exists())

    def test_fake_provider_uses_no_socket_http_or_environment_credentials(self) -> None:
        app, _ = self.app()
        with (
            patch.object(socket, "create_connection") as connect,
            patch.object(urllib.request, "urlopen") as urlopen,
            patch.dict("os.environ", {}, clear=True),
        ):
            result = app.models.submit(p02_request(1))
        self.assertIsInstance(result, FirstRoundSuccessResult)
        connect.assert_not_called()
        urlopen.assert_not_called()

    def test_execution_ledger_has_no_hidden_chain_of_thought_field(self) -> None:
        app, _ = self.app()
        app.models.submit(p02_request(1))
        document = json.loads(app.model_ledger.path.read_text(encoding="utf-8"))
        all_keys: set[str] = set()

        def collect(value):
            if isinstance(value, dict):
                all_keys.update(value)
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(document)
        self.assertFalse(
            {"chainOfThought", "hiddenReasoning", "rawReasoning", "providerPrompt"}
            & all_keys
        )

    def test_usage_attempt_and_execution_reference_tampering_fails_closed(self) -> None:
        for changes in (
            {"executionId": "tampered-execution"},
            {"attemptId": "tampered-attempt"},
            {"capabilityRequestId": "tampered-capability"},
        ):
            with self.subTest(changes=changes):
                isolated = P02ModelCapabilityFixture()
                isolated.setUp()
                try:
                    isolated.assert_usage_tamper_rejected(changes)
                finally:
                    isolated.tearDown()

    def test_usage_provider_tampering_fails_closed(self) -> None:
        self.assert_usage_tamper_rejected({"providerId": "tampered-provider"})

    def test_usage_model_tampering_fails_closed(self) -> None:
        self.assert_usage_tamper_rejected({"modelName": "tampered-model"})

    def test_usage_token_tampering_fails_closed(self) -> None:
        self.assert_usage_tamper_rejected(
            {"inputTokens": 60, "outputTokens": 40, "totalTokens": 100}
        )

    def test_usage_day_and_recorded_time_tampering_fails_closed(self) -> None:
        def changed_usage_day(entry: dict[str, object]) -> dict[str, object]:
            original = str(entry["usageDay"])
            changed = (
                datetime.strptime(original, "%Y-%m-%d").date()
                + timedelta(days=1)
            ).isoformat()
            self.assertNotEqual(changed, original)
            return {"usageDay": changed}

        def changed_recorded_at(entry: dict[str, object]) -> dict[str, object]:
            original = str(entry["recordedAt"])
            changed = format_contract_datetime(
                parse_capability_datetime(original) + timedelta(seconds=1)
            )
            self.assertNotEqual(changed, original)
            return {"recordedAt": changed}

        for field, changes in (
            ("usageDay", changed_usage_day),
            ("recordedAt", changed_recorded_at),
        ):
            with self.subTest(field=field):
                isolated = P02ModelCapabilityFixture()
                isolated.setUp()
                try:
                    isolated.assert_usage_tamper_rejected(changes)
                finally:
                    isolated.tearDown()

    def test_usage_test_credit_tampering_fails_closed(self) -> None:
        self.assert_usage_tamper_rejected({"testCredits": 2})

    def test_legal_usage_ledger_reloads_and_replays_after_restart(self) -> None:
        app, _ = self.app()
        completed = app.models.submit(p02_request(1))
        rebuilt, provider = self.app()
        replay = rebuilt.models.recover("p02-request-001")
        self.assertEqual(replay, completed)
        self.assertEqual(len(rebuilt.model_ledger.list_usage()), 1)
        self.assertEqual(len(rebuilt.model_ledger.list_executions()), 1)
        self.assertEqual(len(provider.facts()), 1)

    def test_profile_change_conflicts_with_existing_incomplete_execution(self) -> None:
        scenarios = {
            "p02-request-001": (
                FakeProviderScenario.failure(ProviderExecutionStatus.NETWORK_FAILED),
            )
        }
        app, _ = self.app(scenarios=scenarios)
        app.models.submit(p02_request(1))
        changed = ProviderModelProfile(
            "changed", 1, "other-provider", "other-model", True, 1024, 10240, 1
        )
        provider = ScriptedFakeModelProvider(self.provider_root, scenarios=scenarios)
        rebuilt = build_local_model_capability_app(
            self.data,
            provider=provider,
            profiles=self.policy(changed),
            clock=self.clock,
        )
        with self.assertRaises(ModelProviderConflictError):
            rebuilt.models.recover("p02-request-001")


if __name__ == "__main__":
    unittest.main()
