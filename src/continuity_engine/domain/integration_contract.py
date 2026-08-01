from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import JsonValue


@dataclass(frozen=True, slots=True)
class Identity:
    user_id: str
    assistant_id: str
    subject_id: str
    binding_id: str
    binding_version: int

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "userId": self.user_id,
            "assistantId": self.assistant_id,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "bindingVersion": self.binding_version,
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> Identity:
        return cls(
            user_id=value["userId"],
            assistant_id=value["assistantId"],
            subject_id=value["subjectId"],
            binding_id=value["bindingId"],
            binding_version=value["bindingVersion"],
        )


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: str
    message_id: str
    message_version_id: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "conversationId": self.conversation_id,
            "messageId": self.message_id,
            "messageVersionId": self.message_version_id,
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> Conversation:
        return cls(
            conversation_id=value["conversationId"],
            message_id=value["messageId"],
            message_version_id=value["messageVersionId"],
        )


@dataclass(frozen=True, slots=True)
class MessageVersionFact:
    schema_version: str
    fact_id: str
    fact_type: str
    identity: Identity
    conversation_id: str
    message_id: str
    message_version_id: str
    sender_type: str
    content: str
    content_hash: str
    created_at: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "factId": self.fact_id,
            "factType": self.fact_type,
            "identity": self.identity.to_dict(),
            "conversationId": self.conversation_id,
            "messageId": self.message_id,
            "messageVersionId": self.message_version_id,
            "senderType": self.sender_type,
            "content": self.content,
            "contentHash": self.content_hash,
            "createdAt": self.created_at,
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> MessageVersionFact:
        return cls(
            schema_version=value["schemaVersion"],
            fact_id=value["factId"],
            fact_type=value["factType"],
            identity=Identity._from_validated_dict(value["identity"]),
            conversation_id=value["conversationId"],
            message_id=value["messageId"],
            message_version_id=value["messageVersionId"],
            sender_type=value["senderType"],
            content=value["content"],
            content_hash=value["contentHash"],
            created_at=value["createdAt"],
        )


@dataclass(frozen=True, slots=True)
class PlatformFactPackage:
    schema_version: str
    facts: tuple[MessageVersionFact, ...]
    observation_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "facts": [item.to_dict() for item in self.facts],
            "observationRefs": list(self.observation_refs),
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> PlatformFactPackage:
        return cls(
            schema_version=value["schemaVersion"],
            facts=tuple(
                MessageVersionFact._from_validated_dict(item)
                for item in value["facts"]
            ),
            observation_refs=tuple(value["observationRefs"]),
        )


@dataclass(frozen=True, slots=True)
class PlatformObservation:
    schema_version: str
    observation_id: str
    source_event_id: str
    observation_type: str
    identity: Identity
    occurred_at: str
    observed_at: str
    message_version_ref: Conversation

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "observationId": self.observation_id,
            "sourceEventId": self.source_event_id,
            "observationType": self.observation_type,
            "identity": self.identity.to_dict(),
            "occurredAt": self.occurred_at,
            "observedAt": self.observed_at,
            "messageVersionRef": self.message_version_ref.to_dict(),
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> PlatformObservation:
        return cls(
            schema_version=value["schemaVersion"],
            observation_id=value["observationId"],
            source_event_id=value["sourceEventId"],
            observation_type=value["observationType"],
            identity=Identity._from_validated_dict(value["identity"]),
            occurred_at=value["occurredAt"],
            observed_at=value["observedAt"],
            message_version_ref=Conversation._from_validated_dict(
                value["messageVersionRef"]
            ),
        )


@dataclass(frozen=True, slots=True)
class Constraints:
    purpose: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {"purpose": self.purpose}

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> Constraints:
        return cls(purpose=value["purpose"])


@dataclass(frozen=True, slots=True)
class ContinuityInteractionRequest:
    contract_version: str
    schema_version: str
    request_id: str
    request_hash: str
    request_type: str
    identity: Identity
    conversation: Conversation
    expected_engine_revision: int
    platform_fact_package: PlatformFactPackage
    observations: tuple[PlatformObservation, ...]
    constraints: Constraints
    created_at: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "contractVersion": self.contract_version,
            "schemaVersion": self.schema_version,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "requestType": self.request_type,
            "identity": self.identity.to_dict(),
            "conversation": self.conversation.to_dict(),
            "expectedEngineRevision": self.expected_engine_revision,
            "platformFactPackage": self.platform_fact_package.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "constraints": self.constraints.to_dict(),
            "createdAt": self.created_at,
        }

    @classmethod
    def _from_validated_dict(
        cls,
        value: dict[str, Any],
    ) -> ContinuityInteractionRequest:
        return cls(
            contract_version=value["contractVersion"],
            schema_version=value["schemaVersion"],
            request_id=value["requestId"],
            request_hash=value["requestHash"],
            request_type=value["requestType"],
            identity=Identity._from_validated_dict(value["identity"]),
            conversation=Conversation._from_validated_dict(value["conversation"]),
            expected_engine_revision=value["expectedEngineRevision"],
            platform_fact_package=PlatformFactPackage._from_validated_dict(
                value["platformFactPackage"]
            ),
            observations=tuple(
                PlatformObservation._from_validated_dict(item)
                for item in value["observations"]
            ),
            constraints=Constraints._from_validated_dict(value["constraints"]),
            created_at=value["createdAt"],
        )


@dataclass(frozen=True, slots=True)
class SubjectBindingFixture:
    schema_version: str
    binding_id: str
    user_id: str
    assistant_id: str
    subject_id: str
    binding_version: int
    status: str
    created_at: str
    effective_at: str
    replaced_binding_id: str | None

    @classmethod
    def first_round(cls) -> SubjectBindingFixture:
        return cls(
            schema_version="subject-binding/first-round-v1",
            binding_id="binding-001",
            user_id="user-001",
            assistant_id="assistant-001",
            subject_id="subject-001",
            binding_version=1,
            status="active",
            created_at="2026-07-30T00:00:00Z",
            effective_at="2026-07-30T00:00:00Z",
            replaced_binding_id=None,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schemaVersion": self.schema_version,
            "bindingId": self.binding_id,
            "userId": self.user_id,
            "assistantId": self.assistant_id,
            "subjectId": self.subject_id,
            "bindingVersion": self.binding_version,
            "status": self.status,
            "createdAt": self.created_at,
            "effectiveAt": self.effective_at,
            "replacedBindingId": self.replaced_binding_id,
        }

    @classmethod
    def _from_validated_dict(cls, value: dict[str, Any]) -> SubjectBindingFixture:
        return cls(
            schema_version=value["schemaVersion"],
            binding_id=value["bindingId"],
            user_id=value["userId"],
            assistant_id=value["assistantId"],
            subject_id=value["subjectId"],
            binding_version=value["bindingVersion"],
            status=value["status"],
            created_at=value["createdAt"],
            effective_at=value["effectiveAt"],
            replaced_binding_id=value["replacedBindingId"],
        )
