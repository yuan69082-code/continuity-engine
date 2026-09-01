import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.errors import (
    LearningValidationError,
    MemoryEvidenceConflictError,
    MemoryIdentityConflictError,
    MemoryInfluenceError,
    MemoryLineageError,
    MemoryPersistenceError,
    MemoryValidationError,
)
from continuity_engine.domain.events import ChangeOperation, StateMutation
from continuity_engine.domain.memory import (
    DerivedSummaryStatus,
    MemoryActivationConfig,
    MemoryActivationPolicy,
    MemoryEvidenceType,
    MemoryKind,
    MemoryLineageType,
    MemoryRecord,
    MemoryStatus,
    MemoryTemperature,
    MemoryTimeRange,
    MemoryVisibility,
)
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.memory_consolidation_service import (
    MemoryConsolidationService,
)
from continuity_engine.services.memory_service import (
    MemoryService,
    RepositoryMemoryRetriever,
)
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.domain.memory import MemoryRetrievalRequest
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p04_memory_fixture import (
    P04_GOLDEN_SCENARIO_VERSION,
    run_p04_golden_scenario,
)


UTC = timezone.utc


class _InfluenceRecorder:
    def __init__(self) -> None:
        self.records = []

    def record_influence(self, record) -> None:
        self.records.append(record)


class P04MemoryConsolidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
        self.repository = JsonMemoryRepository(self.root, environment="TEST")
        self.service = MemoryConsolidationService(
            self.repository, clock=lambda: self.now
        )

    def memory(
        self,
        memory_id: str,
        root: str,
        *,
        content: str = "The relationship was reconciled.",
        scope: str = "relationship:current",
        kind: MemoryKind = MemoryKind.RELATIONAL,
        consolidation_id: str | None = None,
        importance: float = 0.8,
        relation_relevance: float = 0.9,
        emotional_weight: float = 0.4,
        occurred_at: datetime | None = None,
        subject_id: str = "subject-1",
        environment: str = "TEST",
        source_event_ids: list[str] | None = None,
        source_memory_ids: list[str] | None = None,
        root_evidence_ids: list[str] | None = None,
    ) -> MemoryRecord:
        occurred = occurred_at or self.now - timedelta(days=1)
        return MemoryRecord(
            memory_id=memory_id,
            subject_id=subject_id,
            environment=environment,
            kind=kind,
            evidence_type=MemoryEvidenceType.EXPERIENTIAL,
            content=content,
            root_evidence_ids=root_evidence_ids or [root],
            source_event_ids=(
                source_event_ids
                if source_event_ids is not None
                else ([] if source_memory_ids else [root.removeprefix("event:")])
            ),
            source_memory_ids=source_memory_ids or [],
            occurred_at=occurred,
            observed_at=occurred + timedelta(minutes=1),
            recorded_at=occurred + timedelta(minutes=2),
            consolidated_at=max(self.now, occurred + timedelta(minutes=3)),
            confidence=0.8,
            importance=importance,
            activation=0.0,
            scope=scope,
            time_range=MemoryTimeRange(occurred, occurred),
            tags=["p04", "synthetic"],
            visibility=MemoryVisibility.ENGINE_PRIVATE,
            relation_relevance=relation_relevance,
            emotional_weight=emotional_weight,
            consolidation_id=consolidation_id or f"consolidation:{memory_id}:{root}",
        )

    def test_consolidation_exact_replay_and_identity_conflict(self) -> None:
        candidate = self.memory("memory-1", "event:one")
        first = self.service.consolidate(candidate)
        replay = self.service.consolidate(MemoryRecord.from_dict(candidate.to_dict()))
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(self.repository.memory_history("subject-1", "memory-1")), 1)

        payload = candidate.to_dict()
        payload["content"] = "A conflicting consolidation body."
        payload["consolidation_input_hash"] = None
        with self.assertRaises(MemoryIdentityConflictError):
            self.service.consolidate(MemoryRecord.from_dict(payload))

    def test_duplicate_root_does_not_reinforce_but_independent_root_does(self) -> None:
        first = self.service.consolidate(self.memory("memory-1", "event:one")).memory
        duplicate = self.service.consolidate(
            self.memory("memory-alias", "event:one", consolidation_id="consolidation:alias")
        )
        second_candidate = self.memory(
            "memory-other", "event:two", consolidation_id="consolidation:two"
        )
        reinforced = self.service.consolidate(second_candidate)
        restarted = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: self.now
        )
        replayed_reinforcement = restarted.consolidate(
            MemoryRecord.from_dict(second_candidate.to_dict())
        )

        self.assertTrue(duplicate.idempotent_replay)
        self.assertEqual(duplicate.unique_evidence_added, 0)
        self.assertEqual(reinforced.memory.memory_id, first.memory_id)
        self.assertEqual(reinforced.memory.unique_evidence_count, 2)
        self.assertTrue(replayed_reinforcement.idempotent_replay)
        self.assertEqual(replayed_reinforcement.memory.unique_evidence_count, 2)
        self.assertEqual(len(self.repository.list_memories("subject-1")), 1)

    def test_duplicate_root_alias_operation_is_durable_and_conflicting_input_fails(self) -> None:
        original = self.service.consolidate(self.memory("memory-1", "event:one")).memory
        alias = self.memory(
            "memory-alias", "event:one", consolidation_id="consolidation:alias"
        )
        first_alias = self.service.consolidate(alias)
        operation = self.repository.load_consolidation_operation(
            "subject-1", "consolidation:alias"
        )
        self.assertTrue(first_alias.idempotent_replay)
        self.assertIsNotNone(operation)
        self.assertEqual(operation.result_memory_id, original.memory_id)

        restarted = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: self.now
        )
        replay = restarted.consolidate(MemoryRecord.from_dict(alias.to_dict()))
        before = self.repository.load_memory("subject-1", original.memory_id)
        with self.assertRaises(MemoryIdentityConflictError):
            restarted.consolidate(
                self.memory(
                    "memory-alias-two",
                    "event:two",
                    consolidation_id="consolidation:alias",
                )
            )
        after = self.repository.load_memory("subject-1", original.memory_id)

        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.memory.memory_id, original.memory_id)
        self.assertEqual(before.canonical_hash(), after.canonical_hash())
        self.assertEqual(len(self.repository.memory_history("subject-1", original.memory_id)), 1)

    def test_operation_replay_returns_its_exact_result_revision_across_restart(self) -> None:
        first_candidate = self.memory(
            "memory-1", "event:one", consolidation_id="consolidation:c1"
        )
        second_candidate = self.memory(
            "memory-2", "event:two", consolidation_id="consolidation:c2"
        )
        first = self.service.consolidate(first_candidate).memory
        second = self.service.consolidate(second_candidate).memory

        self.assertEqual((first.revision, second.revision), (0, 1))
        replay_first = self.service.consolidate(
            MemoryRecord.from_dict(first_candidate.to_dict())
        )
        restarted = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: self.now
        )
        restarted_first = restarted.consolidate(
            MemoryRecord.from_dict(first_candidate.to_dict())
        )
        restarted_second = restarted.consolidate(
            MemoryRecord.from_dict(second_candidate.to_dict())
        )

        for replay in (replay_first, restarted_first):
            self.assertTrue(replay.idempotent_replay)
            self.assertEqual(replay.memory.revision, 0)
            self.assertEqual(replay.memory.canonical_hash(), first.canonical_hash())
        self.assertTrue(restarted_second.idempotent_replay)
        self.assertEqual(restarted_second.memory.revision, 1)
        self.assertEqual(restarted_second.memory.canonical_hash(), second.canonical_hash())
        self.assertEqual(
            len(self.repository.memory_history("subject-1", first.memory_id)), 2
        )

    def test_operation_replay_survives_later_terminal_propagation(self) -> None:
        first_candidate = self.memory(
            "memory-1", "event:one", consolidation_id="consolidation:c1"
        )
        second_candidate = self.memory(
            "memory-2", "event:two", consolidation_id="consolidation:c2"
        )
        first = self.service.consolidate(first_candidate).memory
        second = self.service.consolidate(second_candidate).memory
        terminal = self.service.propagate_signal(
            "subject-1",
            lineage_id="lineage:revoke",
            target_memory_id=second.memory_id,
            signal=MemoryLineageType.REVOCATION,
            source_event_id="revoke",
            root_evidence_ids=["event:revoke"],
        ).memory
        restarted = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: self.now
        )

        replay_first = restarted.consolidate(
            MemoryRecord.from_dict(first_candidate.to_dict())
        )
        replay_second = restarted.consolidate(
            MemoryRecord.from_dict(second_candidate.to_dict())
        )
        self.assertEqual(terminal.status, MemoryStatus.REVOKED)
        self.assertEqual(terminal.revision, 2)
        self.assertEqual(replay_first.memory.canonical_hash(), first.canonical_hash())
        self.assertEqual(replay_second.memory.canonical_hash(), second.canonical_hash())
        self.assertEqual((replay_first.memory.revision, replay_second.memory.revision), (0, 1))

    def test_alias_candidate_source_memory_must_be_prior_and_same_boundary(self) -> None:
        original = self.service.consolidate(
            self.memory("memory-1", "event:one")
        ).memory
        foreign = self.memory(
            "foreign-source",
            "event:one",
            subject_id="subject-2",
            scope="scope:foreign",
        )
        self.repository.save_memory(foreign)
        future = self.memory(
            "future-source",
            "event:one",
            occurred_at=self.now + timedelta(hours=1),
            scope="scope:future",
        )
        self.repository.save_memory(future)

        cases = {
            "missing": "missing-source",
            "cross_subject": foreign.memory_id,
            "forward": future.memory_id,
        }
        for label, source_memory_id in cases.items():
            with self.subTest(label=label), self.assertRaises(MemoryPersistenceError):
                self.service.consolidate(
                    self.memory(
                        f"alias-{label}",
                        "event:one",
                        consolidation_id=f"consolidation:alias:{label}",
                        source_event_ids=[],
                        source_memory_ids=[source_memory_id],
                    )
                )
        with self.assertRaises(MemoryValidationError):
            self.service.consolidate(
                self.memory(
                    "alias-cross-environment",
                    "event:one",
                    consolidation_id="consolidation:alias:cross-environment",
                    environment="RESEARCH",
                    source_memory_ids=[original.memory_id],
                )
            )

    def test_alias_candidate_uses_its_own_traceable_source_chain(self) -> None:
        original = self.service.consolidate(
            self.memory("memory-1", "event:one")
        ).memory
        legal_alias = self.memory(
            "memory-alias",
            "event:one",
            consolidation_id="consolidation:alias:legal",
            source_event_ids=[],
            source_memory_ids=[original.memory_id],
        )
        first = self.service.consolidate(legal_alias)
        restarted = MemoryConsolidationService(
            JsonMemoryRepository(self.root, environment="TEST"), clock=lambda: self.now
        )
        replay = restarted.consolidate(MemoryRecord.from_dict(legal_alias.to_dict()))

        self.assertTrue(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(replay.memory.canonical_hash(), original.canonical_hash())
        self.assertEqual(
            len(self.repository.memory_history("subject-1", original.memory_id)), 1
        )

        untraceable = self.memory(
            "memory-alias-untraceable",
            "event:one",
            consolidation_id="consolidation:alias:untraceable",
            source_event_ids=[],
            source_memory_ids=[original.memory_id],
            root_evidence_ids=["event:one", "event:forged"],
        )
        with self.assertRaises(MemoryPersistenceError):
            restarted.consolidate(untraceable)

    def test_conflicting_evidence_is_not_silently_merged(self) -> None:
        self.service.consolidate(self.memory("memory-1", "event:one"))
        with self.assertRaises(MemoryEvidenceConflictError):
            self.service.consolidate(
                self.memory(
                    "memory-2",
                    "event:two",
                    content="The relationship remained in conflict.",
                )
            )
        self.assertEqual(len(self.repository.list_memories("subject-1")), 1)

    def test_activation_is_explicit_configurable_and_never_deletes(self) -> None:
        policy = MemoryActivationPolicy(
            MemoryActivationConfig(
                hot_threshold=0.7,
                warm_threshold=0.4,
                cold_threshold=0.1,
                hot_capacity=1,
                warm_capacity=1,
                cold_capacity=1,
                decay_days=30,
            )
        )
        service = MemoryConsolidationService(
            self.repository, clock=lambda: self.now, activation_policy=policy
        )
        for index in range(4):
            service.consolidate(
                self.memory(
                    f"memory-{index}",
                    f"event:{index}",
                    scope=f"scope:{index}",
                    importance=1.0 - index * 0.1,
                    occurred_at=self.now - timedelta(days=index * 10),
                )
            )
        before_versions = sum(
            len(self.repository.memory_history("subject-1", f"memory-{index}"))
            for index in range(4)
        )
        service.recalculate_activation("subject-1")
        records = self.repository.list_memories("subject-1")

        self.assertEqual(len(records), 4)
        self.assertEqual({item.status for item in records}, {MemoryStatus.ACTIVE})
        self.assertIn(MemoryTemperature.ARCHIVED, {item.temperature for item in records})
        self.assertGreaterEqual(
            sum(
                len(self.repository.memory_history("subject-1", f"memory-{index}"))
                for index in range(4)
            ),
            before_versions,
        )
        self.assertEqual(list(self.root.rglob("*deleted*")), [])

    def test_summary_trace_invalidation_and_rebuild_are_append_only(self) -> None:
        argument = self.service.consolidate(
            self.memory(
                "argument",
                "event:argument",
                content="An argument occurred.",
                scope="relationship:argument",
            )
        ).memory
        reconciliation = self.service.consolidate(
            self.memory(
                "reconciliation",
                "event:reconciliation",
                content="A reconciliation was completed.",
                scope="relationship:reconciliation",
            )
        ).memory
        summary = self.service.generate_summary(
            "subject-1",
            summary_id="summary-relationship",
            summary_type="relationship.day",
            scope="relationship:day",
            source_memory_ids=[argument.memory_id, reconciliation.memory_id],
            confidence=0.9,
        )
        traced, sources = self.service.trace_summary("subject-1", summary.summary_id)
        self.assertEqual(traced.canonical_hash(), summary.canonical_hash())
        self.assertEqual([item.memory_id for item in sources], ["argument", "reconciliation"])

        propagated = self.service.propagate_signal(
            "subject-1",
            lineage_id="lineage-revoke-argument",
            target_memory_id="argument",
            signal=MemoryLineageType.REVOCATION,
            source_event_id="event:argument-revoked",
            root_evidence_ids=["event:argument-revoked"],
        )
        self.assertEqual(propagated.memory.status, MemoryStatus.REVOKED)
        self.assertEqual(len(propagated.invalidated_summaries), 1)
        self.assertEqual(
            self.repository.load_summary("subject-1", summary.summary_id).status,
            DerivedSummaryStatus.INVALIDATED,
        )
        rebuilt = self.service.generate_summary(
            "subject-1",
            summary_id="summary-relationship",
            summary_type="relationship.day",
            scope="relationship:day",
            source_memory_ids=[reconciliation.memory_id],
            confidence=0.9,
        )
        self.assertEqual(rebuilt.status, DerivedSummaryStatus.ACTIVE)
        self.assertGreater(rebuilt.summary_version, summary.summary_version)
        self.assertNotIn("argument", rebuilt.content.casefold())
        self.assertEqual(len(self.repository.summary_history("subject-1", summary.summary_id)), 3)

    def test_correction_revocation_and_deletion_are_tombstones_not_physical_delete(self) -> None:
        for signal in MemoryLineageType:
            with self.subTest(signal=signal), tempfile.TemporaryDirectory() as directory:
                repository = JsonMemoryRepository(directory, environment="TEST")
                service = MemoryConsolidationService(repository, clock=lambda: self.now)
                service.consolidate(self.memory("target", "event:target"))
                result = service.propagate_signal(
                    "subject-1",
                    lineage_id=f"lineage:{signal.value}",
                    target_memory_id="target",
                    signal=signal,
                    source_event_id=f"event:{signal.value}",
                    root_evidence_ids=[f"event:{signal.value}"],
                )
                self.assertEqual(len(repository.memory_history("subject-1", "target")), 2)
                self.assertEqual(len(repository.list_lineage("subject-1")), 1)
                self.assertEqual(repository.list_memories("subject-1"), [])
                self.assertEqual(len(repository.list_memories("subject-1", include_inactive=True)), 1)
                replay = service.propagate_signal(
                    "subject-1",
                    lineage_id=f"lineage:{signal.value}",
                    target_memory_id="target",
                    signal=signal,
                    source_event_id=f"event:{signal.value}",
                    root_evidence_ids=[f"event:{signal.value}"],
                )
                self.assertTrue(replay.idempotent_replay)

    def test_repository_retriever_is_read_only_feature_gated_and_engine_private(self) -> None:
        memory = self.service.consolidate(self.memory("memory-1", "event:one")).memory
        before = [path.read_bytes() for path in self.root.rglob("*.json")]
        request = MemoryRetrievalRequest.create(
            request_id="request-1",
            subject_id="subject-1",
            query="relationship reconciled",
            requested_at=self.now,
            minimum_relevance=0,
        )
        recorder = _InfluenceRecorder()
        enabled = MemoryService(RepositoryMemoryRetriever(self.repository), recorder, clock=lambda: self.now)
        result = enabled.retrieve(request)
        disabled = RepositoryMemoryRetriever(self.repository, enabled=False).retrieve(request)
        after = [path.read_bytes() for path in self.root.rglob("*.json")]

        self.assertEqual([item.memory_id for item in result.selected_memories], [memory.memory_id])
        self.assertEqual(result.selected_memories[0].metadata["visibility"], "ENGINE_PRIVATE")
        self.assertEqual(disabled, [])
        self.assertEqual(before, after)

    def test_repository_retriever_excludes_archived_without_deleting_or_writing(self) -> None:
        expected = []
        for temperature in MemoryTemperature:
            memory = self.memory(
                f"memory-{temperature.value.lower()}",
                f"event:{temperature.value.lower()}",
                scope=f"scope:{temperature.value.lower()}",
            )
            payload = memory.to_dict()
            payload["temperature"] = temperature.value
            stored = MemoryRecord.from_dict(payload)
            self.repository.save_memory(stored)
            if temperature is not MemoryTemperature.ARCHIVED:
                expected.append(stored.memory_id)
        before = [path.read_bytes() for path in self.root.rglob("*.json")]
        request = MemoryRetrievalRequest.create(
            request_id="request-temperatures",
            subject_id="subject-1",
            query="relationship",
            requested_at=self.now,
            minimum_relevance=0,
            limit=10,
        )
        retrieved = RepositoryMemoryRetriever(self.repository).retrieve(request)
        after = [path.read_bytes() for path in self.root.rglob("*.json")]

        self.assertEqual({item.memory_id for item in retrieved}, set(expected))
        self.assertEqual(
            self.repository.load_memory("subject-1", "memory-archived").temperature,
            MemoryTemperature.ARCHIVED,
        )
        self.assertEqual(
            RepositoryMemoryRetriever(self.repository, enabled=False).retrieve(request), []
        )
        self.assertEqual(before, after)

    def test_influence_provenance_is_sealed_and_learning_deduplicates_after_restart(self) -> None:
        first = self.service.consolidate(
            self.memory("memory-a", "event:real", scope="scope:a")
        ).memory
        second = self.service.consolidate(
            self.memory("memory-b", "event:real", scope="scope:b")
        ).memory
        request = MemoryRetrievalRequest.create(
            request_id="request-provenance",
            subject_id="subject-1",
            query="relationship reconciled",
            requested_at=self.now,
            minimum_relevance=0,
            limit=10,
        )
        recorder = _InfluenceRecorder()
        service = MemoryService(
            RepositoryMemoryRetriever(self.repository), recorder, clock=lambda: self.now
        )
        result = service.retrieve(request)
        for forged in (["event:forged"], [], "event:real", None):
            with self.subTest(forged=forged), self.assertRaises(MemoryInfluenceError):
                service.record_influence(
                    result,
                    memory_id=first.memory_id,
                    influence_type="learning",
                    summary="Rejected provenance override.",
                    reason="Formal provenance is sealed.",
                    metadata={"root_evidence_ids": forged},
                )
        first_influence = service.record_influence(
            result,
            memory_id=first.memory_id,
            influence_type="learning",
            summary="First sealed influence.",
            reason="Use the formal memory root.",
        )
        second_influence = service.record_influence(
            result,
            memory_id=second.memory_id,
            influence_type="learning",
            summary="Second sealed influence.",
            reason="Use the same formal memory root.",
        )
        self.assertEqual(first_influence.metadata["root_evidence_ids"], ["event:real"])
        self.assertEqual(second_influence.metadata["root_evidence_ids"], ["event:real"])

        def learning_candidate(learning: LearningService, memory_id: str, roots: list[str]):
            return learning.create_candidate(
                "subject-1",
                source_event_id=None,
                source_memory_id=memory_id,
                root_evidence_ids=roots,
                related_state_revision=0,
                observation="A durable preference was explicitly evaluated.",
                hypothesis="A concise response preference is useful.",
                proposed_change=StateMutation(
                    "identity.expression_preferences",
                    ChangeOperation.APPEND,
                    "prefers concise responses",
                    "Use explicit evidence only.",
                ),
                confidence=0.7,
                original_experience={"memory_id": memory_id},
                reason="Test sealed root evidence identity.",
                source="p04-test",
            )

        learning = LearningService(JsonLearningRepository(self.root), clock=lambda: self.now)
        one = learning_candidate(
            learning, first.memory_id, list(first_influence.metadata["root_evidence_ids"])
        )
        restarted = LearningService(
            JsonLearningRepository(self.root), clock=lambda: self.now
        )
        alias = learning_candidate(
            restarted, second.memory_id, list(second_influence.metadata["root_evidence_ids"])
        )
        independent = learning_candidate(restarted, "memory-c", ["event:independent"])
        with self.assertRaises(LearningValidationError):
            restarted.validate_learning(
                "subject-1",
                one.learning_event.learning_id,
                [alias.learning_event.learning_id, independent.learning_event.learning_id],
                reason="One aliased root and one independent root are only two roots.",
                source="p04-test",
            )

    def test_consolidation_and_summary_have_no_subject_state_or_event_write_authority(self) -> None:
        states = SubjectStateService(
            JsonSubjectStateRepository(self.root), clock=lambda: self.now
        )
        before = states.create("subject-1")
        memory = self.service.consolidate(self.memory("memory-1", "event:one")).memory
        self.service.generate_summary(
            "subject-1",
            summary_id="summary-1",
            summary_type="topic.test",
            scope="topic:test",
            source_memory_ids=[memory.memory_id],
            confidence=0.8,
        )
        after = states.load("subject-1")

        self.assertEqual(after.to_dict(), before.to_dict())
        self.assertEqual(after.revision, 0)
        self.assertEqual(states.get_update_history("subject-1"), [])

    def test_learning_deduplicates_root_evidence_across_memory_identities(self) -> None:
        learning = LearningService(JsonLearningRepository(self.root), clock=lambda: self.now)

        def candidate(memory_id: str, root: str):
            return learning.create_candidate(
                "subject-1",
                source_event_id=None,
                source_memory_id=memory_id,
                root_evidence_ids=[root],
                related_state_revision=0,
                observation="A durable preference was explicitly evaluated.",
                hypothesis="A concise response preference is useful.",
                proposed_change=StateMutation(
                    "identity.expression_preferences",
                    ChangeOperation.APPEND,
                    "prefers concise responses",
                    "Use explicit evidence only.",
                ),
                confidence=0.7,
                original_experience={"memory_id": memory_id},
                reason="Test root evidence identity.",
                source="p04-test",
            )

        first = candidate("memory-a", "event:one")
        alias = candidate("memory-b", "event:one")
        third = candidate("memory-c", "event:two")
        with self.assertRaises(LearningValidationError):
            learning.validate_learning(
                "subject-1",
                first.learning_event.learning_id,
                [alias.learning_event.learning_id, third.learning_event.learning_id],
                reason="Aliased evidence must not count twice.",
                source="p04-test",
            )

        fourth = candidate("memory-d", "event:three")
        validated = learning.validate_learning(
            "subject-1",
            first.learning_event.learning_id,
            [third.learning_event.learning_id, fourth.learning_event.learning_id],
            reason="Three independent roots support validation.",
            source="p04-test",
        )
        self.assertEqual(len(validated.learning_event.root_evidence_ids), 3)

    def test_summary_identity_and_semantic_inputs_are_not_silently_reused(self) -> None:
        first_memory = self.service.consolidate(
            self.memory("memory-1", "event:one", scope="scope:one")
        ).memory
        summary = self.service.generate_summary(
            "subject-1",
            summary_id="summary-semantic",
            summary_type="topic.test",
            scope="topic:test",
            source_memory_ids=[first_memory.memory_id],
            confidence=0.8,
        )
        exact = self.service.generate_summary(
            "subject-1",
            summary_id="summary-semantic",
            summary_type="topic.test",
            scope="topic:test",
            source_memory_ids=[first_memory.memory_id],
            confidence=0.8,
        )
        self.assertEqual(exact.canonical_hash(), summary.canonical_hash())
        self.assertEqual(len(self.repository.summary_history("subject-1", summary.summary_id)), 1)

        for changed_type, changed_scope in (
            ("topic.changed", "topic:test"),
            ("topic.test", "topic:changed"),
        ):
            with self.subTest(
                summary_type=changed_type, scope=changed_scope
            ), self.assertRaises(MemoryIdentityConflictError):
                self.service.generate_summary(
                    "subject-1",
                    summary_id="summary-semantic",
                    summary_type=changed_type,
                    scope=changed_scope,
                    source_memory_ids=[first_memory.memory_id],
                    confidence=0.8,
                )

        confidence_update = self.service.generate_summary(
            "subject-1",
            summary_id="summary-semantic",
            summary_type="topic.test",
            scope="topic:test",
            source_memory_ids=[first_memory.memory_id],
            confidence=0.9,
        )
        self.assertEqual(confidence_update.summary_version, 3)
        self.assertEqual(confidence_update.confidence, 0.9)

        second_memory = self.service.consolidate(
            self.memory("memory-2", "event:two", scope="scope:two")
        ).memory
        source_update = self.service.generate_summary(
            "subject-1",
            summary_id="summary-semantic",
            summary_type="topic.test",
            scope="topic:test",
            source_memory_ids=[first_memory.memory_id, second_memory.memory_id],
            confidence=0.9,
        )
        self.assertEqual(source_update.summary_version, 5)
        self.assertEqual(source_update.source_event_ids, ["one", "two"])
        self.assertEqual(source_update.root_evidence_ids, ["event:one", "event:two"])

    def test_lineage_roots_bind_source_event_and_traceable_sources(self) -> None:
        target = self.service.consolidate(
            self.memory("target", "event:target")
        ).memory
        for roots in (["event:unrelated"], ["event:revoke", "event:unrelated"]):
            with self.subTest(roots=roots), self.assertRaises(MemoryLineageError):
                self.service.propagate_signal(
                    "subject-1",
                    lineage_id=f"lineage-invalid-{len(roots)}",
                    target_memory_id=target.memory_id,
                    signal=MemoryLineageType.REVOCATION,
                    source_event_id="revoke",
                    root_evidence_ids=roots,
                )
        result = self.service.propagate_signal(
            "subject-1",
            lineage_id="lineage-valid",
            target_memory_id=target.memory_id,
            signal=MemoryLineageType.REVOCATION,
            source_event_id="revoke",
            root_evidence_ids=["event:revoke", "event:target"],
        )
        self.assertEqual(result.memory.status, MemoryStatus.REVOKED)
        self.assertEqual(
            result.lineage.root_evidence_ids, ["event:revoke", "event:target"]
        )

    def test_golden_scenario_preserves_fact_intention_relationship_and_revision(self) -> None:
        result = run_p04_golden_scenario(self.root / "golden")
        restarted = JsonMemoryRepository(self.root / "golden", environment="TEST")
        summary = restarted.load_summary(
            "p03-golden-subject", "summary:relationship:day2"
        )

        self.assertEqual(result.version, P04_GOLDEN_SCENARIO_VERSION)
        self.assertIn("intention", result.memories[0].tags)
        self.assertIn("fact", result.memories[1].tags)
        self.assertIn("argument", summary.content.casefold())
        self.assertIn("reconciliation", summary.content.casefold())
        self.assertEqual(result.p03.subject_state.relationship.current_status, "reconciled")
        self.assertEqual(result.p03.subject_state.revision, 2)
        self.assertEqual(summary.canonical_hash(), result.relational_summary.canonical_hash())
        self.assertEqual(len(result.memories), len({item.memory_id for item in result.memories}))


if __name__ == "__main__":
    unittest.main()
