from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from continuity_engine.domain.errors import ModelProviderConflictError
from continuity_engine.domain.model_provider import (
    ModelExecutionRequest,
    ProviderExecutionFact,
    ProviderExecutionStatus,
    ProviderQueryResult,
    ProviderQueryStatus,
)
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.storage.json_integration_repository import (
    _atomic_write_json,
    _read_json,
    _strict_document,
)


@dataclass(frozen=True, slots=True)
class FakeProviderScenario:
    status: ProviderExecutionStatus
    response_candidate: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str | None = None
    error_code: str | None = None
    retry_class: str | None = None
    execution_occurred: bool = True

    @classmethod
    def success(
        cls,
        response_candidate: str = "A bounded synthetic model response.",
        *,
        input_tokens: int = 24,
        output_tokens: int = 12,
    ) -> FakeProviderScenario:
        return cls(
            status=ProviderExecutionStatus.SUCCEEDED,
            response_candidate=response_candidate,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason="stop",
        )

    @classmethod
    def failure(
        cls,
        status: ProviderExecutionStatus,
    ) -> FakeProviderScenario:
        mapping = {
            ProviderExecutionStatus.GENERATION_FAILED: (
                "GENERATION_FAILED",
                "never",
                True,
            ),
            ProviderExecutionStatus.NETWORK_FAILED: (
                "NETWORK_FAILED",
                "retry",
                False,
            ),
            ProviderExecutionStatus.TIMEOUT: ("TIMEOUT", "query", True),
            ProviderExecutionStatus.UNKNOWN: ("UNKNOWN", "query", True),
            ProviderExecutionStatus.FAILED_RETRYABLE: (
                "PROVIDER_RETRYABLE",
                "retry",
                False,
            ),
            ProviderExecutionStatus.FAILED_TERMINAL: (
                "PROVIDER_TERMINAL",
                "never",
                True,
            ),
            ProviderExecutionStatus.CANCELLED: ("CANCELLED", "never", False),
            ProviderExecutionStatus.EXPIRED: ("EXPIRED", "never", False),
        }
        error_code, retry_class, occurred = mapping[status]
        return cls(
            status=status,
            error_code=error_code,
            retry_class=retry_class,
            execution_occurred=occurred,
        )


class ScriptedFakeModelProvider:
    """Deterministic, local-only Provider fixture with queryable execution facts."""

    _FORMAT_VERSION = 1

    def __init__(
        self,
        root: str | Path,
        *,
        scenarios: dict[str, tuple[FakeProviderScenario, ...]] | None = None,
        default_scenario: FakeProviderScenario | None = None,
    ) -> None:
        self._path = Path(root) / "fake-provider-state.p02-v1.json"
        self._scenarios = scenarios or {}
        self._default = default_scenario or FakeProviderScenario.success()
        if self._path.exists():
            self._load()
        else:
            self._write([])

    @property
    def state_path(self) -> Path:
        return self._path

    def execute(self, request: ModelExecutionRequest) -> ProviderExecutionFact:
        facts = self._load()
        existing = next(
            (item for item in facts if item.attempt_id == request.attempt_id),
            None,
        )
        if existing is not None:
            if (
                existing.execution_id != request.execution_id
                or existing.request_fingerprint != request.request_fingerprint
            ):
                raise ModelProviderConflictError(
                    "Fake Provider attempt identity was reused with different input"
                )
            return existing
        ordinal = self._attempt_ordinal(request.attempt_id)
        scripted = self._scenarios.get(request.request_id, ())
        scenario = scripted[ordinal - 1] if ordinal <= len(scripted) else self._default
        started = parse_capability_datetime(request.created_at) + timedelta(
            seconds=ordinal
        )
        fact = ProviderExecutionFact(
            execution_id=request.execution_id,
            attempt_id=request.attempt_id,
            request_fingerprint=request.request_fingerprint,
            provider_id=request.profile.provider_id,
            model_name=request.profile.model_name,
            status=scenario.status,
            response_candidate=scenario.response_candidate,
            input_tokens=scenario.input_tokens,
            output_tokens=scenario.output_tokens,
            finish_reason=scenario.finish_reason,
            error_code=scenario.error_code,
            retry_class=scenario.retry_class,
            started_at=format_contract_datetime(started),
            completed_at=format_contract_datetime(started + timedelta(seconds=1)),
            execution_occurred=scenario.execution_occurred,
        )
        facts.append(fact)
        self._write(facts)
        return fact

    def query(self, request: ModelExecutionRequest) -> ProviderQueryResult:
        fact = next(
            (
                item
                for item in self._load()
                if item.attempt_id == request.attempt_id
            ),
            None,
        )
        if fact is None:
            return ProviderQueryResult(ProviderQueryStatus.NOT_EXECUTED)
        if (
            fact.execution_id != request.execution_id
            or fact.request_fingerprint != request.request_fingerprint
        ):
            raise ModelProviderConflictError(
                "Fake Provider query identity conflicts with persisted fact"
            )
        return ProviderQueryResult(ProviderQueryStatus.FOUND, fact)

    def facts(self) -> list[ProviderExecutionFact]:
        return list(self._load())

    @staticmethod
    def _attempt_ordinal(attempt_id: str) -> int:
        try:
            ordinal = int(attempt_id.rsplit("-", 1)[1])
        except (IndexError, ValueError) as exc:
            raise ModelProviderConflictError(
                "Fake Provider attempt id must end with its ordinal"
            ) from exc
        if ordinal < 1:
            raise ModelProviderConflictError("Fake Provider attempt ordinal is invalid")
        return ordinal

    def _load(self) -> list[ProviderExecutionFact]:
        raw = _read_json(self._path, name="P02 Fake Provider state")
        document = _strict_document(
            raw,
            name="P02 Fake Provider state document",
            expected_keys={"formatVersion", "facts"},
        )
        if document["formatVersion"] != self._FORMAT_VERSION or not isinstance(
            document["facts"], list
        ):
            raise ModelProviderConflictError("P02 Fake Provider state is invalid")
        facts = [ProviderExecutionFact.from_dict(item) for item in document["facts"]]
        if len({item.attempt_id for item in facts}) != len(facts):
            raise ModelProviderConflictError(
                "P02 Fake Provider contains duplicate attempt ids"
            )
        return facts

    def _write(self, facts: list[ProviderExecutionFact]) -> None:
        _atomic_write_json(
            self._path,
            {
                "formatVersion": self._FORMAT_VERSION,
                "facts": [item.to_dict() for item in facts],
            },
            name="P02 Fake Provider state",
        )
