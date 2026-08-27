from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from continuity_engine.domain.integration_hashing import calculate_state_hash
from continuity_engine.testing import (
    P01SandboxManager,
    RetentionMode,
    SandboxEnvironment,
    SandboxLifecycle,
    SandboxOperationError,
    StateFixture,
)
from continuity_engine.testing.models import SnapshotManifest
from continuity_engine.testing.persistence import (
    REPARSE_POINT_ATTRIBUTE,
    canonical_hash,
    file_hash,
    is_link_like,
    tree_inventory_hash,
)
from continuity_engine.testing.sandbox import (
    REQUIRED_SNAPSHOT_COMPONENTS,
    SNAPSHOT_MANIFEST,
    _mapped_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
FROZEN_AT = datetime(2035, 4, 5, 6, 7, 8, tzinfo=UTC)


class MutableMaintenanceClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def fixture() -> StateFixture:
    return StateFixture(
        fixture_id="fixture-p01-001",
        personality_traits=("values continuity",),
        expression_preferences=("concise",),
        relationship_status="testing together",
        relationship_moments=("created a disposable sandbox",),
        continuity_focus=("verify exact rollback",),
        memories=("This is synthetic test memory.",),
    )


class P01SandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.formal_root = self.workspace / "formal-data"
        self.formal_root.mkdir()
        self.formal_canary = self.formal_root / "do-not-touch.bin"
        self.formal_canary.write_bytes(b"formal-subject-canary-v1")
        self.canary_hash = hashlib.sha256(self.formal_canary.read_bytes()).hexdigest()
        self.maintenance = MutableMaintenanceClock(datetime(2040, 1, 1, tzinfo=UTC))
        self.manager = P01SandboxManager(
            self.workspace / "p01-root",
            formal_data_roots=(self.formal_root,),
            maintenance_clock=self.maintenance,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_runtime(self, *, apply_fixture: bool = True):
        runtime = self.manager.create_sandbox(frozen_at=FROZEN_AT)
        if apply_fixture:
            runtime.apply_fixture(fixture())
        return runtime

    def assert_code(self, code: str, callback) -> SandboxOperationError:
        with self.assertRaises(SandboxOperationError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def complete_round_trip(self, runtime):
        formal_before = tree_inventory_hash(self.formal_root)
        snapshot = self.manager.create_snapshot(
            runtime.descriptor.sandbox_id,
            expected_revision=runtime.subject_state().revision,
        )
        proof = self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, snapshot.snapshot_id
        )
        self.manager.rollback(runtime.descriptor.sandbox_id, snapshot.snapshot_id)
        formal_after = tree_inventory_hash(self.formal_root)
        receipt = self.manager.create_acceptance_receipt(
            runtime.descriptor.sandbox_id,
            snapshot.snapshot_id,
            proof.proof_id,
            formal_inventory_before_hash=formal_before,
            formal_inventory_after_hash=formal_after,
        )
        return snapshot, proof, receipt

    def test_disposable_identity_binding_cycle_namespace_and_root_are_unique(self) -> None:
        first = self.create_runtime(apply_fixture=False)
        second = self.create_runtime(apply_fixture=False)
        left = first.descriptor
        right = second.descriptor
        self.assertEqual(left.environment, SandboxEnvironment.TEST)
        self.assertTrue(left.synthetic)
        self.assertFalse(left.promotion_allowed)
        for field in (
            "sandbox_id",
            "subject_id",
            "binding_id",
            "cycle_id",
            "namespace_id",
            "active_branch_id",
            "data_root",
        ):
            self.assertNotEqual(getattr(left, field), getattr(right, field))

    def test_sandbox_root_is_physically_and_logically_isolated(self) -> None:
        runtime = self.create_runtime()
        data_root = runtime.data_root.resolve()
        self.assertNotEqual(data_root, self.formal_root.resolve())
        self.assertNotIn(self.formal_root.resolve(), data_root.parents)
        self.assertNotIn(data_root, self.formal_root.resolve().parents)
        self.assertEqual(self.manager.formal_access_count, 0)
        self.assertEqual(
            hashlib.sha256(self.formal_canary.read_bytes()).hexdigest(), self.canary_hash
        )

    def test_subject_clock_is_frozen_and_advance_is_predictable(self) -> None:
        runtime = self.create_runtime()
        self.assertEqual(runtime.clock.now(), FROZEN_AT)
        state_before = runtime.subject_state()
        self.assertEqual(state_before.temporal.created_at, FROZEN_AT)
        advanced = runtime.clock.advance(timedelta(hours=3, minutes=15))
        self.assertEqual(advanced, FROZEN_AT + timedelta(hours=3, minutes=15))
        runtime.apply_changed_event(
            personality_trait="patient",
            relationship_status="closer",
            continuity_focus="advanced clock",
            memory_content="Synthetic later memory.",
        )
        update = runtime.subject_states.get_update_history(runtime.descriptor.subject_id)[-1]
        self.assertEqual(update.event.occurred_at, advanced)
        self.assertEqual(update.applied_at, advanced)
        self.assertEqual(runtime.subject_state().temporal.updated_at, advanced)

    def test_all_sandbox_component_timestamps_use_subject_clock(self) -> None:
        runtime = self.create_runtime()
        event = runtime.subject_states.get_update_history(runtime.descriptor.subject_id)[0].event
        learning = runtime.learning.list_learning_events(runtime.descriptor.subject_id)[0]
        resource = runtime.resources.get_resource_state(runtime.descriptor.subject_id)
        trace_times = {item["occurredAt"] for item in runtime.trace.to_dict()["entries"]}
        expected = "2035-04-05T06:07:08Z"
        self.assertEqual(event.to_dict()["occurred_at"], expected)
        self.assertEqual(learning.to_dict()["created_at"], expected)
        self.assertEqual(resource.to_dict()["updated_at"], expected)
        self.assertEqual(trace_times, {expected})

    def test_maintenance_clock_does_not_enter_subject_history(self) -> None:
        runtime = self.create_runtime()
        serialized = json.dumps(
            runtime.logical_components(), ensure_ascii=False, sort_keys=True, default=str
        )
        self.assertNotIn("2040-01-01", serialized)
        self.assertEqual(runtime.descriptor.created_at, self.maintenance.value)

    def test_fixture_is_explicit_synthetic_test_data(self) -> None:
        runtime = self.create_runtime()
        value = json.loads(
            (runtime.data_root / "fixture" / "state-fixture.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(value["synthetic"])
        self.assertEqual(value["environment"], "TEST")
        self.assertFalse(value["promotionAllowed"])
        event = runtime.subject_states.get_update_history(runtime.descriptor.subject_id)[0].event
        self.assertTrue(event.metadata["synthetic"])
        self.assertEqual(event.metadata["environment"], "TEST")

    def test_personality_and_relationship_fixture_use_event_evolution(self) -> None:
        runtime = self.create_runtime()
        state = runtime.subject_state()
        updates = runtime.subject_states.get_update_history(runtime.descriptor.subject_id)
        self.assertEqual(state.revision, 1)
        self.assertEqual(len(updates), 1)
        self.assertIn("values continuity", state.identity.stable_traits)
        self.assertEqual(state.relationship.current_status, "testing together")
        self.assertEqual(updates[0].before_revision, 0)
        self.assertEqual(updates[0].after_revision, 1)

    def test_snapshot_has_every_required_logical_component(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(
            runtime.descriptor.sandbox_id, expected_revision=1
        )
        self.assertTrue(snapshot.complete)
        self.assertEqual({item.name for item in snapshot.components}, REQUIRED_SNAPSHOT_COMPONENTS)
        self.assertTrue(all(item.complete for item in snapshot.components))
        self.assertTrue(all(item.canonical_content_hash.startswith("sha256:") for item in snapshot.components))
        self.assertTrue(all(item.file_hash.startswith("sha256:") for item in snapshot.components))

    def test_snapshot_creation_fails_when_a_component_is_missing(self) -> None:
        runtime = self.create_runtime()
        runtime.memory.path.unlink()
        self.assert_code(
            "SNAPSHOT_INCOMPLETE",
            lambda: self.manager.create_snapshot(
                runtime.descriptor.sandbox_id, expected_revision=1
            ),
        )
        descriptor = self.manager._load_descriptor(runtime.branch_root.parents[1])
        self.assertEqual(descriptor.snapshot_ids, [])

    def test_snapshot_rejects_unmapped_physical_file(self) -> None:
        runtime = self.create_runtime()
        (runtime.data_root / "unmapped-state.json").write_text("{}\n", encoding="utf-8")
        self.assert_code(
            "SNAPSHOT_INCOMPLETE",
            lambda: self.manager.create_snapshot(
                runtime.descriptor.sandbox_id, expected_revision=1
            ),
        )
        descriptor = self.manager._load_descriptor(runtime.branch_root.parents[1])
        self.assertEqual(descriptor.snapshot_ids, [])
        self.assertEqual(descriptor.snapshot_anchors, {})

    def test_snapshot_rejects_duplicate_physical_component_mapping(self) -> None:
        logical = {
            "left": {"physicalPath": "shared.json"},
            "right": {"physicalPath": "shared.json"},
        }
        self.assert_code(
            "SNAPSHOT_INCOMPLETE", lambda: _mapped_inventory(logical)
        )

    def test_snapshot_creation_requires_the_known_revision(self) -> None:
        runtime = self.create_runtime()
        self.assert_code(
            "SNAPSHOT_REVISION_CONFLICT",
            lambda: self.manager.create_snapshot(
                runtime.descriptor.sandbox_id, expected_revision=0
            ),
        )

    def test_tampered_logical_component_is_rejected(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        snapshot_root = runtime.branch_root.parents[1] / "n" / snapshot.snapshot_id
        logical = snapshot_root / "logical" / "memory.json"
        logical.write_text('{"name":"memory","payload":{"tampered":true}}\n', encoding="utf-8")
        self.assert_code(
            "SNAPSHOT_TAMPERED",
            lambda: self.manager.validate_snapshot(runtime.descriptor.sandbox_id, snapshot.snapshot_id),
        )

    def test_tampered_physical_payload_is_rejected(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        snapshot_root = runtime.branch_root.parents[1] / "n" / snapshot.snapshot_id
        clock = snapshot_root / "payload" / "clock" / "subject-clock.v1.json"
        value = json.loads(clock.read_text(encoding="utf-8"))
        value["currentTime"] = "2036-01-01T00:00:00Z"
        clock.write_text(json.dumps(value), encoding="utf-8")
        self.assert_code(
            "SNAPSHOT_TAMPERED",
            lambda: self.manager.validate_snapshot(runtime.descriptor.sandbox_id, snapshot.snapshot_id),
        )

    def test_recomputed_internal_snapshot_hashes_do_not_bypass_external_anchor(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        snapshot_root = runtime.branch_root.parents[1] / "n" / snapshot.snapshot_id
        clock_path = snapshot_root / "payload" / "clock" / "subject-clock.v1.json"
        clock_value = json.loads(clock_path.read_text(encoding="utf-8"))
        clock_value["currentTime"] = "2036-01-01T00:00:00Z"
        clock_path.write_text(json.dumps(clock_value) + "\n", encoding="utf-8")

        logical_path = snapshot_root / "logical" / "subject_clock.json"
        logical_value = json.loads(logical_path.read_text(encoding="utf-8"))
        logical_value["payload"] = clock_value
        logical_path.write_text(json.dumps(logical_value) + "\n", encoding="utf-8")

        manifest_path = snapshot_root / SNAPSHOT_MANIFEST
        manifest = SnapshotManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
        clock_component = next(item for item in manifest.components if item.name == "subject_clock")
        aggregate = canonical_hash(
            [{"path": clock_component.physical_path, "sha256": file_hash(clock_path)}]
        )
        components = tuple(
            replace(
                item,
                canonical_content_hash=canonical_hash(clock_value),
                file_hash=aggregate,
            )
            if item.name == "subject_clock"
            else item
            for item in manifest.components
        )
        inventory = tuple(
            replace(item, file_hash=file_hash(clock_path))
            if item.relative_path == clock_component.physical_path
            else item
            for item in manifest.physical_inventory
        )
        rewritten = replace(
            manifest,
            components=components,
            physical_inventory=inventory,
            manifest_hash="pending",
        )
        rewritten = replace(
            rewritten, manifest_hash=canonical_hash(rewritten.unsigned_dict())
        )
        manifest_path.write_text(
            json.dumps(rewritten.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assert_code(
            "SNAPSHOT_TAMPERED",
            lambda: self.manager.validate_snapshot(
                runtime.descriptor.sandbox_id, snapshot.snapshot_id
            ),
        )

    def test_snapshot_component_identity_metadata_mismatch_is_rejected(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        snapshot_root = runtime.branch_root.parents[1] / "n" / snapshot.snapshot_id
        manifest_path = snapshot_root / SNAPSHOT_MANIFEST
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        value["components"][0]["snapshotId"] = "wrong-snapshot"
        manifest_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        self.assert_code(
            "SNAPSHOT_TAMPERED",
            lambda: self.manager.validate_snapshot(
                runtime.descriptor.sandbox_id, snapshot.snapshot_id
            ),
        )

    def test_rollback_failure_restores_the_unchanged_current_branch(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        runtime.clock.advance(timedelta(hours=1))
        runtime.apply_changed_event(
            personality_trait="after snapshot",
            relationship_status="changed",
            continuity_focus="fault test",
            memory_content="Synthetic fault-test memory.",
        )
        changed = runtime.component_fingerprint()
        self.assert_code(
            "ROLLBACK_FAILED",
            lambda: self.manager.rollback(
                runtime.descriptor.sandbox_id,
                snapshot.snapshot_id,
                fault="after_original_moved",
            ),
        )
        recovered = self.manager.open_runtime(runtime.descriptor.sandbox_id)
        self.assertEqual(recovered.component_fingerprint(), changed)

    def test_changed_true_and_rollback_restore_every_component_exactly(self) -> None:
        runtime = self.create_runtime()
        before_hash = calculate_state_hash(runtime.subject_state())
        before = runtime.component_fingerprint()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        runtime.clock.advance(timedelta(days=1))
        runtime.apply_changed_event(
            personality_trait="learned patience",
            relationship_status="closer after testing",
            continuity_focus="post-snapshot focus",
            memory_content="Synthetic post-snapshot memory.",
        )
        after = runtime.component_fingerprint()
        self.assertEqual(runtime.subject_state().revision, 2)
        self.assertNotEqual(calculate_state_hash(runtime.subject_state()), before_hash)
        for component in (
            "subject_state",
            "events",
            "state_mutations",
            "evolution",
            "memory",
            "learning",
            "relationship_state",
            "resource_ledger",
            "subject_clock",
            "test_trace",
        ):
            self.assertNotEqual(after[component], before[component], component)
        self.manager.rollback(runtime.descriptor.sandbox_id, snapshot.snapshot_id)
        restored = self.manager.open_runtime(runtime.descriptor.sandbox_id)
        self.assertEqual(restored.subject_state().revision, 1)
        self.assertEqual(calculate_state_hash(restored.subject_state()), before_hash)
        self.assertEqual(restored.component_fingerprint(), before)

    def test_standard_engine_interaction_produces_real_changed_true_and_sessions(self) -> None:
        runtime = self.create_runtime()
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        proof = self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, snapshot.snapshot_id
        )
        self.assertTrue(proof.changed)
        self.assertEqual(proof.previous_revision, 1)
        self.assertEqual(proof.current_revision, 2)
        self.assertIsNotNone(proof.engine_update_id)
        self.assertEqual(len(proof.wake_session_ids), 1)
        self.assertEqual(len(proof.think_session_ids), 1)
        self.assertEqual(len(proof.action_session_ids), 1)
        self.assertTrue(
            {"wake", "perception", "thinking", "action", "evolution", "completed"}
            .issubset(proof.standard_call_log)
        )
        changed = self.manager.open_runtime(runtime.descriptor.sandbox_id)
        self.assertEqual(len(changed.integration_ledger.list_operations()), 1)
        self.assertEqual(len(changed.integration_ledger.list_completed()), 1)

    def test_standard_interaction_durable_state_is_closed_world_snapshotted(self) -> None:
        runtime = self.create_runtime()
        first = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, first.snapshot_id
        )
        changed_snapshot = self.manager.create_snapshot(
            runtime.descriptor.sandbox_id, expected_revision=2
        )
        components = {item.name: item for item in changed_snapshot.components}
        for name in (
            "wake_sessions",
            "thinking_sessions",
            "action_sessions",
            "operation_journal",
            "completed_result_ledger",
        ):
            self.assertGreater(components[name].count, 0, name)
        inventory_paths = {
            item.relative_path for item in changed_snapshot.physical_inventory
        }
        mapped_paths = {
            path
            for component in changed_snapshot.components
            for path in component.physical_path.split(";")
        }
        self.assertEqual(inventory_paths, mapped_paths)

    def test_branch_is_independent_and_created_from_a_valid_snapshot(self) -> None:
        runtime = self.create_runtime()
        original_branch = runtime.branch_id
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        new_branch = self.manager.create_branch(runtime.descriptor.sandbox_id, snapshot.snapshot_id)
        self.assertNotEqual(new_branch, original_branch)
        branched = self.manager.open_runtime(runtime.descriptor.sandbox_id)
        branched.apply_changed_event(
            personality_trait="branch-only",
            relationship_status="branch relationship",
            continuity_focus="branch focus",
            memory_content="Synthetic branch memory.",
        )
        original = self.manager.open_runtime(
            runtime.descriptor.sandbox_id, branch_id=original_branch
        )
        self.assertEqual(branched.subject_state().revision, 2)
        self.assertEqual(original.subject_state().revision, 1)

    def test_promotion_is_forbidden_in_manager_and_runtime(self) -> None:
        runtime = self.create_runtime()
        self.assert_code(
            "PROMOTION_FORBIDDEN", lambda: self.manager.promote(runtime.descriptor.sandbox_id)
        )
        self.assert_code("PROMOTION_FORBIDDEN", runtime.promote)

    def test_success_exports_evidence_before_automatic_cleanup(self) -> None:
        runtime = self.create_runtime()
        formal_before = tree_inventory_hash(self.formal_root)
        _snapshot, _proof, receipt = self.complete_round_trip(runtime)
        evidence, cleanup = self.manager.finalize_success(
            runtime.descriptor.sandbox_id, receipt.receipt_id
        )
        self.assertTrue(cleanup.cleaned)
        self.assertTrue(evidence.sandbox_removed)
        self.assertTrue(evidence.changed)
        self.assertTrue(evidence.exact_restored)
        self.assertTrue(evidence.standard_interaction_completed)
        self.assertTrue(evidence.formal_isolation_verified)
        self.assertFalse(runtime.branch_root.parents[1].exists())
        evidence_path = self.manager.evidence_root / f"{evidence.evidence_id}.json"
        self.assertTrue(evidence_path.is_file())
        self.assertTrue(json.loads(evidence_path.read_text(encoding="utf-8"))["sandboxRemoved"])
        self.assertEqual(tree_inventory_hash(self.formal_root), formal_before)

    def test_finalize_without_changed_and_rollback_is_rejected(self) -> None:
        runtime = self.create_runtime()
        self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        self.assert_code(
            "ACCEPTANCE_NOT_READY",
            lambda: self.manager.finalize_success(runtime.descriptor.sandbox_id),
        )

    def test_changed_without_rollback_cannot_create_acceptance_receipt(self) -> None:
        runtime = self.create_runtime()
        formal_hash = tree_inventory_hash(self.formal_root)
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        proof = self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, snapshot.snapshot_id
        )
        self.assert_code(
            "ACCEPTANCE_NOT_READY",
            lambda: self.manager.create_acceptance_receipt(
                runtime.descriptor.sandbox_id,
                snapshot.snapshot_id,
                proof.proof_id,
                formal_inventory_before_hash=formal_hash,
                formal_inventory_after_hash=formal_hash,
            ),
        )

    def test_rollback_then_changed_fingerprint_cannot_create_receipt(self) -> None:
        runtime = self.create_runtime()
        formal_hash = tree_inventory_hash(self.formal_root)
        snapshot = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        proof = self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, snapshot.snapshot_id
        )
        self.manager.rollback(runtime.descriptor.sandbox_id, snapshot.snapshot_id)
        restored = self.manager.open_runtime(runtime.descriptor.sandbox_id)
        restored.apply_changed_event(
            personality_trait="post-rollback drift",
            relationship_status="drifted",
            continuity_focus="drift",
            memory_content="Synthetic drift memory.",
        )
        self.assert_code(
            "ACCEPTANCE_NOT_READY",
            lambda: self.manager.create_acceptance_receipt(
                runtime.descriptor.sandbox_id,
                snapshot.snapshot_id,
                proof.proof_id,
                formal_inventory_before_hash=formal_hash,
                formal_inventory_after_hash=formal_hash,
            ),
        )

    def test_acceptance_proof_cannot_cross_snapshot(self) -> None:
        runtime = self.create_runtime()
        formal_hash = tree_inventory_hash(self.formal_root)
        first = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        proof = self.manager.execute_standard_interaction(
            runtime.descriptor.sandbox_id, first.snapshot_id
        )
        self.manager.rollback(runtime.descriptor.sandbox_id, first.snapshot_id)
        second = self.manager.create_snapshot(runtime.descriptor.sandbox_id, expected_revision=1)
        self.assert_code(
            "ACCEPTANCE_NOT_READY",
            lambda: self.manager.create_acceptance_receipt(
                runtime.descriptor.sandbox_id,
                second.snapshot_id,
                proof.proof_id,
                formal_inventory_before_hash=formal_hash,
                formal_inventory_after_hash=formal_hash,
            ),
        )

    def test_tampered_acceptance_receipt_is_rejected(self) -> None:
        runtime = self.create_runtime()
        _snapshot, _proof, receipt = self.complete_round_trip(runtime)
        receipt_path = (
            runtime.branch_root.parents[1]
            / "acceptance"
            / "receipts"
            / f"{receipt.receipt_id}.json"
        )
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
        value["exactRestored"] = False
        receipt_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        self.assert_code(
            "ACCEPTANCE_NOT_READY",
            lambda: self.manager.finalize_success(
                runtime.descriptor.sandbox_id, receipt.receipt_id
            ),
        )

    def test_failed_sandbox_is_retained_for_exactly_24_hours(self) -> None:
        runtime = self.create_runtime()
        retained = self.manager.retain_failure(runtime.descriptor.sandbox_id)
        self.assertEqual(retained.retention_mode, RetentionMode.FAILURE_24_HOURS)
        self.assertEqual(retained.lifecycle, SandboxLifecycle.RETAINED)
        self.assertEqual(retained.expires_at - retained.created_at, timedelta(hours=24))
        self.assertEqual(self.manager.open_runtime(runtime.descriptor.sandbox_id).subject_state().revision, 1)

    def test_explicit_debug_retention_cannot_exceed_seven_days(self) -> None:
        runtime = self.create_runtime()
        retained = self.manager.retain_failure(
            runtime.descriptor.sandbox_id, debug_for=timedelta(days=7)
        )
        self.assertEqual(retained.retention_mode, RetentionMode.DEBUG)
        self.assertEqual(retained.expires_at - retained.created_at, timedelta(days=7))
        second = self.create_runtime()
        self.assert_code(
            "RETENTION_INVALID",
            lambda: self.manager.retain_failure(
                second.descriptor.sandbox_id, debug_for=timedelta(days=7, seconds=1)
            ),
        )

    def test_expiry_scan_runs_at_explicit_maintenance_entry(self) -> None:
        runtime = self.create_runtime()
        self.manager.retain_failure(runtime.descriptor.sandbox_id)
        self.maintenance.value += timedelta(hours=25)
        results = self.manager.scan_expired()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].cleaned)

    def test_expiry_scan_runs_when_a_new_manager_starts(self) -> None:
        runtime = self.create_runtime()
        self.manager.retain_failure(runtime.descriptor.sandbox_id)
        self.maintenance.value += timedelta(hours=25)
        P01SandboxManager(
            self.manager.base_root,
            formal_data_roots=(self.formal_root,),
            maintenance_clock=self.maintenance,
        )
        self.assertFalse(runtime.branch_root.parents[1].exists())

    def test_abandoned_active_sandbox_is_cleaned_after_24_hours(self) -> None:
        runtime = self.create_runtime()
        self.assertEqual(runtime.descriptor.lifecycle, SandboxLifecycle.ACTIVE)
        self.assertEqual(
            runtime.descriptor.expires_at - runtime.descriptor.created_at,
            timedelta(hours=24),
        )
        self.maintenance.value += timedelta(hours=25)
        P01SandboxManager(
            self.manager.base_root,
            formal_data_roots=(self.formal_root,),
            maintenance_clock=self.maintenance,
        )
        self.assertFalse(runtime.branch_root.parents[1].exists())

    def test_manual_cleanup_is_targeted_and_idempotent(self) -> None:
        first = self.create_runtime()
        second = self.create_runtime()
        result = self.manager.cleanup(first.descriptor.sandbox_id)
        repeated = self.manager.cleanup(first.descriptor.sandbox_id)
        self.assertTrue(result.cleaned)
        self.assertTrue(repeated.already_clean)
        self.assertTrue(second.branch_root.parents[1].exists())

    def test_unknown_or_unregistered_directory_cannot_be_cleaned(self) -> None:
        rogue = self.manager.sandboxes_root / "unknown-sandbox"
        rogue.mkdir()
        canary = rogue / "keep.txt"
        canary.write_text("keep", encoding="utf-8")
        self.assert_code(
            "SANDBOX_NOT_REGISTERED", lambda: self.manager.cleanup("unknown-sandbox")
        )
        self.assertEqual(canary.read_text(encoding="utf-8"), "keep")

    def test_missing_sandbox_marker_refuses_cleanup(self) -> None:
        runtime = self.create_runtime()
        marker = runtime.branch_root.parents[1] / "sandbox-manifest.v1.json"
        marker.unlink()
        self.assert_code(
            "SANDBOX_MARKER_MISSING", lambda: self.manager.cleanup(runtime.descriptor.sandbox_id)
        )
        self.assertTrue(runtime.branch_root.parents[1].exists())

    def test_repository_formal_home_and_parent_roots_are_forbidden(self) -> None:
        candidates = (
            ROOT,
            self.formal_root,
            self.formal_root / "nested",
            Path.home(),
            Path.home().parent,
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assert_code(
                    "SANDBOX_ROOT_FORBIDDEN",
                    lambda candidate=candidate: P01SandboxManager(
                        candidate, formal_data_roots=(self.formal_root,)
                    ),
                )

    def test_link_or_junction_cleanup_target_is_rejected(self) -> None:
        runtime = self.create_runtime()
        with patch(
            "continuity_engine.testing.sandbox.assert_no_link_components",
            side_effect=SandboxOperationError(
                "SANDBOX_PATH_FORBIDDEN", "simulated reparse target"
            ),
        ):
            self.assert_code(
                "SANDBOX_PATH_FORBIDDEN",
                lambda: self.manager.cleanup(runtime.descriptor.sandbox_id),
            )
        self.assertTrue(runtime.branch_root.parents[1].exists())

    def test_windows_reparse_attribute_is_treated_as_link_like(self) -> None:
        class FakeStat:
            st_file_attributes = REPARSE_POINT_ATTRIBUTE

        class FakePath:
            def is_symlink(self):
                return False

            def lstat(self):
                return FakeStat()

        self.assertTrue(is_link_like(FakePath()))

    def test_p01_runtime_does_not_require_vio_or_background_scheduler(self) -> None:
        runtime = self.create_runtime()
        self.assertEqual(runtime.subject_state().revision, 1)
        source = (ROOT / "src" / "continuity_engine" / "testing" / "sandbox.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import threading", source)
        self.assertNotIn("import vio", source.lower())
        self.assertNotIn("from vio", source.lower())
        self.assertNotIn("requests.", source.lower())

    def test_all_p01_repository_roots_are_inside_sandbox_and_formal_tree_is_unchanged(self) -> None:
        before = tree_inventory_hash(self.formal_root)
        runtime = self.create_runtime()
        self.assertTrue(runtime.repository_roots_authorized())
        data_root = runtime.data_root.resolve(strict=False)
        for repository_root in runtime.repository_roots():
            resolved = repository_root.resolve(strict=False)
            self.assertIn(data_root, resolved.parents)
        snapshot, _proof, _receipt = self.complete_round_trip(runtime)
        self.assertTrue(snapshot.complete)
        self.assertEqual(tree_inventory_hash(self.formal_root), before)
        self.assertEqual(self.manager.formal_access_count, 0)

    def test_six_frozen_schema_file_hashes_are_unchanged(self) -> None:
        schema_root = ROOT / "src" / "continuity_engine" / "interfaces" / "schemas"
        expected = {
            "continuity-interaction-request.first-round-v1.schema.json": "18d9656cf4a3842cc55b18411593dfc48a79522ac742b64d83a6fa17d9add656",
            "platform-observation.message-created.first-round-v1.schema.json": "bc3aaff3d5a928975e9ec434a74d05c7f18bffaaa1bdca46da78142552a98ace",
            "platform-fact.message-version.first-round-v1.schema.json": "2ccf8fea7dc69cc1d89e5da5ae8f798f3c170285e61a5d4191d3cbfad1a8746b",
            "capability-request.v1.schema.json": "093284bfc70d0bd5679b34c68d4197a49103680094443ac9d7d6550f9a44e949",
            "capability-result.v1.schema.json": "3359228260eeb5a48f52c2f7ca20bf4821705aa7e50ecd41973d495e703a7001",
            "capability-model-output.v1.schema.json": "babdf85c2aa28609d2eb16178ab0a57e3b648f686ab05def0f86dca898526426",
        }
        actual = {
            name: hashlib.sha256((schema_root / name).read_bytes()).hexdigest()
            for name in expected
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
