from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from continuity_engine.domain.errors import MachineContractValidationError
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import HASH_PATTERN


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MachineContractValidationError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class SubjectBinding:
    """The persisted runtime binding between one Vio assistant and one subject."""

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
    cycle_id: str
    binding_fixture_hash: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.schema_version, "schemaVersion"),
            (self.binding_id, "bindingId"),
            (self.user_id, "userId"),
            (self.assistant_id, "assistantId"),
            (self.subject_id, "subjectId"),
            (self.created_at, "createdAt"),
            (self.effective_at, "effectiveAt"),
            (self.cycle_id, "cycleId"),
        ):
            _required_text(value, name)
        if self.binding_version != 1 or isinstance(self.binding_version, bool):
            raise MachineContractValidationError("bindingVersion must be 1")
        if self.status != "active":
            raise MachineContractValidationError("status must be active")
        if self.replaced_binding_id is not None:
            raise MachineContractValidationError(
                "the first runtime binding cannot replace another binding"
            )
        if not self.created_at.endswith("Z") or not self.effective_at.endswith("Z"):
            raise MachineContractValidationError(
                "binding timestamps must use RFC 3339 UTC with uppercase Z"
            )
        if HASH_PATTERN.fullmatch(self.binding_fixture_hash) is None:
            raise MachineContractValidationError(
                "bindingFixtureHash must use sha256: followed by 64 lowercase hexadecimal digits"
            )

    @classmethod
    def from_fixture(
        cls,
        fixture: SubjectBindingFixture,
        *,
        cycle_id: str,
        binding_fixture_hash: str,
    ) -> SubjectBinding:
        if not isinstance(fixture, SubjectBindingFixture):
            raise MachineContractValidationError("fixture must be a SubjectBindingFixture")
        return cls(
            schema_version=fixture.schema_version,
            binding_id=fixture.binding_id,
            user_id=fixture.user_id,
            assistant_id=fixture.assistant_id,
            subject_id=fixture.subject_id,
            binding_version=fixture.binding_version,
            status=fixture.status,
            created_at=fixture.created_at,
            effective_at=fixture.effective_at,
            replaced_binding_id=fixture.replaced_binding_id,
            cycle_id=cycle_id,
            binding_fixture_hash=binding_fixture_hash,
        )

    def to_fixture(self) -> SubjectBindingFixture:
        return SubjectBindingFixture(
            schema_version=self.schema_version,
            binding_id=self.binding_id,
            user_id=self.user_id,
            assistant_id=self.assistant_id,
            subject_id=self.subject_id,
            binding_version=self.binding_version,
            status=self.status,
            created_at=self.created_at,
            effective_at=self.effective_at,
            replaced_binding_id=self.replaced_binding_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_fixture().to_dict(),
            "cycleId": self.cycle_id,
            "bindingFixtureHash": self.binding_fixture_hash,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SubjectBinding:
        expected = {
            "schemaVersion",
            "bindingId",
            "userId",
            "assistantId",
            "subjectId",
            "bindingVersion",
            "status",
            "createdAt",
            "effectiveAt",
            "replacedBindingId",
            "cycleId",
            "bindingFixtureHash",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise MachineContractValidationError(
                "persisted SubjectBinding has an invalid shape"
            )
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
            cycle_id=value["cycleId"],
            binding_fixture_hash=value["bindingFixtureHash"],
        )
