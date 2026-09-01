import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.errors import (
    MemoryIdentityConflictError,
    MemoryPersistenceError,
    MemoryValidationError,
)
from continuity_engine.domain.memory import (
    DerivedSummary,
    MemoryConsolidationOperation,
    MemoryEvidenceType,
    MemoryKind,
    MemoryLineageRecord,
    MemoryLineageType,
    MemoryRecord,
    MemoryStatus,
    MemoryTimeRange,
)
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository


UTC = timezone.utc


class P04MemoryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)
        self.repository = JsonMemoryRepository(self.root, environment="TEST")

    def memory(
        self,
        memory_id: str = "memory-1",
        *,
        subject_id: str = "subject-1",
        environment: str = "TEST",
        source_event_ids: list[str] | None = None,
        source_memory_ids: list[str] | None = None,
        root_evidence_ids: list[str] | None = None,
        revision: int = 0,
        content: str = "A traceable episodic memory.",
        consolidation_id: str | None = None,
    ) -> MemoryRecord:
        return MemoryRecord(
            memory_id=memory_id,
            subject_id=subject_id,
            environment=environment,
            kind=MemoryKind.EPISODIC,
            evidence_type=MemoryEvidenceType.EXPERIENTIAL,
            content=content,
            root_evidence_ids=root_evidence_ids or [f"event:{memory_id}"],
            source_event_ids=(
                source_event_ids
                if source_event_ids is not None
                else ([] if source_memory_ids else [memory_id])
            ),
            source_memory_ids=source_memory_ids or [],
            occurred_at=self.now,
            observed_at=self.now + timedelta(seconds=1),
            recorded_at=self.now + timedelta(seconds=2),
            consolidated_at=self.now + timedelta(seconds=3),
            confidence=0.8,
            importance=0.7,
            activation=0.6,
            scope=f"scope:{memory_id}",
            time_range=MemoryTimeRange(self.now, self.now),
            tags=["p04", "synthetic"],
            revision=revision,
            memory_version=revision + 1,
            consolidation_id=consolidation_id or f"consolidation:{memory_id}",
        )

    def test_domain_round_trip_normalizes_time_and_hash(self) -> None:
        plus_eight = timezone(timedelta(hours=8))
        memory = self.memory()
        payload = memory.to_dict()
        payload["occurred_at"] = "2026-08-30T18:00:00+08:00"
        payload["time_range"] = {
            "start_at": "2026-08-30T18:00:00+08:00",
            "end_at": "2026-08-30T18:00:00+08:00",
        }
        restored = MemoryRecord.from_dict(payload)

        self.assertEqual(restored.occurred_at, datetime(2026, 8, 30, 10, 0, tzinfo=UTC))
        self.assertEqual(restored.to_dict()["occurred_at"], "2026-08-30T10:00:00Z")
        self.assertEqual(
            MemoryRecord.from_dict(restored.to_dict()).canonical_hash(),
            restored.canonical_hash(),
        )
        self.assertEqual(plus_eight.utcoffset(None), timedelta(hours=8))

    def test_memory_kind_and_evidence_type_are_distinct_closed_terms(self) -> None:
        payload = self.memory().to_dict()
        payload["evidence_type"] = "episodic"
        with self.assertRaises(MemoryValidationError):
            MemoryRecord.from_dict(payload)

    def test_source_chain_root_evidence_and_duplicate_inputs_fail_closed(self) -> None:
        payload = self.memory().to_dict()
        payload["source_event_ids"] = []
        with self.assertRaises(MemoryValidationError):
            MemoryRecord.from_dict(payload)
        payload = self.memory().to_dict()
        payload["root_evidence_ids"] = ["root", "root"]
        with self.assertRaises(MemoryValidationError):
            MemoryRecord.from_dict(payload)

    def test_atomic_persistence_restart_idempotence_and_identity_conflict(self) -> None:
        memory = self.memory()
        self.assertTrue(self.repository.save_memory(memory))
        self.assertFalse(self.repository.save_memory(MemoryRecord.from_dict(memory.to_dict())))

        restarted = JsonMemoryRepository(self.root, environment="TEST")
        self.assertEqual(restarted.load_memory("subject-1", "memory-1").to_dict(), memory.to_dict())
        payload = memory.to_dict()
        payload["content"] = "Conflicting body under the same immutable version."
        payload["consolidation_input_hash"] = None
        with self.assertRaises(MemoryIdentityConflictError):
            restarted.save_memory(MemoryRecord.from_dict(payload))

    def test_cross_subject_and_forward_memory_source_fail_closed(self) -> None:
        self.repository.save_memory(self.memory("memory-1"))
        valid = self.memory(
            "memory-2",
            source_event_ids=[],
            source_memory_ids=["memory-1"],
            root_evidence_ids=["event:memory-1"],
        )
        self.repository.save_memory(valid)
        other_repository = JsonMemoryRepository(self.root, environment="TEST")
        cross_subject = self.memory(
            "memory-3",
            subject_id="subject-2",
            source_event_ids=[],
            source_memory_ids=["memory-1"],
            root_evidence_ids=["event:memory-1"],
        )
        with self.assertRaises(MemoryValidationError):
            other_repository.save_memory(cross_subject)

    def test_environment_isolation_fails_before_persistence(self) -> None:
        with self.assertRaises(MemoryValidationError):
            self.repository.save_memory(self.memory(environment="RESEARCH"))
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_integrity_hash_and_recomputed_structural_tampering_fail_closed(self) -> None:
        self.repository.save_memory(self.memory())
        path = next(self.root.rglob("*.json"))
        document = json.loads(path.read_text(encoding="utf-8"))
        document["memory_records"][0]["content"] = "tampered"
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(MemoryPersistenceError):
            self.repository.list_memories("subject-1")

        self.repository = JsonMemoryRepository(self.root / "fresh", environment="TEST")
        self.repository.save_memory(self.memory())
        path = next((self.root / "fresh").rglob("*.json"))
        document = json.loads(path.read_text(encoding="utf-8"))
        document["memory_records"].append(dict(document["memory_records"][0]))
        content = dict(document)
        content.pop("document_hash")
        document["document_hash"] = self.repository._document_hash(content)
        path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(MemoryPersistenceError):
            self.repository.list_memories("subject-1")

    def test_failed_atomic_replace_keeps_previous_document_readable(self) -> None:
        original = self.memory()
        self.repository.save_memory(original)
        second = self.memory("memory-2")
        with patch(
            "continuity_engine.storage.json_memory_repository.os.replace",
            side_effect=OSError("simulated replace failure"),
        ), self.assertRaises(OSError):
            self.repository.save_memory(second)

        restarted = JsonMemoryRepository(self.root, environment="TEST")
        self.assertEqual(
            [item.memory_id for item in restarted.list_memories("subject-1")],
            ["memory-1"],
        )
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_summary_must_trace_to_same_subject_memory(self) -> None:
        memory = self.memory()
        self.repository.save_memory(memory)
        summary = DerivedSummary(
            summary_id="summary-1",
            subject_id="subject-1",
            environment="TEST",
            summary_type="topic.v1",
            scope="scope:summary",
            time_range=memory.time_range,
            generated_at=self.now + timedelta(minutes=1),
            summary_version=1,
            source_event_ids=list(memory.source_event_ids),
            source_memory_ids=[memory.memory_id],
            source_message_ids=[],
            root_evidence_ids=list(memory.root_evidence_ids),
            confidence=0.8,
            content="A rebuildable summary.",
        )
        self.assertTrue(self.repository.save_summary(summary))
        self.assertEqual(
            self.repository.load_summary("subject-1", "summary-1").canonical_hash(),
            summary.canonical_hash(),
        )

    def test_consolidation_operation_loading_rejects_tampering_and_broken_boundaries(self) -> None:
        mutations = {
            "duplicate": lambda document: document["consolidation_operations"].append(
                dict(document["consolidation_operations"][0])
            ),
            "conflicting_hash": lambda document: document[
                "consolidation_operations"
            ].append(
                {
                    **document["consolidation_operations"][0],
                    "canonical_input_hash": f"sha256:{'1' * 64}",
                }
            ),
            "missing_result": lambda document: document[
                "consolidation_operations"
            ][0].update({"result_memory_id": "missing"}),
            "missing_result_revision": lambda document: document[
                "consolidation_operations"
            ][0].pop("result_memory_revision"),
            "forward_result_revision": lambda document: document[
                "consolidation_operations"
            ][0].update({"result_memory_revision": 99}),
            "result_hash_tamper": lambda document: document[
                "consolidation_operations"
            ][0].update({"result_memory_canonical_hash": f"sha256:{'3' * 64}"}),
            "input_hash_tamper": lambda document: document[
                "consolidation_operations"
            ][0].update({"canonical_input_hash": f"sha256:{'2' * 64}"}),
            "cross_subject": lambda document: document[
                "consolidation_operations"
            ][0].update({"subject_id": "subject-2"}),
            "cross_environment": lambda document: document[
                "consolidation_operations"
            ][0].update({"environment": "RESEARCH"}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                repository = JsonMemoryRepository(directory, environment="TEST")
                memory = self.memory()
                operation = MemoryConsolidationOperation(
                    consolidation_id=memory.consolidation_id,
                    subject_id=memory.subject_id,
                    environment=memory.environment,
                    canonical_input_hash=memory.consolidation_hash(),
                    canonical_input=memory.to_dict(),
                    result_memory_id=memory.memory_id,
                    result_memory_revision=memory.revision,
                    result_memory_canonical_hash=memory.canonical_hash(),
                    recorded_at=memory.consolidated_at,
                )
                repository.save_consolidation(memory, operation)
                self.assertEqual(
                    repository.load_consolidation_operation(
                        memory.subject_id, memory.consolidation_id
                    ).canonical_hash(),
                    operation.canonical_hash(),
                )
                path = next(Path(directory).rglob("*.json"))
                document = json.loads(path.read_text(encoding="utf-8"))
                mutate(document)
                content = dict(document)
                content.pop("document_hash")
                document["document_hash"] = repository._document_hash(content)
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(MemoryPersistenceError):
                    repository.list_memories("subject-1")

    def test_operation_canonical_input_source_chain_is_revalidated_after_restart(self) -> None:
        memory = self.memory()
        self.repository.save_memory(memory)
        alias_payload = memory.to_dict()
        alias_payload.update(
            {
                "memory_id": "memory-alias",
                "source_event_ids": [],
                "source_memory_ids": [memory.memory_id],
                "consolidation_id": "consolidation:alias",
                "consolidation_input_hash": None,
            }
        )
        alias = MemoryRecord.from_dict(alias_payload)
        operation = MemoryConsolidationOperation(
            consolidation_id=alias.consolidation_id,
            subject_id=alias.subject_id,
            environment=alias.environment,
            canonical_input_hash=alias.consolidation_hash(),
            canonical_input=alias.to_dict(),
            result_memory_id=memory.memory_id,
            result_memory_revision=memory.revision,
            result_memory_canonical_hash=memory.canonical_hash(),
            recorded_at=alias.consolidated_at,
        )
        self.repository.save_consolidation(memory, operation)

        path = next(self.root.rglob("*.json"))
        document = json.loads(path.read_text(encoding="utf-8"))
        raw_operation = document["consolidation_operations"][0]
        tampered_input = dict(raw_operation["canonical_input"])
        tampered_input["source_memory_ids"] = ["missing-source"]
        tampered = MemoryRecord.from_dict(tampered_input)
        raw_operation["canonical_input"] = tampered.to_dict()
        raw_operation["canonical_input_hash"] = tampered.consolidation_hash()
        content = dict(document)
        content.pop("document_hash")
        document["document_hash"] = self.repository._document_hash(content)
        path.write_text(json.dumps(document), encoding="utf-8")

        restarted = JsonMemoryRepository(self.root, environment="TEST")
        with self.assertRaises(MemoryPersistenceError):
            restarted.load_consolidation_operation("subject-1", "consolidation:alias")

    def test_lineage_loading_rejects_unbound_roots_forward_replacement_and_tampering(self) -> None:
        cases = ("missing_source_root", "unrelated_root", "missing_replacement", "forward_replacement", "cross_subject")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                repository = JsonMemoryRepository(directory, environment="TEST")
                target = self.memory("target")
                repository.save_memory(target)
                lineage_time = self.now + timedelta(minutes=1)
                lineage = MemoryLineageRecord(
                    lineage_id="lineage-1",
                    subject_id="subject-1",
                    environment="TEST",
                    target_memory_id="target",
                    signal=MemoryLineageType.REVOCATION,
                    source_event_id="revoke",
                    root_evidence_ids=["event:revoke", "event:target"],
                    recorded_at=lineage_time,
                )
                payload = target.to_dict()
                payload.update(
                    {
                        "status": MemoryStatus.REVOKED.value,
                        "lineage_event_id": "revoke",
                        "revision": 1,
                        "memory_version": 2,
                    }
                )
                repository.apply_propagation(
                    MemoryRecord.from_dict(payload), lineage, []
                )
                if case == "forward_replacement":
                    future = self.memory("future")
                    future_payload = future.to_dict()
                    occurred = self.now + timedelta(hours=2)
                    future_payload.update(
                        {
                            "occurred_at": occurred.isoformat(),
                            "observed_at": (occurred + timedelta(seconds=1)).isoformat(),
                            "recorded_at": (occurred + timedelta(seconds=2)).isoformat(),
                            "consolidated_at": (occurred + timedelta(seconds=3)).isoformat(),
                            "time_range": MemoryTimeRange(occurred, occurred).to_dict(),
                        }
                    )
                    repository.save_memory(MemoryRecord.from_dict(future_payload))
                path = next(Path(directory).rglob("*.json"))
                document = json.loads(path.read_text(encoding="utf-8"))
                raw_lineage = document["lineage_records"][0]
                if case == "missing_source_root":
                    raw_lineage["root_evidence_ids"] = ["event:target"]
                elif case == "unrelated_root":
                    raw_lineage["root_evidence_ids"].append("event:unrelated")
                elif case == "missing_replacement":
                    raw_lineage["replacement_memory_id"] = "missing"
                elif case == "forward_replacement":
                    raw_lineage["replacement_memory_id"] = "future"
                else:
                    raw_lineage["subject_id"] = "subject-2"
                content = dict(document)
                content.pop("document_hash")
                document["document_hash"] = repository._document_hash(content)
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaises(MemoryPersistenceError):
                    repository.list_lineage("subject-1")


if __name__ == "__main__":
    unittest.main()
