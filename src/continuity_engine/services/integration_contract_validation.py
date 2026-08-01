from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from continuity_engine.domain.errors import MachineContractValidationError
from continuity_engine.domain.integration_contract import (
    ContinuityInteractionRequest,
    SubjectBindingFixture,
)
from continuity_engine.interfaces.integration_contract_schema import (
    DEFAULT_SCHEMA_REGISTRY,
    REQUEST_SCHEMA_ID,
    LocalSchemaRegistry,
)

from .integration_contract_hashing import (
    calculate_binding_fixture_hash,
    calculate_content_hash,
    calculate_request_hash,
    verify_declared_hash,
)


_FORBIDDEN_STATE_WRITE_FIELDS = frozenset(
    {
        "mutation",
        "statemutation",
        "impactscope",
        "fieldpath",
        "operation",
        "statepatch",
        "statesnapshot",
        "subjectstate",
        "subjectstateoverride",
        "subjectstatepatch",
        "subjectstatesnapshot",
    }
)


def _normalized_field_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _reject_state_write_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                normalized = _normalized_field_name(key)
                if normalized in _FORBIDDEN_STATE_WRITE_FIELDS:
                    raise MachineContractValidationError(
                        f"state-write field is forbidden at {path}.{key}"
                    )
                child_path = f"{path}.{key}"
            else:
                child_path = f"{path}[{key!r}]"
            _reject_state_write_fields(item, path=child_path)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _reject_state_write_fields(item, path=f"{path}[{index}]")


def _require_equal(*, name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise MachineContractValidationError(f"{name} does not match")


class MachineContractValidator:
    """Strict E1 validator for untrusted first-round contract documents."""

    def __init__(
        self,
        schema_registry: LocalSchemaRegistry = DEFAULT_SCHEMA_REGISTRY,
    ) -> None:
        self._schema_registry = schema_registry

    @property
    def schema_registry(self) -> LocalSchemaRegistry:
        return self._schema_registry

    def validate_request(self, payload: Any) -> ContinuityInteractionRequest:
        _reject_state_write_fields(payload)
        self._schema_registry.validate(REQUEST_SCHEMA_ID, payload)

        request_identity = payload["identity"]
        request_conversation = payload["conversation"]
        observation = payload["observations"][0]
        fact_package = payload["platformFactPackage"]
        fact = fact_package["facts"][0]

        _require_equal(
            name="Observation identity",
            actual=observation["identity"],
            expected=request_identity,
        )
        _require_equal(
            name="fact identity",
            actual=fact["identity"],
            expected=request_identity,
        )
        _require_equal(
            name="Observation messageVersionRef",
            actual=observation["messageVersionRef"],
            expected=request_conversation,
        )
        _require_equal(
            name="fact conversation reference",
            actual={
                "conversationId": fact["conversationId"],
                "messageId": fact["messageId"],
                "messageVersionId": fact["messageVersionId"],
            },
            expected=request_conversation,
        )
        _require_equal(
            name="observationRefs",
            actual=fact_package["observationRefs"],
            expected=[observation["observationId"]],
        )

        verify_declared_hash(
            declared=fact["contentHash"],
            calculated=calculate_content_hash(fact["content"]),
            field_name="contentHash",
        )
        verify_declared_hash(
            declared=payload["requestHash"],
            calculated=calculate_request_hash(payload),
            field_name="requestHash",
        )

        return ContinuityInteractionRequest._from_validated_dict(payload)

    def fixed_subject_binding(self) -> SubjectBindingFixture:
        return SubjectBindingFixture.first_round()

    def validate_fixed_subject_binding(
        self,
        payload: Any,
        *,
        binding_fixture_hash: str,
    ) -> SubjectBindingFixture:
        _reject_state_write_fields(payload)
        if not isinstance(payload, dict):
            raise MachineContractValidationError(
                "SubjectBinding fixture must be an object"
            )

        expected = SubjectBindingFixture.first_round().to_dict()
        if payload != expected:
            raise MachineContractValidationError(
                "SubjectBinding fixture does not match the fixed first-round fixture"
            )

        verify_declared_hash(
            declared=binding_fixture_hash,
            calculated=calculate_binding_fixture_hash(payload),
            field_name="bindingFixtureHash",
        )
        return SubjectBindingFixture._from_validated_dict(payload)
