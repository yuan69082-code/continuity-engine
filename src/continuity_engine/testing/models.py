from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def format_utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field_name} must use RFC 3339 UTC with uppercase Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid datetime") from exc
    return parsed


def require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


class SandboxEnvironment(str, Enum):
    TEST = "TEST"


class RetentionMode(str, Enum):
    SUCCESS_AUTO_CLEAN = "SUCCESS_AUTO_CLEAN"
    FAILURE_24_HOURS = "FAILURE_24_HOURS"
    DEBUG = "DEBUG"


class SandboxLifecycle(str, Enum):
    ACTIVE = "ACTIVE"
    RETAINED = "RETAINED"
    CLEANED = "CLEANED"


class SandboxOperationError(RuntimeError):
    """Expected fail-closed P01 error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = require_text(code, "code")
        self.message = require_text(message, "message")


@dataclass(frozen=True, slots=True)
class StateFixture:
    fixture_id: str
    personality_traits: tuple[str, ...]
    expression_preferences: tuple[str, ...]
    relationship_status: str
    relationship_moments: tuple[str, ...]
    continuity_focus: tuple[str, ...]
    memories: tuple[str, ...]
    synthetic: bool = True
    environment: SandboxEnvironment = SandboxEnvironment.TEST

    def __post_init__(self) -> None:
        require_text(self.fixture_id, "fixture_id")
        for field_name, values in (
            ("personality_traits", self.personality_traits),
            ("expression_preferences", self.expression_preferences),
            ("relationship_moments", self.relationship_moments),
            ("continuity_focus", self.continuity_focus),
            ("memories", self.memories),
        ):
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{field_name} must contain non-empty strings")
        require_text(self.relationship_status, "relationship_status")
        if self.synthetic is not True or self.environment is not SandboxEnvironment.TEST:
            raise ValueError("a P01 State Fixture must be synthetic TEST data")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "fixtureId": self.fixture_id,
            "personalityTraits": list(self.personality_traits),
            "expressionPreferences": list(self.expression_preferences),
            "relationshipStatus": self.relationship_status,
            "relationshipMoments": list(self.relationship_moments),
            "continuityFocus": list(self.continuity_focus),
            "memories": list(self.memories),
            "synthetic": self.synthetic,
            "environment": self.environment.value,
        }


@dataclass(slots=True)
class SandboxDescriptor:
    sandbox_id: str
    environment: SandboxEnvironment
    subject_id: str
    binding_id: str
    cycle_id: str
    namespace_id: str
    data_root: str
    created_at: datetime
    expires_at: datetime | None
    retention_mode: RetentionMode
    synthetic: bool
    promotion_allowed: bool
    lifecycle: SandboxLifecycle
    active_branch_id: str
    branch_ids: list[str] = field(default_factory=list)
    snapshot_ids: list[str] = field(default_factory=list)
    snapshot_anchors: dict[str, str] = field(default_factory=dict)
    acceptance_receipt_ids: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for value, name in (
            (self.sandbox_id, "sandbox_id"),
            (self.subject_id, "subject_id"),
            (self.binding_id, "binding_id"),
            (self.cycle_id, "cycle_id"),
            (self.namespace_id, "namespace_id"),
            (self.data_root, "data_root"),
            (self.active_branch_id, "active_branch_id"),
        ):
            require_text(value, name)
        if self.environment is not SandboxEnvironment.TEST:
            raise ValueError("P01 sandboxes must use the TEST environment")
        if self.synthetic is not True or self.promotion_allowed is not False:
            raise ValueError("P01 sandboxes must be synthetic and non-promotable")
        if self.created_at.tzinfo is None or (
            self.expires_at is not None and self.expires_at.tzinfo is None
        ):
            raise ValueError("sandbox timestamps must be timezone-aware")
        if self.active_branch_id not in self.branch_ids:
            raise ValueError("active branch must be registered")
        if set(self.snapshot_ids) != set(self.snapshot_anchors):
            raise ValueError("every registered snapshot must have one external anchor")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "sandboxId": self.sandbox_id,
            "environment": self.environment.value,
            "subjectId": self.subject_id,
            "bindingId": self.binding_id,
            "cycleId": self.cycle_id,
            "namespaceId": self.namespace_id,
            "dataRoot": self.data_root,
            "createdAt": format_utc(self.created_at),
            "expiresAt": format_utc(self.expires_at) if self.expires_at else None,
            "retentionMode": self.retention_mode.value,
            "synthetic": self.synthetic,
            "promotionAllowed": self.promotion_allowed,
            "lifecycle": self.lifecycle.value,
            "activeBranchId": self.active_branch_id,
            "branchIds": list(self.branch_ids),
            "snapshotIds": list(self.snapshot_ids),
            "snapshotAnchors": dict(sorted(self.snapshot_anchors.items())),
            "acceptanceReceiptIds": list(self.acceptance_receipt_ids),
            "protectedPaths": list(self.protected_paths),
        }

    @classmethod
    def from_dict(cls, value: Any) -> SandboxDescriptor:
        if not isinstance(value, dict):
            raise ValueError("sandbox descriptor must be an object")
        return cls(
            sandbox_id=value.get("sandboxId"),
            environment=SandboxEnvironment(value.get("environment")),
            subject_id=value.get("subjectId"),
            binding_id=value.get("bindingId"),
            cycle_id=value.get("cycleId"),
            namespace_id=value.get("namespaceId"),
            data_root=value.get("dataRoot"),
            created_at=parse_utc(value.get("createdAt"), "createdAt"),
            expires_at=(
                parse_utc(value.get("expiresAt"), "expiresAt")
                if value.get("expiresAt") is not None
                else None
            ),
            retention_mode=RetentionMode(value.get("retentionMode")),
            synthetic=value.get("synthetic"),
            promotion_allowed=value.get("promotionAllowed"),
            lifecycle=SandboxLifecycle(value.get("lifecycle")),
            active_branch_id=value.get("activeBranchId"),
            branch_ids=list(value.get("branchIds", [])),
            snapshot_ids=list(value.get("snapshotIds", [])),
            snapshot_anchors=dict(value.get("snapshotAnchors", {})),
            acceptance_receipt_ids=list(value.get("acceptanceReceiptIds", [])),
            protected_paths=list(value.get("protectedPaths", [])),
        )


@dataclass(frozen=True, slots=True)
class SnapshotFileInventoryEntry:
    relative_path: str
    file_hash: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "relativePath": self.relative_path,
            "fileHash": self.file_hash,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SnapshotFileInventoryEntry:
        if not isinstance(value, dict):
            raise ValueError("snapshot inventory entry must be an object")
        return cls(
            relative_path=require_text(value.get("relativePath"), "relativePath"),
            file_hash=require_text(value.get("fileHash"), "fileHash"),
        )


@dataclass(frozen=True, slots=True)
class SnapshotComponent:
    name: str
    physical_path: str
    canonical_content_hash: str
    file_hash: str
    revision: int | None
    count: int
    snapshot_id: str
    source_branch: str
    created_at: datetime
    complete: bool = True

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "physicalPath": self.physical_path,
            "canonicalContentHash": self.canonical_content_hash,
            "fileHash": self.file_hash,
            "revision": self.revision,
            "count": self.count,
            "snapshotId": self.snapshot_id,
            "sourceBranch": self.source_branch,
            "createdAt": format_utc(self.created_at),
            "complete": self.complete,
        }

    @classmethod
    def from_dict(cls, value: Any) -> SnapshotComponent:
        if not isinstance(value, dict):
            raise ValueError("snapshot component must be an object")
        return cls(
            name=value["name"],
            physical_path=value["physicalPath"],
            canonical_content_hash=value["canonicalContentHash"],
            file_hash=value["fileHash"],
            revision=value.get("revision"),
            count=value["count"],
            snapshot_id=value["snapshotId"],
            source_branch=value["sourceBranch"],
            created_at=parse_utc(value["createdAt"], "component.createdAt"),
            complete=value["complete"],
        )


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    manifest_version: int
    snapshot_id: str
    sandbox_id: str
    subject_id: str
    namespace_id: str
    environment: SandboxEnvironment
    promotion_allowed: bool
    source_branch: str
    source_revision: int
    created_at: datetime
    components: tuple[SnapshotComponent, ...]
    physical_inventory: tuple[SnapshotFileInventoryEntry, ...]
    complete: bool
    manifest_hash: str

    def unsigned_dict(self) -> dict[str, JsonValue]:
        return {
            "manifestVersion": self.manifest_version,
            "snapshotId": self.snapshot_id,
            "sandboxId": self.sandbox_id,
            "subjectId": self.subject_id,
            "namespaceId": self.namespace_id,
            "environment": self.environment.value,
            "promotionAllowed": self.promotion_allowed,
            "sourceBranch": self.source_branch,
            "sourceRevision": self.source_revision,
            "createdAt": format_utc(self.created_at),
            "components": [component.to_dict() for component in self.components],
            "physicalInventory": [item.to_dict() for item in self.physical_inventory],
            "complete": self.complete,
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.unsigned_dict(), "manifestHash": self.manifest_hash}

    @classmethod
    def from_dict(cls, value: Any) -> SnapshotManifest:
        if not isinstance(value, dict):
            raise ValueError("snapshot manifest must be an object")
        return cls(
            manifest_version=value["manifestVersion"],
            snapshot_id=value["snapshotId"],
            sandbox_id=value["sandboxId"],
            subject_id=value["subjectId"],
            namespace_id=value["namespaceId"],
            environment=SandboxEnvironment(value["environment"]),
            promotion_allowed=value["promotionAllowed"],
            source_branch=value["sourceBranch"],
            source_revision=value["sourceRevision"],
            created_at=parse_utc(value["createdAt"], "manifest.createdAt"),
            components=tuple(
                SnapshotComponent.from_dict(item) for item in value["components"]
            ),
            physical_inventory=tuple(
                SnapshotFileInventoryEntry.from_dict(item)
                for item in value["physicalInventory"]
            ),
            complete=value["complete"],
            manifest_hash=value["manifestHash"],
        )


@dataclass(frozen=True, slots=True)
class SandboxInteractionProof:
    proof_id: str
    sandbox_id: str
    snapshot_id: str
    request_id: str
    request_hash: str
    operation_id: str
    response_id: str
    result_hash: str
    changed: bool
    previous_revision: int
    current_revision: int
    engine_update_id: str | None
    wake_session_ids: tuple[str, ...]
    think_session_ids: tuple[str, ...]
    action_session_ids: tuple[str, ...]
    standard_call_log: tuple[str, ...]
    snapshot_fingerprint: dict[str, Any]
    changed_fingerprint: dict[str, Any]
    created_at: datetime
    proof_hash: str

    def unsigned_dict(self) -> dict[str, JsonValue]:
        return {
            "proofId": self.proof_id,
            "sandboxId": self.sandbox_id,
            "snapshotId": self.snapshot_id,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "responseId": self.response_id,
            "resultHash": self.result_hash,
            "changed": self.changed,
            "previousRevision": self.previous_revision,
            "currentRevision": self.current_revision,
            "engineUpdateId": self.engine_update_id,
            "wakeSessionIds": list(self.wake_session_ids),
            "thinkSessionIds": list(self.think_session_ids),
            "actionSessionIds": list(self.action_session_ids),
            "standardCallLog": list(self.standard_call_log),
            "snapshotFingerprint": self.snapshot_fingerprint,
            "changedFingerprint": self.changed_fingerprint,
            "createdAt": format_utc(self.created_at),
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.unsigned_dict(), "proofHash": self.proof_hash}

    @classmethod
    def from_dict(cls, value: Any) -> SandboxInteractionProof:
        if not isinstance(value, dict):
            raise ValueError("interaction proof must be an object")
        return cls(
            proof_id=value["proofId"],
            sandbox_id=value["sandboxId"],
            snapshot_id=value["snapshotId"],
            request_id=value["requestId"],
            request_hash=value["requestHash"],
            operation_id=value["operationId"],
            response_id=value["responseId"],
            result_hash=value["resultHash"],
            changed=value["changed"],
            previous_revision=value["previousRevision"],
            current_revision=value["currentRevision"],
            engine_update_id=value.get("engineUpdateId"),
            wake_session_ids=tuple(value["wakeSessionIds"]),
            think_session_ids=tuple(value["thinkSessionIds"]),
            action_session_ids=tuple(value["actionSessionIds"]),
            standard_call_log=tuple(value["standardCallLog"]),
            snapshot_fingerprint=dict(value["snapshotFingerprint"]),
            changed_fingerprint=dict(value["changedFingerprint"]),
            created_at=parse_utc(value["createdAt"], "proof.createdAt"),
            proof_hash=value["proofHash"],
        )


@dataclass(frozen=True, slots=True)
class SandboxAcceptanceReceipt:
    receipt_id: str
    sandbox_id: str
    snapshot_id: str
    interaction_proof_id: str
    request_id: str
    request_hash: str
    operation_id: str
    response_id: str
    result_hash: str
    changed: bool
    previous_revision: int
    current_revision: int
    engine_update_id: str
    snapshot_fingerprint: dict[str, Any]
    changed_fingerprint: dict[str, Any]
    restored_fingerprint: dict[str, Any]
    exact_restored: bool
    snapshot_anchor_hash: str
    standard_interaction_completed: bool
    formal_inventory_before_hash: str
    formal_inventory_after_hash: str
    formal_isolation_verified: bool
    repository_roots_authorized: bool
    created_at: datetime
    receipt_hash: str

    def unsigned_dict(self) -> dict[str, JsonValue]:
        return {
            "receiptId": self.receipt_id,
            "sandboxId": self.sandbox_id,
            "snapshotId": self.snapshot_id,
            "interactionProofId": self.interaction_proof_id,
            "requestId": self.request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "responseId": self.response_id,
            "resultHash": self.result_hash,
            "changed": self.changed,
            "previousRevision": self.previous_revision,
            "currentRevision": self.current_revision,
            "engineUpdateId": self.engine_update_id,
            "snapshotFingerprint": self.snapshot_fingerprint,
            "changedFingerprint": self.changed_fingerprint,
            "restoredFingerprint": self.restored_fingerprint,
            "exactRestored": self.exact_restored,
            "snapshotAnchorHash": self.snapshot_anchor_hash,
            "standardInteractionCompleted": self.standard_interaction_completed,
            "formalInventoryBeforeHash": self.formal_inventory_before_hash,
            "formalInventoryAfterHash": self.formal_inventory_after_hash,
            "formalIsolationVerified": self.formal_isolation_verified,
            "repositoryRootsAuthorized": self.repository_roots_authorized,
            "createdAt": format_utc(self.created_at),
        }

    def to_dict(self) -> dict[str, JsonValue]:
        return {**self.unsigned_dict(), "receiptHash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Any) -> SandboxAcceptanceReceipt:
        if not isinstance(value, dict):
            raise ValueError("acceptance receipt must be an object")
        return cls(
            receipt_id=value["receiptId"],
            sandbox_id=value["sandboxId"],
            snapshot_id=value["snapshotId"],
            interaction_proof_id=value["interactionProofId"],
            request_id=value["requestId"],
            request_hash=value["requestHash"],
            operation_id=value["operationId"],
            response_id=value["responseId"],
            result_hash=value["resultHash"],
            changed=value["changed"],
            previous_revision=value["previousRevision"],
            current_revision=value["currentRevision"],
            engine_update_id=value["engineUpdateId"],
            snapshot_fingerprint=dict(value["snapshotFingerprint"]),
            changed_fingerprint=dict(value["changedFingerprint"]),
            restored_fingerprint=dict(value["restoredFingerprint"]),
            exact_restored=value["exactRestored"],
            snapshot_anchor_hash=value["snapshotAnchorHash"],
            standard_interaction_completed=value["standardInteractionCompleted"],
            formal_inventory_before_hash=value["formalInventoryBeforeHash"],
            formal_inventory_after_hash=value["formalInventoryAfterHash"],
            formal_isolation_verified=value["formalIsolationVerified"],
            repository_roots_authorized=value["repositoryRootsAuthorized"],
            created_at=parse_utc(value["createdAt"], "receipt.createdAt"),
            receipt_hash=value["receiptHash"],
        )


@dataclass(frozen=True, slots=True)
class CleanupResult:
    sandbox_id: str
    cleaned: bool
    already_clean: bool
    reason: str
    cleaned_at: datetime


@dataclass(frozen=True, slots=True)
class SandboxEvidence:
    evidence_id: str
    sandbox_id: str
    subject_id: str
    environment: SandboxEnvironment
    promotion_allowed: bool
    snapshot_hashes: tuple[str, ...]
    acceptance_receipt_id: str
    acceptance_receipt_hash: str
    interaction_request_id: str
    request_hash: str
    operation_id: str
    response_id: str
    result_hash: str
    changed: bool
    previous_revision: int
    current_revision: int
    engine_update_id: str
    snapshot_component_fingerprint: dict[str, Any]
    changed_component_fingerprint: dict[str, Any]
    restored_component_fingerprint: dict[str, Any]
    exact_restored: bool
    snapshot_anchor_hash: str
    standard_interaction_completed: bool
    formal_isolation_verified: bool
    formal_inventory_before_hash: str
    formal_inventory_after_hash: str
    repository_roots_authorized: bool
    final_state_hash: str
    final_revision: int
    exported_at: datetime
    sandbox_removed: bool

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "evidenceId": self.evidence_id,
            "sandboxId": self.sandbox_id,
            "subjectId": self.subject_id,
            "environment": self.environment.value,
            "promotionAllowed": self.promotion_allowed,
            "snapshotHashes": list(self.snapshot_hashes),
            "acceptanceReceiptId": self.acceptance_receipt_id,
            "acceptanceReceiptHash": self.acceptance_receipt_hash,
            "interactionRequestId": self.interaction_request_id,
            "requestHash": self.request_hash,
            "operationId": self.operation_id,
            "responseId": self.response_id,
            "resultHash": self.result_hash,
            "changed": self.changed,
            "previousRevision": self.previous_revision,
            "currentRevision": self.current_revision,
            "engineUpdateId": self.engine_update_id,
            "snapshotComponentFingerprint": self.snapshot_component_fingerprint,
            "changedComponentFingerprint": self.changed_component_fingerprint,
            "restoredComponentFingerprint": self.restored_component_fingerprint,
            "exactRestored": self.exact_restored,
            "snapshotAnchorHash": self.snapshot_anchor_hash,
            "standardInteractionCompleted": self.standard_interaction_completed,
            "formalIsolationVerified": self.formal_isolation_verified,
            "formalInventoryBeforeHash": self.formal_inventory_before_hash,
            "formalInventoryAfterHash": self.formal_inventory_after_hash,
            "repositoryRootsAuthorized": self.repository_roots_authorized,
            "finalStateHash": self.final_state_hash,
            "finalRevision": self.final_revision,
            "exportedAt": format_utc(self.exported_at),
            "sandboxRemoved": self.sandbox_removed,
        }
