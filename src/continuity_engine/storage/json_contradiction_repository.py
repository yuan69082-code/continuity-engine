from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from continuity_engine.domain.contradiction import (
    AuditAction,
    ContradictionCase,
    ContradictionStatus,
    VerificationStatus,
    contradiction_hash,
    validate_resolution_binding,
)
from continuity_engine.storage.base import ResolutionEvidenceVerifier
from continuity_engine.domain.errors import (
    ContradictionIdentityConflictError,
    ContradictionNotFoundError,
    ContradictionPersistenceError,
    ContradictionValidationError,
)


CONTRADICTION_FORMAT_VERSION = 3


class JsonContradictionRepository:
    """Atomic P07 audit repository.

    This document is a non-authoritative, rebuildable contradiction audit. It
    contains only sealed claim value hashes and references already present in P06 output; it is
    not a SubjectState, Event, Memory, Timeline, or Context authority.
    """

    def __init__(
        self, root: Path | str, *, environment: str,
        resolution_evidence_verifier: ResolutionEvidenceVerifier | None = None,
    ) -> None:
        if environment not in {"ENGINE", "TEST", "RESEARCH"}:
            raise ContradictionValidationError(
                "contradiction repository environment is unsupported"
            )
        requested = Path(root)
        if requested.exists() and requested.is_symlink():
            raise ContradictionPersistenceError(
                "contradiction repository root cannot be a symbolic link"
            )
        self.root = requested.resolve(strict=False) / "contradiction" / environment.lower()
        self.environment = environment
        self._resolution_evidence_verifier = resolution_evidence_verifier

    def initialize_empty(self, subject_id: str) -> None:
        """Explicit initialization; detection/read gates need not create files."""
        if self._load_if_exists(subject_id) is None:
            self._write_document(self._path(subject_id), self._load_or_empty(subject_id))

    def save_detected(self, case: ContradictionCase) -> ContradictionCase:
        self._require_case_boundary(case)
        if case.revision != 0:
            raise ContradictionValidationError("detected case must begin at revision zero")
        if case.status is not ContradictionStatus.PENDING_VERIFICATION:
            raise ContradictionValidationError(
                "detected case must begin pending verification"
            )
        data = self._load_or_empty(case.subject_id)
        records = self._records(data)
        history = [item for item in records if item.case_id == case.case_id]
        if history:
            first = history[0]
            if first.canonical_hash() != case.canonical_hash():
                raise ContradictionIdentityConflictError(
                    f"contradiction identity conflict: {case.case_id}"
                )
            return history[-1]
        records.append(case)
        data["case_records"] = [item.to_dict() for item in records]
        self._write_document(self._path(case.subject_id), data)
        return case

    def append_transition(self, case: ContradictionCase) -> ContradictionCase:
        self._require_case_boundary(case)
        data = self._load_if_exists(case.subject_id)
        if data is None:
            raise ContradictionNotFoundError(f"contradiction not found: {case.case_id}")
        records = self._records(data)
        history = [item for item in records if item.case_id == case.case_id]
        if not history:
            raise ContradictionNotFoundError(f"contradiction not found: {case.case_id}")
        current = history[-1]
        if case.revision <= current.revision:
            existing = next(
                (item for item in history if item.revision == case.revision), None
            )
            if existing is not None and existing.canonical_hash() == case.canonical_hash():
                return existing
            raise ContradictionIdentityConflictError(
                "contradiction transition identity conflict"
            )
        self._validate_transition(current, case)
        records.append(case)
        data["case_records"] = [item.to_dict() for item in records]
        self._write_document(self._path(case.subject_id), data)
        return case

    def load_case(self, subject_id: str, case_id: str) -> ContradictionCase:
        history = self.case_history(subject_id, case_id)
        if not history:
            raise ContradictionNotFoundError(f"contradiction not found: {case_id}")
        return history[-1]

    def case_history(self, subject_id: str, case_id: str) -> list[ContradictionCase]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        return [
            item for item in self._records(data) if item.case_id == case_id
        ]

    def list_cases(self, subject_id: str) -> list[ContradictionCase]:
        data = self._load_if_exists(subject_id)
        if data is None:
            return []
        latest: dict[str, ContradictionCase] = {}
        for item in self._records(data):
            latest[item.case_id] = item
        return sorted(latest.values(), key=lambda item: item.case_id)

    def _path(self, subject_id: str) -> Path:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ContradictionValidationError("subject_id must be non-empty")
        name = hashlib.sha256(subject_id.encode("utf-8")).hexdigest()
        return self.root / f"{name}.json"

    def _require_case_boundary(self, case: ContradictionCase) -> None:
        if not isinstance(case, ContradictionCase):
            raise ContradictionValidationError("repository case is invalid")
        ContradictionCase.from_dict(case.to_dict())
        if case.environment != self.environment:
            raise ContradictionValidationError(
                "contradiction environment does not match repository"
            )

    def _load_if_exists(self, subject_id: str) -> dict[str, Any] | None:
        path = self._path(subject_id)
        if not path.is_file():
            return None
        return self._read_document(path, subject_id)

    def _load_or_empty(self, subject_id: str) -> dict[str, Any]:
        return self._load_if_exists(subject_id) or {
            "format_version": CONTRADICTION_FORMAT_VERSION,
            "subject_id": subject_id,
            "environment": self.environment,
            "authority": "NON_AUTHORITATIVE_P07_AUDIT",
            "case_records": [],
        }

    def _read_document(self, path: Path, subject_id: str) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContradictionPersistenceError(
                "contradiction document cannot be read"
            ) from exc
        if not isinstance(raw, dict):
            raise ContradictionPersistenceError("contradiction document must be an object")
        expected_keys = {
            "format_version",
            "subject_id",
            "environment",
            "authority",
            "case_records",
            "document_hash",
        }
        if set(raw) != expected_keys:
            raise ContradictionPersistenceError("contradiction document shape is invalid")
        if raw.get("format_version") != CONTRADICTION_FORMAT_VERSION:
            raise ContradictionPersistenceError("contradiction format version is unsupported")
        if (
            raw.get("subject_id") != subject_id
            or raw.get("environment") != self.environment
            or raw.get("authority") != "NON_AUTHORITATIVE_P07_AUDIT"
        ):
            raise ContradictionPersistenceError("contradiction document boundary mismatch")
        records = raw.get("case_records")
        if not isinstance(records, list):
            raise ContradictionPersistenceError("contradiction records must be a list")
        body = {key: value for key, value in raw.items() if key != "document_hash"}
        if raw.get("document_hash") != contradiction_hash(body):
            raise ContradictionPersistenceError("contradiction document integrity failed")
        self._records(body)
        return body

    def _records(self, data: dict[str, Any]) -> list[ContradictionCase]:
        try:
            records = [
                ContradictionCase.from_dict(item) for item in data.get("case_records", [])
            ]
        except (ContradictionValidationError, TypeError, ValueError) as exc:
            raise ContradictionPersistenceError(
                "contradiction record integrity failed"
            ) from exc
        histories: dict[str, list[ContradictionCase]] = {}
        for item in records:
            if item.subject_id != data.get("subject_id") or item.environment != self.environment:
                raise ContradictionPersistenceError(
                    "contradiction record crosses repository boundary"
                )
            histories.setdefault(item.case_id, []).append(item)
        for case_id, history in histories.items():
            if tuple(item.revision for item in history) != tuple(range(len(history))):
                raise ContradictionPersistenceError(
                    f"contradiction revision chain is invalid: {case_id}"
                )
            if history[0].status is not ContradictionStatus.PENDING_VERIFICATION:
                raise ContradictionPersistenceError("contradiction history has invalid origin")
            for previous, current in zip(history, history[1:]):
                try:
                    self._validate_transition(previous, current)
                except ContradictionValidationError as exc:
                    raise ContradictionPersistenceError(
                        "contradiction transition chain is invalid"
                    ) from exc
        return records

    def _validate_transition(
        self, previous: ContradictionCase, current: ContradictionCase
    ) -> None:
        if current.revision != previous.revision + 1:
            raise ContradictionValidationError("contradiction revision must be monotonic")
        immutable = (
            previous.case_id == current.case_id
            and previous.kind is current.kind
            and previous.subject_id == current.subject_id
            and previous.environment == current.environment
            and previous.proposition_id == current.proposition_id
            and previous.scope_id == current.scope_id
            and previous.claims == current.claims
            and previous.dispositions == current.dispositions
            and previous.impact_scope == current.impact_scope
            and previous.source_snapshot_hash == current.source_snapshot_hash
            and previous.detector_version == current.detector_version
            and previous.verification_task.task_id == current.verification_task.task_id
            and previous.verification_task.required_claim_ids
            == current.verification_task.required_claim_ids
            and previous.verification_task.conditions == current.verification_task.conditions
        )
        if not immutable:
            raise ContradictionValidationError(
                "contradiction transition rewrites immutable evidence"
            )
        if current.audit_history[:-1] != previous.audit_history:
            raise ContradictionValidationError("contradiction audit history is not append-only")
        tail = current.audit_history[-1]
        allowed = {
            ContradictionStatus.PENDING_VERIFICATION: {
                ContradictionStatus.RESOLVED: AuditAction.RESOLVED,
            },
            ContradictionStatus.OPEN: {
                ContradictionStatus.ISOLATED: AuditAction.ISOLATED,
                ContradictionStatus.PENDING_VERIFICATION: AuditAction.ISOLATED,
                ContradictionStatus.RESOLVED: AuditAction.RESOLVED,
            },
            ContradictionStatus.ISOLATED: {
                ContradictionStatus.PENDING_VERIFICATION: AuditAction.ISOLATED,
                ContradictionStatus.RESOLVED: AuditAction.RESOLVED,
            },
            ContradictionStatus.REOPENED: {
                ContradictionStatus.RESOLVED: AuditAction.RESOLVED,
                ContradictionStatus.SUPERSEDED: AuditAction.SUPERSEDED,
            },
            ContradictionStatus.RESOLVED: {
                ContradictionStatus.REOPENED: AuditAction.REOPENED,
                ContradictionStatus.SUPERSEDED: AuditAction.SUPERSEDED,
            },
            ContradictionStatus.SUPERSEDED: {},
        }
        if allowed.get(previous.status, {}).get(current.status) is not tail.action:
            raise ContradictionValidationError("illegal contradiction lifecycle transition")
        expected_verification = (
            VerificationStatus.COMPLETED
            if current.status
            in {ContradictionStatus.RESOLVED, ContradictionStatus.SUPERSEDED}
            else VerificationStatus.OPEN
        )
        if current.verification_task.status is not expected_verification:
            raise ContradictionValidationError(
                "contradiction verification status does not match lifecycle"
            )
        if tail.resolution is not None:
            validate_resolution_binding(previous, tail.resolution, tail.action)
            verifier = self._resolution_evidence_verifier
            if verifier is None:
                raise ContradictionValidationError("TRUSTED_RESOLUTION_EVIDENCE_VERIFIER_REQUIRED")
            try:
                verified = verifier.verify(previous, tail.resolution.as_request(), action=tail.action)
            except Exception as exc:
                raise ContradictionValidationError("PERSISTED_RESOLUTION_VERIFICATION_FAILED") from exc
            if verified != tail.resolution:
                raise ContradictionValidationError("persisted resolution differs from trusted evidence binding")
            if tail.action is AuditAction.REOPENED and set(verified.source_hashes).issubset(
                {value for audit in previous.audit_history for value in audit.source_hashes}
            ):
                raise ContradictionValidationError("reopen requires genuinely new evidence")

    def _write_document(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "format_version": CONTRADICTION_FORMAT_VERSION,
            "subject_id": data["subject_id"],
            "environment": data["environment"],
            "authority": "NON_AUTHORITATIVE_P07_AUDIT",
            "case_records": data["case_records"],
        }
        document = {**body, "document_hash": contradiction_hash(body)}
        payload = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.stem}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
