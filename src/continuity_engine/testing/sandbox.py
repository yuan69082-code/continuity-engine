from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from continuity_engine.domain.awakening import AwakeCycle
from continuity_engine.domain.events import ChangeOperation, Event, StateMutation, StateSection
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import (
    calculate_binding_fixture_hash,
    calculate_state_hash,
    canonicalize_json,
    sha256_hash,
)
from continuity_engine.domain.memory import MemoryCandidate, MemoryRetrievalRequest
from continuity_engine.domain.resources import RuntimeMode
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_subject_binding_repository import JsonSubjectBindingRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository

from .models import (
    CleanupResult,
    RetentionMode,
    SandboxDescriptor,
    SandboxEnvironment,
    SandboxEvidence,
    SandboxAcceptanceReceipt,
    SandboxInteractionProof,
    SandboxLifecycle,
    SandboxOperationError,
    SnapshotComponent,
    SnapshotFileInventoryEntry,
    SnapshotManifest,
    StateFixture,
    format_utc,
)
from .persistence import (
    SandboxFrozenClock,
    SandboxActionRepository,
    SandboxMemoryRepository,
    SandboxTraceRepository,
    assert_descendant,
    assert_no_link_components,
    atomic_write_json,
    canonical_hash,
    copy_tree_without_links,
    file_hash,
    is_link_like,
    physical_file_inventory,
    read_json,
    remove_tree_safely,
)


P01_ROOT_MARKER = ".p01-sandbox-root.v1.json"
P01_REGISTRY = "sandbox-registry.v1.json"
SANDBOX_MARKER = "sandbox-manifest.v1.json"
BRANCH_MARKER = "branch-manifest.v1.json"
SNAPSHOT_MANIFEST = "snapshot-manifest.v1.json"
MAX_DEBUG_RETENTION = timedelta(days=7)
FAILURE_RETENTION = timedelta(hours=24)

REQUIRED_SNAPSHOT_COMPONENTS = frozenset(
    {
        "subject_state",
        "events",
        "state_mutations",
        "evolution",
        "memory",
        "learning",
        "relationship_state",
        "wake_sessions",
        "thinking_sessions",
        "action_sessions",
        "operation_journal",
        "completed_result_ledger",
        "capability_ledger",
        "resource_ledger",
        "subject_binding",
        "awake_cycle",
        "subject_clock",
        "state_fixture",
        "test_trace",
    }
)


def _id(prefix: str) -> str:
    compact_prefixes = {
        "p01": "sb",
        "p01-subject": "sub",
        "p01-binding": "bind",
        "p01-cycle": "cy",
        "p01-namespace": "ns",
        "p01-branch": "br",
        "p01-snapshot": "snap",
        "p01-resource": "res",
    }
    if prefix == "p01-snapshot":
        return f"n{uuid4().hex[:12]}"
    return f"{compact_prefixes.get(prefix, prefix)}-{uuid4().hex[:16]}"


def _subject_file_name(subject_id: str) -> str:
    return f"{hashlib.sha256(subject_id.encode('utf-8')).hexdigest()}.json"


def _physical_id(value: str, prefix: str) -> str:
    return f"{prefix}{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SandboxOperationError(
            "SANDBOX_PATH_FORBIDDEN", "component path escaped its branch data root"
        ) from exc


def _aggregate_file_hash(data_root: Path, physical_path: str) -> str:
    entries: list[dict[str, str]] = []
    for relative_name in physical_path.split(";"):
        path = data_root / Path(relative_name)
        if not path.is_file() or is_link_like(path):
            raise SandboxOperationError(
                "SNAPSHOT_INCOMPLETE", "a component physical file is missing or unsafe"
            )
        entries.append({"path": relative_name, "sha256": file_hash(path)})
    return canonical_hash(entries)


def _physical_path_entries(physical_path: str) -> tuple[str, ...]:
    if not isinstance(physical_path, str) or not physical_path:
        raise SandboxOperationError("SNAPSHOT_TAMPERED", "component path is empty")
    entries = physical_path.split(";")
    if len(entries) != len(set(entries)):
        raise SandboxOperationError("SNAPSHOT_TAMPERED", "component paths are duplicated")
    for entry in entries:
        candidate = Path(entry)
        if (
            not entry
            or candidate.is_absolute()
            or entry != candidate.as_posix()
            or any(part in ("", ".", "..") for part in candidate.parts)
        ):
            raise SandboxOperationError("SNAPSHOT_TAMPERED", "component path is unsafe")
    return tuple(entries)


def _mapped_inventory(logical: dict[str, dict[str, Any]]) -> set[str]:
    mapped: set[str] = set()
    for item in logical.values():
        for path in _physical_path_entries(item["physicalPath"]):
            if path in mapped:
                raise SandboxOperationError(
                    "SNAPSHOT_INCOMPLETE",
                    "a physical file is mapped to more than one snapshot component",
                )
            mapped.add(path)
    return mapped


def _manifest_fingerprint(manifest: SnapshotManifest) -> dict[str, dict[str, Any]]:
    return {
        item.name: {
            "canonicalContentHash": item.canonical_content_hash,
            "revision": item.revision,
            "count": item.count,
        }
        for item in manifest.components
    }


class SandboxRuntime:
    """One test-only subject branch wired to real Event/Evolution repositories."""

    def __init__(
        self,
        *,
        descriptor: SandboxDescriptor,
        branch_id: str,
        branch_root: Path,
        access_recorder: Callable[[Path, str], None] | None = None,
    ) -> None:
        if branch_id not in descriptor.branch_ids:
            raise SandboxOperationError("SANDBOX_BRANCH_INVALID", "branch is not registered")
        self.descriptor = descriptor
        self.branch_id = branch_id
        self.branch_root = branch_root
        self.data_root = branch_root / "data"
        self._record_access = access_recorder or (lambda _path, _kind: None)
        self._record_access(self.data_root, "runtime")
        self.clock = SandboxFrozenClock(self.data_root / "clock" / "subject-clock.v1.json")
        self.state_repository = JsonSubjectStateRepository(self.data_root / "subject-state")
        self.subject_states = SubjectStateService(self.state_repository, clock=self.clock.now)
        self.awakening = JsonAwakeningRepository(self.data_root)
        self.learning_repository = JsonLearningRepository(self.data_root)
        self.learning = LearningService(self.learning_repository, clock=self.clock.now)
        self.resource_repository = JsonResourceRepository(self.data_root)
        self.resources = ResourceManager(self.resource_repository, clock=self.clock.now)
        self.memory = SandboxMemoryRepository(self.data_root)
        self.memory_service = MemoryService(
            self.memory,
            self.memory,
            clock=self.clock.now,
        )
        self.trace = SandboxTraceRepository(self.data_root)
        self.binding_repository = JsonSubjectBindingRepository(self.data_root)
        self.integration_ledger = JsonIntegrationResultLedger(self.data_root)
        self.thinking_repository = JsonThinkingRepository(self.data_root)
        self.action_repository = SandboxActionRepository(self.data_root)
        self._assert_repository_roots_authorized()

    def repository_roots(self) -> tuple[Path, ...]:
        return (
            self.state_repository.root,
            self.awakening.root,
            self.learning_repository.root,
            self.resource_repository.root,
            self.memory.path.parent,
            self.trace.path.parent,
            self.binding_repository.path.parent,
            self.integration_ledger.path.parent,
            self.thinking_repository.root,
            self.action_repository.path.parent,
            self.clock._path.parent,
            self.data_root / "fixture",
            self.data_root / "test-indexes",
        )

    def _assert_repository_roots_authorized(self) -> None:
        for root in self.repository_roots():
            resolved = root.resolve(strict=False)
            base = self.data_root.resolve(strict=False)
            if resolved == base or base not in resolved.parents:
                raise SandboxOperationError(
                    "SANDBOX_PATH_FORBIDDEN",
                    "a P01 repository root is outside its sandbox data root",
                )

    def repository_roots_authorized(self) -> bool:
        self._assert_repository_roots_authorized()
        return True

    def execute_standard_interaction(self):
        from .interaction import execute_standard_interaction

        return execute_standard_interaction(self)

    def subject_state(self):
        return self.subject_states.load(self.descriptor.subject_id)

    def apply_fixture(self, fixture: StateFixture) -> Event:
        fixture_path = self.data_root / "fixture" / "state-fixture.v1.json"
        if fixture_path.exists():
            raise SandboxOperationError("FIXTURE_ALREADY_APPLIED", "fixture is immutable")
        state = self.subject_state()
        if state.revision != 0:
            raise SandboxOperationError(
                "FIXTURE_REVISION_CONFLICT", "fixture requires a new revision-zero subject"
            )
        mutations: list[StateMutation] = []
        for item in fixture.personality_traits:
            mutations.append(
                StateMutation(
                    field_path="identity.stable_traits",
                    operation=ChangeOperation.APPEND,
                    value=item,
                    reason="Synthetic P01 fixture personality evidence.",
                )
            )
        for item in fixture.expression_preferences:
            mutations.append(
                StateMutation(
                    field_path="identity.expression_preferences",
                    operation=ChangeOperation.APPEND,
                    value=item,
                    reason="Synthetic P01 fixture expression preference.",
                )
            )
        mutations.append(
            StateMutation(
                field_path="relationship.current_status",
                operation=ChangeOperation.SET,
                value=fixture.relationship_status,
                reason="Synthetic P01 fixture relationship state.",
            )
        )
        for item in fixture.relationship_moments:
            mutations.append(
                StateMutation(
                    field_path="relationship.important_moments",
                    operation=ChangeOperation.APPEND,
                    value=item,
                    reason="Synthetic P01 fixture relationship evidence.",
                )
            )
        for item in fixture.continuity_focus:
            mutations.append(
                StateMutation(
                    field_path="continuity.current_focus",
                    operation=ChangeOperation.APPEND,
                    value=item,
                    reason="Synthetic P01 fixture continuity focus.",
                )
            )
        event = Event.create(
            event_id=_id("p01-fixture-event"),
            occurred_at=self.clock.now(),
            source="continuity_engine.testing.state_fixture",
            event_type="synthetic_test_fixture",
            content="Apply a synthetic P01 State Fixture through Event/Evolution.",
            impact_scope=[
                StateSection.IDENTITY,
                StateSection.RELATIONSHIP,
                StateSection.CONTINUITY,
            ],
            mutations=mutations,
            reason="Initialize a disposable test subject without fabricating formal history.",
            metadata={
                "synthetic": True,
                "environment": "TEST",
                "sandbox_id": self.descriptor.sandbox_id,
                "branch_id": self.branch_id,
                "fixture_id": fixture.fixture_id,
            },
        )
        result = self.subject_states.apply_event(
            self.descriptor.subject_id,
            event,
            expected_revision=0,
        )
        for index, content in enumerate(fixture.memories):
            self.memory.save_memory(
                MemoryCandidate(
                    memory_id=f"{fixture.fixture_id}-memory-{index + 1}",
                    subject_id=self.descriptor.subject_id,
                    content=content,
                    source="continuity_engine.testing.state_fixture",
                    occurred_at=self.clock.now(),
                    provider_relevance=1.0,
                    related_scope=[StateSection.CONTINUITY],
                    tags=["synthetic", "test"],
                    metadata={"synthetic": True, "environment": "TEST"},
                )
            )
        preference = (
            fixture.expression_preferences[0]
            if fixture.expression_preferences
            else "synthetic fixture preference"
        )
        self.learning.create_candidate(
            self.descriptor.subject_id,
            source_event_id=event.event_id,
            source_memory_id=None,
            related_state_revision=result.state.revision,
            observation="A synthetic fixture supplied explicit learning evidence.",
            hypothesis="The test branch must preserve and restore learning candidates.",
            proposed_change=StateMutation(
                field_path="identity.expression_preferences",
                operation=ChangeOperation.APPEND,
                value=preference,
                reason="Synthetic P01 learning candidate.",
            ),
            confidence=0.5,
            original_experience={
                "synthetic": True,
                "environment": "TEST",
                "source_event_id": event.event_id,
            },
            reason="Exercise the sandbox Learning repository without formal consolidation.",
            source="continuity_engine.testing.state_fixture",
            learning_id=_id("p01-learning"),
        )
        fixture_document = {
            **fixture.to_dict(),
            "sandboxId": self.descriptor.sandbox_id,
            "subjectId": self.descriptor.subject_id,
            "branchId": self.branch_id,
            "appliedEventId": event.event_id,
            "appliedRevision": result.state.revision,
            "appliedAt": format_utc(self.clock.now()),
            "promotionAllowed": False,
        }
        atomic_write_json(fixture_path, fixture_document)
        for component in (
            "SubjectState",
            "Event",
            "Evolution",
            "Memory",
            "Learning",
            "Thinking",
            "operation/result",
        ):
            self.trace.record(
                component,
                self.clock.now(),
                {"fixtureId": fixture.fixture_id, "revision": result.state.revision},
            )
        return event

    def apply_changed_event(
        self,
        *,
        personality_trait: str,
        relationship_status: str,
        continuity_focus: str,
        memory_content: str,
    ) -> Event:
        for value, name in (
            (personality_trait, "personality_trait"),
            (relationship_status, "relationship_status"),
            (continuity_focus, "continuity_focus"),
            (memory_content, "memory_content"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise SandboxOperationError("TEST_CHANGE_INVALID", f"{name} is empty")
        state = self.subject_state()
        event = Event.create(
            event_id=_id("p01-change-event"),
            occurred_at=self.clock.now(),
            source="continuity_engine.testing.changed_true",
            event_type="synthetic_test_change",
            content="Exercise a changed=true sandbox evolution.",
            impact_scope=[
                StateSection.IDENTITY,
                StateSection.RELATIONSHIP,
                StateSection.CONTINUITY,
            ],
            mutations=[
                StateMutation(
                    "identity.stable_traits",
                    ChangeOperation.APPEND,
                    personality_trait,
                    "Synthetic changed=true personality change.",
                ),
                StateMutation(
                    "relationship.current_status",
                    ChangeOperation.SET,
                    relationship_status,
                    "Synthetic changed=true relationship change.",
                ),
                StateMutation(
                    "continuity.current_focus",
                    ChangeOperation.APPEND,
                    continuity_focus,
                    "Synthetic changed=true continuity change.",
                ),
            ],
            reason="Validate exact P01 Snapshot/Rollback across a real Evolution.",
            metadata={
                "synthetic": True,
                "environment": "TEST",
                "sandbox_id": self.descriptor.sandbox_id,
                "branch_id": self.branch_id,
            },
        )
        result = self.subject_states.apply_event(
            self.descriptor.subject_id,
            event,
            expected_revision=state.revision,
        )
        memory_id = _id("p01-memory")
        self.memory.save_memory(
            MemoryCandidate(
                memory_id=memory_id,
                subject_id=self.descriptor.subject_id,
                content=memory_content,
                source="continuity_engine.testing.changed_true",
                occurred_at=self.clock.now(),
                provider_relevance=1.0,
                related_scope=[StateSection.IDENTITY, StateSection.RELATIONSHIP],
                tags=["synthetic", "test", "changed-true"],
                metadata={"synthetic": True, "environment": "TEST"},
            )
        )
        memory_result = self.memory_service.retrieve(
            MemoryRetrievalRequest.create(
                request_id=_id("p01-memory-request"),
                subject_id=self.descriptor.subject_id,
                query=memory_content,
                requested_at=self.clock.now(),
                desired_scope=[StateSection.IDENTITY, StateSection.RELATIONSHIP],
                minimum_relevance=0.0,
            )
        )
        self.memory_service.record_influence(
            memory_result,
            memory_id=memory_id,
            influence_type="synthetic_test",
            summary="A synthetic memory participates in rollback verification.",
            reason="Exercise the test-only Memory influence repository.",
            affected_fields=["identity.stable_traits", "relationship.current_status"],
            state_update=result.update,
            metadata={"synthetic": True, "environment": "TEST"},
        )
        self.learning.create_candidate(
            self.descriptor.subject_id,
            source_event_id=event.event_id,
            source_memory_id=None,
            related_state_revision=result.state.revision,
            observation="A synthetic changed=true event was observed.",
            hypothesis="Snapshot rollback must remove post-snapshot learning evidence.",
            proposed_change=StateMutation(
                field_path="identity.stable_traits",
                operation=ChangeOperation.APPEND,
                value=personality_trait,
                reason="Synthetic post-snapshot learning evidence.",
            ),
            confidence=0.5,
            original_experience={
                "synthetic": True,
                "environment": "TEST",
                "event_id": event.event_id,
            },
            reason="Exercise Learning persistence after the snapshot point.",
            source="continuity_engine.testing.changed_true",
            learning_id=_id("p01-learning"),
        )
        self.resources.request_learning(
            self.descriptor.subject_id,
            _id("p01-learning-session"),
            reason="Exercise resource ledger rollback in a synthetic branch.",
            estimated_tokens=32,
            estimated_compute=1,
        )
        self.trace.record(
            "changed_true",
            self.clock.now(),
            {
                "eventId": event.event_id,
                "updateId": result.update.update_id,
                "revision": result.state.revision,
            },
        )
        return event

    def logical_components(self) -> dict[str, dict[str, Any]]:
        state = self.subject_state()
        updates = self.subject_states.get_update_history(self.descriptor.subject_id)
        wake_sessions = self.awakening.list_sessions(self.descriptor.subject_id)
        think_sessions = self.thinking_repository.list_think_sessions(
            self.descriptor.subject_id
        )
        action_sessions = self.action_repository.list_action_sessions(
            self.descriptor.subject_id
        )
        learning_events = self.learning.list_learning_events(self.descriptor.subject_id)
        learning_traits = self.learning.list_traits(self.descriptor.subject_id)
        learning_records = self.learning.get_history(self.descriptor.subject_id)
        resource_state = self.resources.get_resource_state(self.descriptor.subject_id)
        resource_usage = self.resources.get_usage_history(self.descriptor.subject_id)
        resource_decisions = self.resources.get_decision_history(self.descriptor.subject_id)
        binding = self.binding_repository.load_active()
        cycle = self.awakening.load_cycle(self.descriptor.cycle_id)

        subject_path = self.data_root / "subject-state" / _subject_file_name(
            self.descriptor.subject_id
        )
        learning_path = self.data_root / "learning" / _subject_file_name(
            self.descriptor.subject_id
        )
        resource_path = self.data_root / "resources" / _subject_file_name(
            self.descriptor.subject_id
        )
        fixture_path = self.data_root / "fixture" / "state-fixture.v1.json"
        wake_paths = [
            self.awakening._session_path(self.descriptor.subject_id, item.session_id)
            for item in wake_sessions
        ]
        think_paths = [
            self.thinking_repository._path(self.descriptor.subject_id, item.think_id)
            for item in think_sessions
        ]
        physical_paths = {
            "subject_state": [subject_path],
            "events": [self.data_root / "test-indexes" / "events.v1.json"],
            "state_mutations": [
                self.data_root / "test-indexes" / "state-mutations.v1.json"
            ],
            "evolution": [self.data_root / "test-indexes" / "evolution.v1.json"],
            "relationship_state": [
                self.data_root / "test-indexes" / "relationship-state.v1.json"
            ],
            "memory": [self.memory.path],
            "learning": [learning_path],
            "wake_sessions": [
                self.data_root / "test-indexes" / "wake-sessions.v1.json",
                *wake_paths,
            ],
            "thinking_sessions": [
                self.data_root / "test-indexes" / "thinking-sessions.v1.json",
                *think_paths,
            ],
            "action_sessions": [self.action_repository.path],
            "operation_journal": [self.integration_ledger.operation_path],
            "completed_result_ledger": [self.integration_ledger.path],
            "capability_ledger": [self.integration_ledger.capability_path],
            "resource_ledger": [resource_path],
            "subject_binding": [self.binding_repository.path],
            "awake_cycle": [self.awakening._cycle_path(self.descriptor.cycle_id)],
            "subject_clock": [self.data_root / "clock" / "subject-clock.v1.json"],
            "state_fixture": [fixture_path],
            "test_trace": [self.trace.path],
        }
        from .c1_snapshot import additions, permission_additions
        c1 = additions(self.data_root, self.descriptor.subject_id)
        owner_permissions = permission_additions(self.data_root, self.descriptor.subject_id)
        physical_paths['state_fixture'].extend(path for path, _ in owner_permissions)
        for name, (path, _) in c1.items():
            physical_paths[name].append(path)
        for name, paths in physical_paths.items():
            if any(not path.is_file() or is_link_like(path) for path in paths):
                raise SandboxOperationError(
                    "SNAPSHOT_INCOMPLETE", f"required component is missing or unsafe: {name}"
                )

        result_document = read_json(self.integration_ledger.path)
        operation_document = read_json(self.integration_ledger.operation_path)
        capability_document = read_json(self.integration_ledger.capability_path)
        fixture_document = read_json(fixture_path)
        trace_document = self.trace.to_dict()
        components: dict[str, tuple[Any, int | None, int]] = {
            "subject_state": (state.to_dict(), state.revision, 1),
            "events": ([item.event.to_dict() for item in updates], state.revision, len(updates)),
            "state_mutations": (
                [mutation.to_dict() for item in updates for mutation in item.event.mutations],
                state.revision,
                sum(len(item.event.mutations) for item in updates),
            ),
            "evolution": ([item.to_dict() for item in updates], state.revision, len(updates)),
            "memory": (self.memory.to_dict(), None, len(self.memory.list_memories())),
            "learning": (
                {
                    "learningEvents": [item.to_dict() for item in learning_events],
                    "traits": [item.to_dict() for item in learning_traits],
                    "records": [item.to_dict() for item in learning_records],
                },
                None,
                len(learning_events) + len(learning_traits) + len(learning_records),
            ),
            "relationship_state": (state.to_dict()["relationship"], state.revision, 1),
            "wake_sessions": (
                [item.to_dict() for item in wake_sessions],
                None,
                len(wake_sessions),
            ),
            "thinking_sessions": (
                [item.to_dict() for item in think_sessions],
                None,
                len(think_sessions),
            ),
            "action_sessions": (
                [item.to_dict() for item in action_sessions],
                None,
                len(action_sessions),
            ),
            "operation_journal": (
                operation_document,
                None,
                len(operation_document.get("operations", [])),
            ),
            "completed_result_ledger": (
                result_document,
                None,
                len(result_document.get("results", [])),
            ),
            "capability_ledger": (
                capability_document,
                None,
                len(capability_document.get("requests", []))
                + len(capability_document.get("attempts", [])),
            ),
            "resource_ledger": (
                {
                    "state": resource_state.to_dict(),
                    "usage": [item.to_dict() for item in resource_usage],
                    "decisions": [item.to_dict() for item in resource_decisions],
                },
                resource_state.revision,
                len(resource_usage) + len(resource_decisions),
            ),
            "subject_binding": (binding.to_dict(), None, 1),
            "awake_cycle": (cycle.to_dict(), None, 1),
            "subject_clock": (self.clock.to_dict(), None, 1),
            "state_fixture": (fixture_document, fixture_document["appliedRevision"], 1),
            "test_trace": (trace_document, None, len(trace_document["entries"])),
        }
        for name, (_, document) in c1.items():
            payload, revision, count = components[name]
            components[name] = ({"p01": payload, "c1": document}, revision, count + 1)
        if owner_permissions:
            payload, revision, count = components['state_fixture']
            components['state_fixture'] = ({'fixture': payload,
                'testOwnerPermissions': [document for _, document in owner_permissions]},
                revision, count + len(owner_permissions))
        return {
            name: {
                "payload": payload,
                "physicalPath": ";".join(
                    sorted(_relative(path, self.data_root) for path in physical_paths[name])
                ),
                "revision": revision,
                "count": count,
            }
            for name, (payload, revision, count) in components.items()
        }

    def component_fingerprint(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "canonicalContentHash": canonical_hash(item["payload"]),
                "revision": item["revision"],
                "count": item["count"],
            }
            for name, item in self.logical_components().items()
        }

    def promote(self) -> None:
        raise SandboxOperationError(
            "PROMOTION_FORBIDDEN", "P01 test subjects cannot be promoted or imported"
        )


class P01SandboxManager:
    """Registered, non-promotable P01 sandbox lifecycle and snapshot manager."""

    ROOT_FORMAT_VERSION = 1
    REGISTRY_FORMAT_VERSION = 1

    def __init__(
        self,
        base_root: str | Path,
        *,
        formal_data_roots: tuple[str | Path, ...] = (),
        protected_paths: tuple[str | Path, ...] = (),
        maintenance_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.base_root = Path(base_root).resolve(strict=False)
        self.sandboxes_root = self.base_root / "s"
        self.evidence_root = self.base_root / "evidence"
        self.registry_path = self.base_root / P01_REGISTRY
        self._maintenance_clock = maintenance_clock
        repo_root = Path(__file__).resolve().parents[3]
        self._home_root = Path.home().resolve(strict=False)
        isolated = [repo_root, *map(Path, formal_data_roots), *map(Path, protected_paths)]
        self._isolation_paths = tuple(
            dict.fromkeys(path.resolve(strict=False) for path in isolated)
        )
        supplied = [self._home_root, *self._isolation_paths]
        self.protected_paths = tuple(
            dict.fromkeys(path.resolve(strict=False) for path in supplied)
        )
        self._accesses: list[tuple[Path, str]] = []
        self._validate_base_root()
        self._initialize_root()
        self.scan_expired()

    @property
    def formal_access_count(self) -> int:
        return sum(
            1
            for path, _kind in self._accesses
            if any(
                path == protected or protected in path.parents
                for protected in self._isolation_paths
            )
        )

    def _sandbox_root(self, sandbox_id: str) -> Path:
        return self.sandboxes_root / _physical_id(sandbox_id, "s")

    @staticmethod
    def _branch_root(sandbox_root: Path, branch_id: str) -> Path:
        return sandbox_root / "b" / _physical_id(branch_id, "b")

    def create_sandbox(self, *, frozen_at: datetime) -> SandboxRuntime:
        self.scan_expired()
        if frozen_at.tzinfo is None:
            raise SandboxOperationError("CLOCK_INVALID", "frozen time must be timezone-aware")
        sandbox_id = _id("p01")
        subject_id = _id("p01-subject")
        binding_id = _id("p01-binding")
        cycle_id = _id("p01-cycle")
        namespace_id = _id("p01-namespace")
        branch_id = _id("p01-branch")
        sandbox_root = self._sandbox_root(sandbox_id)
        branch_root = self._branch_root(sandbox_root, branch_id)
        data_root = branch_root / "data"
        created_at = self._maintenance_now()
        descriptor = SandboxDescriptor(
            sandbox_id=sandbox_id,
            environment=SandboxEnvironment.TEST,
            subject_id=subject_id,
            binding_id=binding_id,
            cycle_id=cycle_id,
            namespace_id=namespace_id,
            data_root=str(data_root),
            created_at=created_at,
            expires_at=created_at + FAILURE_RETENTION,
            retention_mode=RetentionMode.FAILURE_24_HOURS,
            synthetic=True,
            promotion_allowed=False,
            lifecycle=SandboxLifecycle.ACTIVE,
            active_branch_id=branch_id,
            branch_ids=[branch_id],
            protected_paths=[str(item) for item in self.protected_paths],
        )
        if sandbox_root.exists():
            raise SandboxOperationError("SANDBOX_ID_CONFLICT", "sandbox already exists")
        data_root.mkdir(parents=True)
        atomic_write_json(
            branch_root / BRANCH_MARKER,
            {
                "formatVersion": 1,
                "sandboxId": sandbox_id,
                "branchId": branch_id,
                "namespaceId": namespace_id,
                "environment": "TEST",
                "synthetic": True,
                "promotionAllowed": False,
                "sourceSnapshotId": None,
            },
        )
        self._save_descriptor(descriptor)
        self._register(descriptor)
        try:
            self._initialize_branch(descriptor, branch_root, frozen_at)
        except Exception:
            remove_tree_safely(sandbox_root, allowed_parent=self.sandboxes_root)
            self._remove_registry_entry(sandbox_id)
            raise
        return self.open_runtime(sandbox_id, branch_id=branch_id)

    def open_runtime(self, sandbox_id: str, *, branch_id: str | None = None) -> SandboxRuntime:
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        if descriptor.lifecycle not in {
            SandboxLifecycle.ACTIVE,
            SandboxLifecycle.RETAINED,
        }:
            raise SandboxOperationError("SANDBOX_NOT_ACTIVE", "sandbox is not accessible")
        selected = branch_id or descriptor.active_branch_id
        if selected not in descriptor.branch_ids:
            raise SandboxOperationError("SANDBOX_BRANCH_INVALID", "branch is not registered")
        branch_root = self._branch_root(sandbox_root, selected)
        self._validate_branch_marker(descriptor, selected, branch_root)
        assert_no_link_components(branch_root, stop_at=sandbox_root)
        return SandboxRuntime(
            descriptor=descriptor,
            branch_id=selected,
            branch_root=branch_root,
            access_recorder=self._record_access,
        )

    def create_snapshot(
        self,
        sandbox_id: str,
        *,
        expected_revision: int,
        branch_id: str | None = None,
    ) -> SnapshotManifest:
        runtime = self.open_runtime(sandbox_id, branch_id=branch_id)
        state = runtime.subject_state()
        if state.revision != expected_revision:
            raise SandboxOperationError(
                "SNAPSHOT_REVISION_CONFLICT",
                f"expected revision {expected_revision}, found {state.revision}",
            )
        snapshot_id = _id("p01-snapshot")
        sandbox_root = runtime.branch_root.parents[1]
        snapshots_root = sandbox_root / "n"
        final_root = snapshots_root / snapshot_id
        staging_root = snapshots_root / f".{snapshot_id}b"
        if final_root.exists() or staging_root.exists():
            raise SandboxOperationError("SNAPSHOT_ID_CONFLICT", "snapshot already exists")
        try:
            logical = runtime.logical_components()
            if set(logical) != REQUIRED_SNAPSHOT_COMPONENTS:
                raise SandboxOperationError(
                    "SNAPSHOT_INCOMPLETE", "snapshot component registry is incomplete"
                )
            physical_inventory = physical_file_inventory(runtime.data_root)
            inventory_paths = {item["relativePath"] for item in physical_inventory}
            if inventory_paths != _mapped_inventory(logical):
                raise SandboxOperationError(
                    "SNAPSHOT_INCOMPLETE",
                    "snapshot physical inventory contains missing or unmapped files",
                )
            staging_root.mkdir(parents=True)
            copy_tree_without_links(
                runtime.data_root,
                staging_root / "payload",
                boundary=sandbox_root,
            )
            logical_root = staging_root / "logical"
            logical_root.mkdir()
            created_at = runtime.clock.now()
            components: list[SnapshotComponent] = []
            for name in sorted(logical):
                item = logical[name]
                logical_path = logical_root / f"{name}.json"
                atomic_write_json(logical_path, {"name": name, "payload": item["payload"]})
                components.append(
                    SnapshotComponent(
                        name=name,
                        physical_path=item["physicalPath"],
                        canonical_content_hash=canonical_hash(item["payload"]),
                        file_hash=_aggregate_file_hash(
                            runtime.data_root, item["physicalPath"]
                        ),
                        revision=item["revision"],
                        count=item["count"],
                        snapshot_id=snapshot_id,
                        source_branch=runtime.branch_id,
                        created_at=created_at,
                    )
                )
            unsigned = SnapshotManifest(
                manifest_version=1,
                snapshot_id=snapshot_id,
                sandbox_id=sandbox_id,
                subject_id=runtime.descriptor.subject_id,
                namespace_id=runtime.descriptor.namespace_id,
                environment=SandboxEnvironment.TEST,
                promotion_allowed=False,
                source_branch=runtime.branch_id,
                source_revision=state.revision,
                created_at=created_at,
                components=tuple(components),
                physical_inventory=tuple(
                    SnapshotFileInventoryEntry(
                        relative_path=item["relativePath"],
                        file_hash=item["fileHash"],
                    )
                    for item in physical_inventory
                ),
                complete=True,
                manifest_hash="pending",
            )
            manifest = replace(unsigned, manifest_hash=canonical_hash(unsigned.unsigned_dict()))
            atomic_write_json(staging_root / SNAPSHOT_MANIFEST, manifest.to_dict())
            os.replace(staging_root, final_root)
            descriptor = self._load_descriptor(sandbox_root)
            descriptor.snapshot_ids.append(snapshot_id)
            descriptor.snapshot_anchors[snapshot_id] = manifest.manifest_hash
            self._save_descriptor(descriptor)
            self._register(descriptor)
            return self.validate_snapshot(sandbox_id, snapshot_id)
        except Exception as exc:
            for candidate in (staging_root, final_root):
                if candidate.exists():
                    remove_tree_safely(candidate, allowed_parent=snapshots_root)
            try:
                descriptor = self._load_descriptor(sandbox_root)
                if snapshot_id in descriptor.snapshot_ids:
                    descriptor.snapshot_ids.remove(snapshot_id)
                    descriptor.snapshot_anchors.pop(snapshot_id, None)
                    self._save_descriptor(descriptor)
                    self._register(descriptor)
            except Exception:
                pass
            if isinstance(exc, SandboxOperationError):
                raise
            raise SandboxOperationError(
                "SNAPSHOT_INCOMPLETE", "snapshot creation failed closed"
            ) from exc

    def validate_snapshot(self, sandbox_id: str, snapshot_id: str) -> SnapshotManifest:
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        if snapshot_id not in descriptor.snapshot_ids:
            raise SandboxOperationError("SNAPSHOT_NOT_FOUND", "snapshot is not registered")
        snapshot_root = sandbox_root / "n" / snapshot_id
        assert_descendant(snapshot_root, sandbox_root)
        assert_no_link_components(snapshot_root, stop_at=sandbox_root)
        try:
            manifest = SnapshotManifest.from_dict(
                read_json(snapshot_root / SNAPSHOT_MANIFEST)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "snapshot manifest is invalid"
            ) from exc
        if (
            manifest.snapshot_id != snapshot_id
            or snapshot_root.name != snapshot_id
            or manifest.sandbox_id != sandbox_id
            or manifest.subject_id != descriptor.subject_id
            or manifest.namespace_id != descriptor.namespace_id
            or manifest.environment is not SandboxEnvironment.TEST
            or manifest.promotion_allowed is not False
            or manifest.complete is not True
            or manifest.source_branch not in descriptor.branch_ids
            or manifest.manifest_hash != canonical_hash(manifest.unsigned_dict())
            or descriptor.snapshot_anchors.get(snapshot_id) != manifest.manifest_hash
        ):
            raise SandboxOperationError("SNAPSHOT_TAMPERED", "snapshot manifest is invalid")
        component_names = {item.name for item in manifest.components}
        if (
            component_names != REQUIRED_SNAPSHOT_COMPONENTS
            or len(manifest.components) != len(REQUIRED_SNAPSHOT_COMPONENTS)
        ):
            raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "snapshot lacks a required component")
        expected_logical_files = {
            f"{component.name}.json" for component in manifest.components
        }
        logical_root = snapshot_root / "logical"
        actual_logical_files = {
            path.name for path in logical_root.iterdir() if path.is_file()
        } if logical_root.is_dir() else set()
        if actual_logical_files != expected_logical_files:
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "snapshot logical inventory is inconsistent"
            )
        for component in manifest.components:
            if (
                component.snapshot_id != manifest.snapshot_id
                or component.source_branch != manifest.source_branch
                or component.created_at != manifest.created_at
                or not component.complete
            ):
                raise SandboxOperationError(
                    "SNAPSHOT_TAMPERED", "snapshot component identity is inconsistent"
                )
            _physical_path_entries(component.physical_path)
            logical_path = snapshot_root / "logical" / f"{component.name}.json"
            if not logical_path.is_file():
                raise SandboxOperationError("SNAPSHOT_TAMPERED", "snapshot logical file is missing")
            logical = read_json(logical_path)
            if logical.get("name") != component.name or canonical_hash(
                logical.get("payload")
            ) != component.canonical_content_hash:
                raise SandboxOperationError(
                    "SNAPSHOT_TAMPERED", "snapshot canonical component hash mismatch"
                )
        payload = snapshot_root / "payload"
        if not payload.is_dir():
            raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "snapshot payload is missing")
        manifest_inventory = [item.to_dict() for item in manifest.physical_inventory]
        if len(manifest_inventory) != len(
            {item["relativePath"] for item in manifest_inventory}
        ) or manifest_inventory != physical_file_inventory(payload):
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "snapshot physical inventory is inconsistent"
            )
        manifest_mapped_paths = [
            path
            for component in manifest.components
            for path in _physical_path_entries(component.physical_path)
        ]
        if len(manifest_mapped_paths) != len(set(manifest_mapped_paths)):
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "a physical file has duplicate component mappings"
            )
        if {item["relativePath"] for item in manifest_inventory} != set(
            manifest_mapped_paths
        ):
            raise SandboxOperationError(
                "SNAPSHOT_INCOMPLETE", "snapshot has unmapped physical files"
            )
        self._validate_payload_against_manifest(descriptor, manifest, payload)
        return manifest

    def create_branch(self, sandbox_id: str, snapshot_id: str) -> str:
        manifest = self.validate_snapshot(sandbox_id, snapshot_id)
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        original_descriptor = SandboxDescriptor.from_dict(descriptor.to_dict())
        branch_id = _id("p01-branch")
        branch_root = self._branch_root(sandbox_root, branch_id)
        snapshot_payload = sandbox_root / "n" / snapshot_id / "payload"
        try:
            copy_tree_without_links(
                snapshot_payload, branch_root / "data", boundary=sandbox_root
            )
            atomic_write_json(
                branch_root / BRANCH_MARKER,
                {
                    "formatVersion": 1,
                    "sandboxId": sandbox_id,
                    "branchId": branch_id,
                    "namespaceId": descriptor.namespace_id,
                    "environment": "TEST",
                    "synthetic": True,
                    "promotionAllowed": False,
                    "sourceSnapshotId": snapshot_id,
                },
            )
            self._validate_payload_against_manifest(
                descriptor, manifest, branch_root / "data"
            )
            descriptor.branch_ids.append(branch_id)
            descriptor.active_branch_id = branch_id
            descriptor.data_root = str(branch_root / "data")
            self._save_descriptor(descriptor)
            self._register(descriptor)
            return branch_id
        except Exception:
            if branch_root.exists():
                remove_tree_safely(branch_root, allowed_parent=sandbox_root / "b")
            self._save_descriptor(original_descriptor)
            self._register(original_descriptor)
            raise

    def rollback(
        self,
        sandbox_id: str,
        snapshot_id: str,
        *,
        fault: str | None = None,
    ) -> SnapshotManifest:
        manifest = self.validate_snapshot(sandbox_id, snapshot_id)
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        branch_id = descriptor.active_branch_id
        branch_root = self._branch_root(sandbox_root, branch_id)
        marker = self._validate_branch_marker(descriptor, branch_id, branch_root)
        if (
            branch_id != manifest.source_branch
            and marker["sourceSnapshotId"] != snapshot_id
        ):
            raise SandboxOperationError(
                "ROLLBACK_TARGET_INVALID",
                "the active branch was not created from the requested snapshot",
            )
        data_root = branch_root / "data"
        rollback_slug = _physical_id(snapshot_id, "r")
        staging = branch_root / f".{rollback_slug}s"
        backup = branch_root / f".{rollback_slug}b"
        if staging.exists() or backup.exists():
            raise SandboxOperationError("ROLLBACK_FAILED", "rollback workspace is not clean")
        snapshot_payload = sandbox_root / "n" / snapshot_id / "payload"
        copy_tree_without_links(snapshot_payload, staging, boundary=sandbox_root)
        self._validate_payload_against_manifest(descriptor, manifest, staging)
        moved_original = False
        installed_snapshot = False
        try:
            os.replace(data_root, backup)
            moved_original = True
            if fault == "after_original_moved":
                raise RuntimeError("injected rollback failure")
            os.replace(staging, data_root)
            installed_snapshot = True
            self._validate_payload_against_manifest(descriptor, manifest, data_root)
            remove_tree_safely(backup, allowed_parent=branch_root)
            return manifest
        except Exception as exc:
            try:
                if installed_snapshot and data_root.exists():
                    remove_tree_safely(data_root, allowed_parent=branch_root)
                if moved_original and backup.exists():
                    os.replace(backup, data_root)
                if staging.exists():
                    remove_tree_safely(staging, allowed_parent=branch_root)
            except Exception as recovery_exc:
                raise SandboxOperationError(
                    "ROLLBACK_FAILED", "rollback failed and original branch recovery failed"
                ) from recovery_exc
            raise SandboxOperationError(
                "ROLLBACK_FAILED", "rollback failed; the original branch was restored"
            ) from exc

    def execute_standard_interaction(
        self,
        sandbox_id: str,
        snapshot_id: str,
    ) -> SandboxInteractionProof:
        manifest = self.validate_snapshot(sandbox_id, snapshot_id)
        runtime = self.open_runtime(sandbox_id)
        if runtime.component_fingerprint() != _manifest_fingerprint(manifest):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "the sandbox is not at the requested snapshot point"
            )
        execution = runtime.execute_standard_interaction()
        result = execution.result
        projection = result.state_projection
        if (
            projection.changed is not True
            or projection.previous_revision != manifest.source_revision
            or projection.current_revision != manifest.source_revision + 1
            or projection.engine_update_id is None
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "standard interaction did not produce changed=true"
            )
        wake_sessions = runtime.awakening.list_sessions(runtime.descriptor.subject_id)
        think_sessions = runtime.thinking_repository.list_think_sessions(
            runtime.descriptor.subject_id
        )
        action_sessions = runtime.action_repository.list_action_sessions(
            runtime.descriptor.subject_id
        )
        operations = runtime.integration_ledger.list_operations()
        completed = runtime.integration_ledger.list_completed()
        changed_fingerprint = runtime.component_fingerprint()
        snapshot_fingerprint = _manifest_fingerprint(manifest)
        expected_changed_components = {
            "subject_state",
            "events",
            "state_mutations",
            "evolution",
            "relationship_state",
            "awake_cycle",
            "wake_sessions",
            "thinking_sessions",
            "action_sessions",
            "operation_journal",
            "completed_result_ledger",
            "test_trace",
        }
        required_calls = {
            "wake",
            "perception",
            "thinking",
            "action",
            "evolution",
            "result",
            "completed",
        }
        if (
            not wake_sessions
            or not think_sessions
            or not action_sessions
            or len(operations) != 1
            or len(completed) != 1
            or not required_calls.issubset(execution.call_log)
            or any(
                changed_fingerprint[name] == snapshot_fingerprint[name]
                for name in expected_changed_components
            )
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "standard interaction persistence is incomplete"
            )
        proof_id = _id("p01-interaction-proof")
        unsigned = SandboxInteractionProof(
            proof_id=proof_id,
            sandbox_id=sandbox_id,
            snapshot_id=snapshot_id,
            request_id=result.request_id,
            request_hash=result.request_hash,
            operation_id=result.operation_id,
            response_id=result.response.response_id,
            result_hash=canonical_hash(result.to_dict()),
            changed=True,
            previous_revision=projection.previous_revision,
            current_revision=projection.current_revision,
            engine_update_id=projection.engine_update_id,
            wake_session_ids=tuple(item.session_id for item in wake_sessions),
            think_session_ids=tuple(item.think_id for item in think_sessions),
            action_session_ids=tuple(item.action_session_id for item in action_sessions),
            standard_call_log=execution.call_log,
            snapshot_fingerprint=snapshot_fingerprint,
            changed_fingerprint=changed_fingerprint,
            created_at=runtime.clock.now(),
            proof_hash="pending",
        )
        proof = replace(unsigned, proof_hash=canonical_hash(unsigned.unsigned_dict()))
        proof_path = (
            runtime.branch_root.parents[1]
            / "acceptance"
            / "interactions"
            / f"{proof_id}.json"
        )
        atomic_write_json(proof_path, proof.to_dict())
        return proof

    def create_acceptance_receipt(
        self,
        sandbox_id: str,
        snapshot_id: str,
        interaction_proof_id: str,
        *,
        formal_inventory_before_hash: str,
        formal_inventory_after_hash: str,
    ) -> SandboxAcceptanceReceipt:
        manifest = self.validate_snapshot(sandbox_id, snapshot_id)
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        proof = self._load_interaction_proof(
            sandbox_root, interaction_proof_id
        )
        runtime = self.open_runtime(sandbox_id)
        restored = runtime.component_fingerprint()
        hashes_valid = all(
            isinstance(value, str)
            and value.startswith("sha256:")
            and len(value) == 71
            for value in (formal_inventory_before_hash, formal_inventory_after_hash)
        )
        if (
            proof.sandbox_id != sandbox_id
            or proof.snapshot_id != snapshot_id
            or proof.snapshot_fingerprint != _manifest_fingerprint(manifest)
            or proof.changed is not True
            or proof.engine_update_id is None
            or restored != proof.snapshot_fingerprint
            or descriptor.snapshot_anchors.get(snapshot_id) != manifest.manifest_hash
            or formal_inventory_before_hash != formal_inventory_after_hash
            or not hashes_valid
            or self.formal_access_count != 0
            or not runtime.repository_roots_authorized()
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "P01 round-trip acceptance is incomplete"
            )
        receipt_id = _id("p01-acceptance")
        unsigned = SandboxAcceptanceReceipt(
            receipt_id=receipt_id,
            sandbox_id=sandbox_id,
            snapshot_id=snapshot_id,
            interaction_proof_id=interaction_proof_id,
            request_id=proof.request_id,
            request_hash=proof.request_hash,
            operation_id=proof.operation_id,
            response_id=proof.response_id,
            result_hash=proof.result_hash,
            changed=True,
            previous_revision=proof.previous_revision,
            current_revision=proof.current_revision,
            engine_update_id=proof.engine_update_id,
            snapshot_fingerprint=proof.snapshot_fingerprint,
            changed_fingerprint=proof.changed_fingerprint,
            restored_fingerprint=restored,
            exact_restored=True,
            snapshot_anchor_hash=manifest.manifest_hash,
            standard_interaction_completed=True,
            formal_inventory_before_hash=formal_inventory_before_hash,
            formal_inventory_after_hash=formal_inventory_after_hash,
            formal_isolation_verified=True,
            repository_roots_authorized=True,
            created_at=runtime.clock.now(),
            receipt_hash="pending",
        )
        receipt = replace(unsigned, receipt_hash=canonical_hash(unsigned.unsigned_dict()))
        path = sandbox_root / "acceptance" / "receipts" / f"{receipt_id}.json"
        atomic_write_json(path, receipt.to_dict())
        original = SandboxDescriptor.from_dict(descriptor.to_dict())
        try:
            descriptor.acceptance_receipt_ids.append(receipt_id)
            self._save_descriptor(descriptor)
            self._register(descriptor)
        except Exception:
            if path.exists():
                path.unlink()
            self._save_descriptor(original)
            self._register(original)
            raise
        return receipt

    def _load_interaction_proof(
        self,
        sandbox_root: Path,
        proof_id: str,
    ) -> SandboxInteractionProof:
        path = sandbox_root / "acceptance" / "interactions" / f"{proof_id}.json"
        try:
            proof = SandboxInteractionProof.from_dict(read_json(path))
        except (KeyError, TypeError, ValueError) as exc:
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "interaction proof is invalid"
            ) from exc
        if proof.proof_id != proof_id or proof.proof_hash != canonical_hash(
            proof.unsigned_dict()
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "interaction proof is not authentic"
            )
        return proof

    def _load_acceptance_receipt(
        self,
        sandbox_root: Path,
        receipt_id: str,
    ) -> SandboxAcceptanceReceipt:
        path = sandbox_root / "acceptance" / "receipts" / f"{receipt_id}.json"
        try:
            receipt = SandboxAcceptanceReceipt.from_dict(read_json(path))
        except (KeyError, TypeError, ValueError) as exc:
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "acceptance receipt is invalid"
            ) from exc
        if receipt.receipt_id != receipt_id or receipt.receipt_hash != canonical_hash(
            receipt.unsigned_dict()
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "acceptance receipt is not authentic"
            )
        return receipt

    def retain_failure(
        self,
        sandbox_id: str,
        *,
        debug_for: timedelta | None = None,
    ) -> SandboxDescriptor:
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        now = self._maintenance_now()
        if debug_for is None:
            mode = RetentionMode.FAILURE_24_HOURS
            duration = FAILURE_RETENTION
        else:
            if debug_for.total_seconds() <= 0 or debug_for > MAX_DEBUG_RETENTION:
                raise SandboxOperationError(
                    "RETENTION_INVALID", "debug retention must be positive and at most seven days"
                )
            mode = RetentionMode.DEBUG
            duration = debug_for
        descriptor.retention_mode = mode
        descriptor.expires_at = now + duration
        descriptor.lifecycle = SandboxLifecycle.RETAINED
        self._save_descriptor(descriptor)
        self._register(descriptor)
        return self._load_descriptor(sandbox_root)

    def finalize_success(
        self,
        sandbox_id: str,
        acceptance_receipt_id: str | None = None,
    ) -> tuple[SandboxEvidence, CleanupResult]:
        descriptor, sandbox_root = self._load_registered(sandbox_id)
        if (
            acceptance_receipt_id is None
            or acceptance_receipt_id not in descriptor.acceptance_receipt_ids
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "a valid P01 round-trip receipt is required"
            )
        receipt = self._load_acceptance_receipt(
            sandbox_root, acceptance_receipt_id
        )
        runtime = self.open_runtime(sandbox_id, branch_id=descriptor.active_branch_id)
        manifest = self.validate_snapshot(sandbox_id, receipt.snapshot_id)
        restored = runtime.component_fingerprint()
        proof = self._load_interaction_proof(
            sandbox_root, receipt.interaction_proof_id
        )
        if (
            receipt.sandbox_id != sandbox_id
            or receipt.snapshot_id != manifest.snapshot_id
            or receipt.snapshot_anchor_hash != manifest.manifest_hash
            or receipt.changed is not True
            or receipt.engine_update_id is None
            or receipt.exact_restored is not True
            or receipt.standard_interaction_completed is not True
            or receipt.formal_isolation_verified is not True
            or receipt.repository_roots_authorized is not True
            or receipt.formal_inventory_before_hash
            != receipt.formal_inventory_after_hash
            or receipt.restored_fingerprint != restored
            or restored != _manifest_fingerprint(manifest)
            or proof.sandbox_id != sandbox_id
            or proof.snapshot_id != receipt.snapshot_id
            or proof.proof_id != receipt.interaction_proof_id
        ):
            raise SandboxOperationError(
                "ACCEPTANCE_NOT_READY", "the P01 acceptance receipt is inconsistent"
            )
        descriptor.retention_mode = RetentionMode.SUCCESS_AUTO_CLEAN
        descriptor.expires_at = self._maintenance_now()
        self._save_descriptor(descriptor)
        self._register(descriptor)
        state = runtime.subject_state()
        snapshot_hashes = tuple(
            self.validate_snapshot(sandbox_id, item).manifest_hash
            for item in descriptor.snapshot_ids
        )
        exported_at = self._maintenance_now()
        evidence = SandboxEvidence(
            evidence_id=_id("p01-evidence"),
            sandbox_id=sandbox_id,
            subject_id=descriptor.subject_id,
            environment=SandboxEnvironment.TEST,
            promotion_allowed=False,
            snapshot_hashes=snapshot_hashes,
            acceptance_receipt_id=receipt.receipt_id,
            acceptance_receipt_hash=receipt.receipt_hash,
            interaction_request_id=receipt.request_id,
            request_hash=receipt.request_hash,
            operation_id=receipt.operation_id,
            response_id=receipt.response_id,
            result_hash=receipt.result_hash,
            changed=receipt.changed,
            previous_revision=receipt.previous_revision,
            current_revision=receipt.current_revision,
            engine_update_id=receipt.engine_update_id,
            snapshot_component_fingerprint=receipt.snapshot_fingerprint,
            changed_component_fingerprint=receipt.changed_fingerprint,
            restored_component_fingerprint=receipt.restored_fingerprint,
            exact_restored=receipt.exact_restored,
            snapshot_anchor_hash=receipt.snapshot_anchor_hash,
            standard_interaction_completed=receipt.standard_interaction_completed,
            formal_isolation_verified=receipt.formal_isolation_verified,
            formal_inventory_before_hash=receipt.formal_inventory_before_hash,
            formal_inventory_after_hash=receipt.formal_inventory_after_hash,
            repository_roots_authorized=receipt.repository_roots_authorized,
            final_state_hash=calculate_state_hash(state),
            final_revision=state.revision,
            exported_at=exported_at,
            sandbox_removed=False,
        )
        evidence_path = self.evidence_root / f"{evidence.evidence_id}.json"
        atomic_write_json(evidence_path, evidence.to_dict())
        cleanup = self.cleanup(sandbox_id, reason="successful acceptance evidence exported")
        evidence = replace(evidence, sandbox_removed=cleanup.cleaned or cleanup.already_clean)
        atomic_write_json(evidence_path, evidence.to_dict())
        if sandbox_root.exists():
            raise SandboxOperationError("SANDBOX_CLEANUP_FAILED", "successful sandbox still exists")
        return evidence, cleanup

    def cleanup(self, sandbox_id: str, *, reason: str = "manual cleanup") -> CleanupResult:
        registry = self._registry()
        entry = registry["sandboxes"].get(sandbox_id)
        now = self._maintenance_now()
        if entry is None:
            raise SandboxOperationError("SANDBOX_NOT_REGISTERED", "cleanup target is unknown")
        if entry.get("lifecycle") == SandboxLifecycle.CLEANED.value:
            return CleanupResult(sandbox_id, False, True, reason, now)
        expected_root = self._sandbox_root(sandbox_id)
        if Path(entry.get("sandboxRoot", "")).resolve(strict=False) != expected_root.resolve(
            strict=False
        ):
            raise SandboxOperationError(
                "SANDBOX_CLEANUP_FORBIDDEN", "registered cleanup path is inconsistent"
            )
        descriptor = self._load_descriptor(expected_root)
        if (
            descriptor.sandbox_id != sandbox_id
            or descriptor.environment is not SandboxEnvironment.TEST
            or descriptor.synthetic is not True
            or descriptor.promotion_allowed is not False
        ):
            raise SandboxOperationError(
                "SANDBOX_CLEANUP_FORBIDDEN", "sandbox marker is missing or invalid"
            )
        self._validate_cleanup_target(expected_root)
        remove_tree_safely(expected_root, allowed_parent=self.sandboxes_root)
        entry["lifecycle"] = SandboxLifecycle.CLEANED.value
        entry["cleanedAt"] = format_utc(now)
        entry["cleanupReason"] = reason
        atomic_write_json(self.registry_path, registry)
        return CleanupResult(sandbox_id, True, False, reason, now)

    def scan_expired(self) -> list[CleanupResult]:
        if not self.registry_path.exists():
            return []
        now = self._maintenance_now()
        results: list[CleanupResult] = []
        for sandbox_id, entry in list(self._registry()["sandboxes"].items()):
            expires_at = entry.get("expiresAt")
            if (
                entry.get("lifecycle")
                in {SandboxLifecycle.ACTIVE.value, SandboxLifecycle.RETAINED.value}
                and isinstance(expires_at, str)
                and datetime.fromisoformat(expires_at[:-1] + "+00:00") <= now
            ):
                results.append(self.cleanup(sandbox_id, reason="expired retention"))
        return results

    def promote(self, sandbox_id: str) -> None:
        self._load_registered(sandbox_id)
        raise SandboxOperationError(
            "PROMOTION_FORBIDDEN", "P01 test subjects can never become formal subjects"
        )

    def _initialize_branch(
        self,
        descriptor: SandboxDescriptor,
        branch_root: Path,
        frozen_at: datetime,
    ) -> None:
        data_root = branch_root / "data"
        clock = SandboxFrozenClock.create(
            data_root / "clock" / "subject-clock.v1.json", frozen_at
        )
        subject_states = SubjectStateService(
            JsonSubjectStateRepository(data_root / "subject-state"), clock=clock.now
        )
        subject_states.create(descriptor.subject_id)
        fixture = SubjectBindingFixture(
            schema_version="subject-binding/p01-test-v1",
            binding_id=descriptor.binding_id,
            user_id=_id("p01-user"),
            assistant_id=_id("p01-assistant"),
            subject_id=descriptor.subject_id,
            binding_version=1,
            status="active",
            created_at=format_utc(clock.now()),
            effective_at=format_utc(clock.now()),
            replaced_binding_id=None,
        )
        binding = SubjectBinding.from_fixture(
            fixture,
            cycle_id=descriptor.cycle_id,
            binding_fixture_hash=calculate_binding_fixture_hash(fixture),
        )
        JsonSubjectBindingRepository(data_root).initialize(binding)
        JsonAwakeningRepository(data_root).save_cycle(
            AwakeCycle.manual(
                subject_id=descriptor.subject_id,
                created_at=clock.now(),
                cycle_id=descriptor.cycle_id,
            )
        )
        ledger = JsonIntegrationResultLedger(data_root)
        ledger.initialize_empty()
        ledger.initialize_capabilities()
        ResourceManager(JsonResourceRepository(data_root), clock=clock.now).create_resource_state(
            descriptor.subject_id,
            token_budget=10_000,
            compute_budget=1_000,
            current_mode=RuntimeMode.LOW_FREQUENCY,
            resource_id=_id("p01-resource"),
        )
        SandboxMemoryRepository(data_root).initialize(descriptor.subject_id)
        SandboxTraceRepository(data_root).initialize(descriptor.subject_id)
        SandboxActionRepository(data_root).initialize(descriptor.subject_id)
        for name in (
            "wake-sessions.v1.json",
            "thinking-sessions.v1.json",
            "events.v1.json",
            "state-mutations.v1.json",
            "evolution.v1.json",
            "relationship-state.v1.json",
        ):
            atomic_write_json(
                data_root / "test-indexes" / name,
                {
                    "formatVersion": 1,
                    "environment": "TEST",
                    "synthetic": True,
                    "subjectId": descriptor.subject_id,
                    "indexPurpose": name.removesuffix(".v1.json"),
                },
            )

    def _validate_payload_against_manifest(
        self,
        descriptor: SandboxDescriptor,
        manifest: SnapshotManifest,
        payload_root: Path,
    ) -> None:
        temporary_branch = payload_root.parent
        runtime = SandboxRuntime(
            descriptor=descriptor,
            branch_id=manifest.source_branch,
            branch_root=temporary_branch,
            access_recorder=self._record_access,
        )
        runtime.data_root = payload_root
        runtime.clock = SandboxFrozenClock(payload_root / "clock" / "subject-clock.v1.json")
        runtime.state_repository = JsonSubjectStateRepository(payload_root / "subject-state")
        runtime.subject_states = SubjectStateService(runtime.state_repository, clock=runtime.clock.now)
        runtime.awakening = JsonAwakeningRepository(payload_root)
        runtime.learning_repository = JsonLearningRepository(payload_root)
        runtime.learning = LearningService(runtime.learning_repository, clock=runtime.clock.now)
        runtime.resource_repository = JsonResourceRepository(payload_root)
        runtime.resources = ResourceManager(runtime.resource_repository, clock=runtime.clock.now)
        runtime.memory = SandboxMemoryRepository(payload_root)
        runtime.memory_service = MemoryService(
            runtime.memory,
            runtime.memory,
            clock=runtime.clock.now,
        )
        runtime.trace = SandboxTraceRepository(payload_root)
        runtime.binding_repository = JsonSubjectBindingRepository(payload_root)
        runtime.integration_ledger = JsonIntegrationResultLedger(payload_root)
        runtime.thinking_repository = JsonThinkingRepository(payload_root)
        runtime.action_repository = SandboxActionRepository(payload_root)
        runtime._assert_repository_roots_authorized()
        logical = runtime.logical_components()
        expected = {item.name: item for item in manifest.components}
        if set(logical) != set(expected):
            raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "payload components differ")
        inventory = physical_file_inventory(payload_root)
        if inventory != [item.to_dict() for item in manifest.physical_inventory]:
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "payload physical inventory differs"
            )
        if {item["relativePath"] for item in inventory} != _mapped_inventory(logical):
            raise SandboxOperationError(
                "SNAPSHOT_INCOMPLETE", "payload includes unmapped physical state"
            )
        if runtime.subject_state().revision != manifest.source_revision:
            raise SandboxOperationError(
                "SNAPSHOT_TAMPERED", "payload revision differs from its manifest"
            )
        for name, item in logical.items():
            component = expected[name]
            if (
                canonical_hash(item["payload"]) != component.canonical_content_hash
                or _aggregate_file_hash(payload_root, item["physicalPath"])
                != component.file_hash
                or item["physicalPath"] != component.physical_path
                or item["revision"] != component.revision
                or item["count"] != component.count
            ):
                raise SandboxOperationError(
                    "SNAPSHOT_TAMPERED", f"payload component does not match: {name}"
                )

    def _validate_base_root(self) -> None:
        if self.base_root == Path(self.base_root.anchor):
            raise SandboxOperationError("SANDBOX_ROOT_FORBIDDEN", "filesystem root is forbidden")
        if self.base_root == self._home_root or self.base_root in self._home_root.parents:
            raise SandboxOperationError(
                "SANDBOX_ROOT_FORBIDDEN", "the user home or one of its parents is forbidden"
            )
        for protected in self._isolation_paths:
            if self.base_root == protected or self.base_root in protected.parents or protected in self.base_root.parents:
                raise SandboxOperationError(
                    "SANDBOX_ROOT_FORBIDDEN",
                    "sandbox root overlaps a repository, formal, or protected path",
                )
        existing = self.base_root
        while not existing.exists() and existing.parent != existing:
            existing = existing.parent
        if is_link_like(existing):
            raise SandboxOperationError(
                "SANDBOX_ROOT_FORBIDDEN", "sandbox root is below a link or junction"
            )

    def _initialize_root(self) -> None:
        self.base_root.mkdir(parents=True, exist_ok=True)
        self.sandboxes_root.mkdir(exist_ok=True)
        self.evidence_root.mkdir(exist_ok=True)
        marker = self.base_root / P01_ROOT_MARKER
        if marker.exists():
            value = read_json(marker)
            if value != {
                "formatVersion": self.ROOT_FORMAT_VERSION,
                "environment": "TEST",
                "purpose": "continuity-engine-p01-sandboxes",
            }:
                raise SandboxOperationError("SANDBOX_ROOT_INVALID", "root marker conflicts")
        else:
            if any(self.base_root.iterdir()):
                entries = {item.name for item in self.base_root.iterdir()}
                if entries - {"s", "evidence"}:
                    raise SandboxOperationError(
                        "SANDBOX_ROOT_INVALID", "unmarked sandbox root is not empty"
                    )
            atomic_write_json(
                marker,
                {
                    "formatVersion": self.ROOT_FORMAT_VERSION,
                    "environment": "TEST",
                    "purpose": "continuity-engine-p01-sandboxes",
                },
            )
        if not self.registry_path.exists():
            atomic_write_json(
                self.registry_path,
                {"formatVersion": self.REGISTRY_FORMAT_VERSION, "sandboxes": {}},
            )
        self._registry()

    def _registry(self) -> dict[str, Any]:
        value = read_json(self.registry_path)
        if value.get("formatVersion") != self.REGISTRY_FORMAT_VERSION or not isinstance(
            value.get("sandboxes"), dict
        ):
            raise SandboxOperationError("SANDBOX_REGISTRY_INVALID", "registry is invalid")
        return value

    def _register(self, descriptor: SandboxDescriptor) -> None:
        registry = self._registry()
        sandbox_root = self._sandbox_root(descriptor.sandbox_id)
        registry["sandboxes"][descriptor.sandbox_id] = {
            "sandboxRoot": str(sandbox_root),
            "environment": "TEST",
            "synthetic": True,
            "promotionAllowed": False,
            "lifecycle": descriptor.lifecycle.value,
            "expiresAt": format_utc(descriptor.expires_at) if descriptor.expires_at else None,
            "snapshotAnchors": dict(sorted(descriptor.snapshot_anchors.items())),
            "descriptorHash": canonical_hash(descriptor.to_dict()),
        }
        atomic_write_json(self.registry_path, registry)

    def _remove_registry_entry(self, sandbox_id: str) -> None:
        registry = self._registry()
        registry["sandboxes"].pop(sandbox_id, None)
        atomic_write_json(self.registry_path, registry)

    def _save_descriptor(self, descriptor: SandboxDescriptor) -> None:
        sandbox_root = self._sandbox_root(descriptor.sandbox_id)
        assert_descendant(sandbox_root, self.sandboxes_root)
        atomic_write_json(sandbox_root / SANDBOX_MARKER, descriptor.to_dict())

    def _load_descriptor(self, sandbox_root: Path) -> SandboxDescriptor:
        marker = sandbox_root / SANDBOX_MARKER
        if not marker.is_file() or is_link_like(marker):
            raise SandboxOperationError("SANDBOX_MARKER_MISSING", "sandbox marker is missing")
        try:
            return SandboxDescriptor.from_dict(read_json(marker))
        except (KeyError, TypeError, ValueError) as exc:
            raise SandboxOperationError("SANDBOX_MARKER_INVALID", "sandbox marker is invalid") from exc

    def _load_registered(self, sandbox_id: str) -> tuple[SandboxDescriptor, Path]:
        if not isinstance(sandbox_id, str) or not sandbox_id.strip():
            raise SandboxOperationError("SANDBOX_NOT_REGISTERED", "sandbox id is invalid")
        registry = self._registry()
        entry = registry["sandboxes"].get(sandbox_id)
        if entry is None or entry.get("lifecycle") == SandboxLifecycle.CLEANED.value:
            raise SandboxOperationError("SANDBOX_NOT_REGISTERED", "sandbox is not active")
        sandbox_root = self._sandbox_root(sandbox_id)
        if Path(entry.get("sandboxRoot", "")).resolve(strict=False) != sandbox_root.resolve(
            strict=False
        ):
            raise SandboxOperationError("SANDBOX_REGISTRY_INVALID", "registered path mismatch")
        self._validate_cleanup_target(sandbox_root)
        descriptor = self._load_descriptor(sandbox_root)
        if canonical_hash(descriptor.to_dict()) != entry.get("descriptorHash"):
            raise SandboxOperationError("SANDBOX_REGISTRY_INVALID", "descriptor hash mismatch")
        if entry.get("snapshotAnchors", {}) != dict(
            sorted(descriptor.snapshot_anchors.items())
        ):
            raise SandboxOperationError("SANDBOX_REGISTRY_INVALID", "snapshot anchors mismatch")
        return descriptor, sandbox_root

    def _validate_cleanup_target(self, sandbox_root: Path) -> None:
        if sandbox_root.parent.resolve(strict=False) != self.sandboxes_root.resolve(strict=False):
            raise SandboxOperationError(
                "SANDBOX_CLEANUP_FORBIDDEN", "cleanup target is not a direct registered child"
            )
        assert_descendant(sandbox_root, self.sandboxes_root)
        assert_no_link_components(sandbox_root, stop_at=self.sandboxes_root)
        if sandbox_root == self._home_root or sandbox_root in self._home_root.parents:
            raise SandboxOperationError(
                "SANDBOX_CLEANUP_FORBIDDEN", "cleanup cannot target home or its parent"
            )
        if any(
            sandbox_root.resolve(strict=False) == path
            or path in sandbox_root.resolve(strict=False).parents
            or sandbox_root.resolve(strict=False) in path.parents
            for path in self._isolation_paths
        ):
            raise SandboxOperationError(
                "SANDBOX_CLEANUP_FORBIDDEN", "cleanup target overlaps a protected path"
            )

    def _validate_branch_marker(
        self, descriptor: SandboxDescriptor, branch_id: str, branch_root: Path
    ) -> dict[str, Any]:
        marker = read_json(branch_root / BRANCH_MARKER)
        source_snapshot_id = marker.get("sourceSnapshotId")
        if source_snapshot_id is not None and (
            not isinstance(source_snapshot_id, str) or not source_snapshot_id.strip()
        ):
            raise SandboxOperationError("SANDBOX_BRANCH_INVALID", "branch marker is invalid")
        if marker != {
            "formatVersion": 1,
            "sandboxId": descriptor.sandbox_id,
            "branchId": branch_id,
            "namespaceId": descriptor.namespace_id,
            "environment": "TEST",
            "synthetic": True,
            "promotionAllowed": False,
            "sourceSnapshotId": source_snapshot_id,
        }:
            raise SandboxOperationError("SANDBOX_BRANCH_INVALID", "branch marker is invalid")
        return marker

    def _record_access(self, path: Path, kind: str) -> None:
        self._accesses.append((path.resolve(strict=False), kind))

    def _maintenance_now(self) -> datetime:
        value = self._maintenance_clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise SandboxOperationError(
                "MAINTENANCE_CLOCK_INVALID", "maintenance clock must be timezone-aware"
            )
        return value.astimezone(timezone.utc)
