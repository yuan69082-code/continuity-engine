from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from continuity_engine.domain.contradiction import (
    AuditAction,
    ClaimDisposition,
    ClaimDomain,
    ClaimEvaluationStatus,
    ClaimEvidenceType,
    ClaimPolarity,
    ClaimProjection,
    ContradictionAuditEntry,
    ContradictionCase,
    ContradictionDetectionResult,
    ContradictionKind,
    ContradictionStatus,
    ResolutionBasisKind,
    ResolutionEvidence,
    StructuredClaim,
    VerifiedResolutionEvidence,
    VerificationStatus,
    contradiction_hash,
    transition_case,
)
from continuity_engine.domain.errors import (
    ContradictionIdentityConflictError,
    ContradictionPersistenceError,
    ContradictionValidationError,
)
from continuity_engine.testing.p07_contradiction_fixture import (
    build_p07_detector,
    P07DeterministicResolutionEvidenceVerifier,
    p07_resolution_evidence,
    run_p07_golden_scenario,
)


class P07ContradictionDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.golden = run_p07_golden_scenario(self.root)
        self.initial = self.golden.detection.cases[0]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_three_contradiction_kinds_are_stable_and_distinct(self):
        self.assertEqual(
            {item.value for item in ContradictionKind},
            {"EPISTEMIC", "EVIDENTIAL", "COGNITIVE"},
        )

    def test_claim_projection_round_trip_has_no_authority_or_provenance_fields(self):
        projection = ClaimProjection(
            "claim.temperature",
            20,
            ClaimPolarity.AFFIRMS,
            ClaimEvidenceType.EXTERNAL,
            ClaimDomain.FACTUAL,
            "room:now",
        )
        self.assertEqual(ClaimProjection.from_dict(projection.to_dict()), projection)
        self.assertNotIn("authority", projection.to_dict())
        self.assertNotIn("provenance_roots", projection.to_dict())

    def test_structured_claim_and_case_round_trip_preserve_canonical_hashes(self):
        claim = self.initial.claims[0]
        self.assertEqual(
            StructuredClaim.from_dict(claim.to_dict()).claim_hash,
            claim.claim_hash,
        )
        restored = ContradictionCase.from_dict(self.initial.to_dict())
        self.assertEqual(restored.canonical_hash(), self.initial.canonical_hash())

    def test_claim_case_and_result_tampering_fails_closed(self):
        claim = self.initial.claims[0].to_dict()
        claim["authority"] = (
            "confirmed_state"
            if claim["authority"] != "confirmed_state"
            else "raw_source"
        )
        with self.assertRaises(ContradictionValidationError):
            StructuredClaim.from_dict(claim)
        case = self.initial.to_dict()
        case["source_snapshot_hash"] = "sha256:" + "0" * 64
        with self.assertRaises(ContradictionValidationError):
            ContradictionCase.from_dict(case)
        result = self.golden.detection.to_dict()
        result["direct_state_write_allowed"] = True
        with self.assertRaises(ContradictionValidationError):
            ContradictionDetectionResult.from_dict(result)

    def test_case_has_no_state_or_evolution_write_authority(self):
        self.assertFalse(self.initial.direct_state_write_allowed)
        self.assertFalse(self.initial.evolution_commit_allowed)
        self.assertTrue(
            all(item.disposition is not None for item in self.initial.dispositions)
        )

    def test_no_confidence_recency_or_authority_winner_is_persisted(self):
        values = {item.disposition for item in self.initial.dispositions}
        self.assertIn(ClaimDisposition.RETAINED_DISPUTED, values)
        self.assertIn(ClaimDisposition.ISOLATED, values)
        self.assertNotIn("winner_claim_id", self.initial.to_dict())
        self.assertNotIn("selected_claim_id", self.initial.to_dict())

    def test_trace_contains_hashes_and_ids_but_no_material_content(self):
        trace = json.dumps(self.golden.detection.trace.to_dict(), ensure_ascii=False)
        for fragment in self.golden.p06.composition.snapshot.fragments:
            self.assertNotIn(fragment.content, trace)
        self.assertNotIn("credential", trace.casefold())
        self.assertNotIn("chain-of-thought", trace.casefold())

    def test_trace_evaluation_counts_cover_every_p06_fragment(self):
        trace = self.golden.detection.trace
        self.assertEqual(
            trace.evaluated_count
            + trace.unassessed_count
            + trace.psychological_excluded_count,
            trace.fragment_count,
        )
        self.assertEqual(len(trace.evaluations), trace.fragment_count)
        self.assertTrue(
            any(
                item.status is ClaimEvaluationStatus.NOT_APPLICABLE
                and item.reason_code == "PSYCHOLOGICAL_CONFLICT_OUT_OF_SCOPE"
                for item in trace.evaluations
            )
        )

    def test_repository_exact_replay_returns_current_case_without_duplicate(self):
        service, repository, _ = build_p07_detector(self.root)
        repeated = service.detect(self.golden.p06.composition)
        self.assertEqual(repeated.cases[0].status, ContradictionStatus.REOPENED)
        self.assertEqual(len(repository.case_history(self.initial.subject_id, self.initial.case_id)), 3)

    def test_repository_same_identity_different_body_fails_closed(self):
        other_root = self.root / "conflict"
        _, repository, _ = build_p07_detector(other_root)
        repository.save_detected(self.initial)
        changed = replace(
            self.initial,
            impact_scope=("CONTEXT_MATERIAL_CONTESTED",),
            case_hash=None,
        )
        with self.assertRaises(ContradictionIdentityConflictError):
            repository.save_detected(changed)

    def test_repository_restart_preserves_history_order_hash_and_status(self):
        _, repository, _ = build_p07_detector(self.root)
        history = repository.case_history(self.initial.subject_id, self.initial.case_id)
        _, restarted, _ = build_p07_detector(self.root)
        restored = restarted.case_history(self.initial.subject_id, self.initial.case_id)
        self.assertEqual(
            [item.canonical_hash() for item in restored],
            [item.canonical_hash() for item in history],
        )
        self.assertEqual(restored[-1].status, ContradictionStatus.REOPENED)

    def test_repository_document_tampering_fails_closed(self):
        _, repository, _ = build_p07_detector(self.root)
        path = repository._path(self.initial.subject_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["case_records"][0]["detector_version"] = "tampered"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ContradictionPersistenceError):
            repository.load_case(self.initial.subject_id, self.initial.case_id)

    def test_repository_cross_environment_fails_closed(self):
        _, repository, _ = build_p07_detector(self.root)
        with self.assertRaises(ContradictionValidationError):
            repository.save_detected(replace(self.initial, environment="RESEARCH", case_hash=None))

    def test_illegal_forward_transition_and_audit_rewrite_fail_closed(self):
        other_root = self.root / "transition"
        _, repository, _ = build_p07_detector(other_root)
        repository.save_detected(self.initial)
        illegal_audit = ContradictionAuditEntry(
            f"audit-{self.initial.case_id}-illegal",
            len(self.initial.audit_history),
            AuditAction.ISOLATED,
            datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
            "NEW_CONFLICTING_EVIDENCE",
            (contradiction_hash("new"),),
        )
        illegal = transition_case(
            self.initial,
            status=ContradictionStatus.REOPENED,
            audit=illegal_audit,
            verification_status=VerificationStatus.OPEN,
        )
        with self.assertRaises(ContradictionValidationError):
            repository.append_transition(illegal)

    def test_resolution_requires_verified_basis_and_preserves_old_evidence(self):
        before = tuple(item.claim_hash for item in self.initial.claims)
        self.assertEqual(
            tuple(item.claim_hash for item in self.golden.resolved.claims), before
        )
        self.assertEqual(
            self.golden.resolved.audit_history[-1].resolution.basis,
            ResolutionBasisKind.USER_CORRECTION,
        )
        with self.assertRaises(ContradictionValidationError):
            ResolutionEvidence(
                "invalid-resolution",
                self.initial.subject_id,
                self.initial.environment,
                ResolutionBasisKind.USER_CORRECTION,
                "user-correction:invalid",
                (),
                "VERIFIED_USER_CORRECTION",
                datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
            )

    def test_reopen_is_append_only_and_does_not_erase_resolution(self):
        reopened = self.golden.reopened
        self.assertEqual(reopened.status, ContradictionStatus.REOPENED)
        self.assertEqual(reopened.revision, 2)
        self.assertEqual(
            [item.action for item in reopened.audit_history[-2:]],
            [AuditAction.RESOLVED, AuditAction.REOPENED],
        )

    def test_resolution_evidence_is_verified_and_bound_to_subject_environment(self):
        service, _, _ = build_p07_detector(self.root / "resolution-boundary")
        case = service.detect(self.golden.p06.composition).cases[0]
        cross_subject = ResolutionEvidence(
            "resolution-cross-subject",
            "another-subject",
            case.environment,
            ResolutionBasisKind.USER_CORRECTION,
            "user-correction:cross-subject",
            (contradiction_hash("verified-cross-subject"),),
            "VERIFIED_USER_CORRECTION",
            datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
        )
        with self.assertRaisesRegex(ContradictionValidationError, "crosses"):
            service.resolve(case.subject_id, case.case_id, cross_subject)
        untrusted_flag = replace(cross_subject, subject_id=case.subject_id, verified=False)
        self.assertFalse(untrusted_flag.verified)
        with self.assertRaises(ContradictionValidationError):
            service.resolve(case.subject_id, case.case_id, untrusted_flag)

    def test_fabricated_resolution_cannot_self_attest_verification(self):
        service, _, _ = build_p07_detector(self.root / "fabricated-resolution")
        case = service.detect(self.golden.p06.composition).cases[0]
        fabricated = ResolutionEvidence(
            "resolution-fabricated",
            case.subject_id,
            case.environment,
            ResolutionBasisKind.USER_CORRECTION,
            "user-correction:does-not-exist",
            (contradiction_hash("fabricated-source"),),
            "VERIFIED_USER_CORRECTION",
            datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc),
            verified=True,
        )
        with self.assertRaises(ContradictionValidationError):
            service.resolve(case.subject_id, case.case_id, fabricated)

    def test_complete_result_rejects_cross_subject_case_even_with_valid_hashes(self):
        trace = self.golden.detection.trace
        case = self.golden.detection.cases[0]
        foreign_claims = tuple(
            replace(item, subject_id="other-subject", claim_hash=None)
            for item in case.claims
        )
        foreign = replace(
            case,
            subject_id="other-subject",
            claims=foreign_claims,
            case_hash=None,
        )
        with self.assertRaises(ContradictionValidationError):
            ContradictionDetectionResult(
                self.golden.detection.status,
                trace,
                (foreign,),
            )

    def test_complete_result_rejects_rehashed_cross_boundary_cases_on_deserialization(self):
        trace = self.golden.detection.trace
        case = self.golden.detection.cases[0]
        variants = (
            replace(
                case,
                subject_id="other-subject",
                claims=tuple(
                    replace(item, subject_id="other-subject", claim_hash=None)
                    for item in case.claims
                ),
                case_hash=None,
            ),
            replace(
                case,
                environment="RESEARCH",
                claims=tuple(
                    replace(item, environment="RESEARCH", claim_hash=None)
                    for item in case.claims
                ),
                case_hash=None,
            ),
            replace(
                case,
                source_snapshot_hash="sha256:" + "1" * 64,
                case_hash=None,
            ),
            replace(case, detector_version="p07-other-detector", case_hash=None),
        )
        for altered in variants:
            with self.subTest(altered=altered.canonical_hash()):
                value = self.golden.detection.to_dict()
                value["cases"] = [altered.to_dict()]
                value["trace"] = trace.to_dict()
                with self.assertRaises(ContradictionValidationError):
                    ContradictionDetectionResult.from_dict(value)

    def test_all_resolution_basis_kinds_require_registry_backed_verification(self):
        references = (
            "user-correction:verified:v1",
            "source-supersession:verified:v2",
            "independent-corroboration:verified:v1",
            "evolution-record:verified:v1",
            "error-source-proof:verified:v1",
        )
        for index, reference in enumerate(references):
            with self.subTest(reference=reference):
                service, _, _ = build_p07_detector(self.root / f"basis-{index}")
                case = service.detect(self.golden.p06.composition).cases[0]
                resolved = service.resolve(
                    case.subject_id,
                    case.case_id,
                    p07_resolution_evidence(reference),
                )
                sealed = resolved.audit_history[-1].resolution
                self.assertIsNotNone(sealed)
                self.assertTrue(sealed.basis_reference_version)
                self.assertTrue(sealed.provenance_roots)
                self.assertEqual(sealed.request_hash[:7], "sha256:")

    def test_resolution_verifier_rejects_missing_hash_basis_and_version_drift(self):
        service, _, _ = build_p07_detector(self.root / "resolution-drift")
        case = service.detect(self.golden.p06.composition).cases[0]
        valid = p07_resolution_evidence("user-correction:verified:v1")
        variants = (
            replace(valid, basis_reference_id="user-correction:missing:v1"),
            replace(valid, source_hashes=(contradiction_hash("wrong-hash"),)),
            replace(valid, basis=ResolutionBasisKind.ERROR_SOURCE_PROOF),
            replace(valid, reason_code="VERIFIED_ERROR_SOURCE_PROOF"),
        )
        for evidence in variants:
            with self.subTest(reference=evidence.basis_reference_id):
                with self.assertRaises(ContradictionValidationError):
                    service.resolve(case.subject_id, case.case_id, evidence)

    def test_reopen_and_supersede_require_sealed_evidence_not_bare_hashes(self):
        service, _, _ = build_p07_detector(self.root / "trusted-lifecycle")
        case = service.detect(self.golden.p06.composition).cases[0]
        resolved = service.resolve(
            case.subject_id,
            case.case_id,
            p07_resolution_evidence("user-correction:verified:v1"),
        )
        with self.assertRaises(TypeError):
            service.reopen(
                case.subject_id,
                case.case_id,
                source_hashes=(contradiction_hash("bare"),),
            )
        reopened = service.reopen(
            case.subject_id,
            case.case_id,
            p07_resolution_evidence("independent-corroboration:new:v1"),
        )
        self.assertEqual(reopened.status, ContradictionStatus.REOPENED)
        superseded = service.supersede(
            case.subject_id,
            case.case_id,
            p07_resolution_evidence("source-supersession:verified:v2"),
        )
        self.assertEqual(superseded.status, ContradictionStatus.SUPERSEDED)
        self.assertEqual(
            superseded.audit_history[-1].resolution.basis,
            ResolutionBasisKind.SOURCE_SUPERSESSION,
        )
        self.assertEqual(resolved.claims, superseded.claims)

    def test_resolution_audit_rejects_rehashed_foreign_evidence_before_persistence(self):
        service, repository, _ = build_p07_detector(self.root / "foreign-resolution")
        case = service.detect(self.golden.p06.composition).cases[0]
        original = self.golden.resolved.audit_history[-1]
        with self.assertRaises(ContradictionValidationError):
            foreign = replace(
                original.resolution, subject_id="different-subject",
                environment="RESEARCH", verification_hash=None,
            )
            audit = replace(original, resolution=foreign)
            altered = transition_case(
                case, status=ContradictionStatus.RESOLVED, audit=audit,
                verification_status=VerificationStatus.COMPLETED,
            )
            repository.append_transition(altered)
            restarted, reloaded, _ = build_p07_detector(self.root / "foreign-resolution")
            self.assertEqual(reloaded.load_case(case.subject_id, case.case_id).status,
                             ContradictionStatus.RESOLVED)
            self.assertEqual(restarted.detect(self.golden.p06.composition).cases[0].status,
                             ContradictionStatus.RESOLVED)

    def test_resolution_evidence_cannot_resolve_unrelated_proposition_and_scope(self):
        from continuity_engine.testing.p07_contradiction_fixture import P07StructuredClaimFixtureResolver

        first, second = self.golden.p06.composition.snapshot.fragments[:2]
        resolver = P07StructuredClaimFixtureResolver()
        resolver._mapping = {
            first.stable_source_id: ClaimProjection(
                "unrelated.weather", True, "AFFIRMS", "external", "FACTUAL", "unrelated"
            ),
            second.stable_source_id: ClaimProjection(
                "unrelated.weather", False, "AFFIRMS", "external", "FACTUAL", "unrelated"
            ),
        }
        service, repository, _ = build_p07_detector(self.root / "unrelated", resolver=resolver)
        case = service.detect(self.golden.p06.composition).cases[0]
        with self.assertRaises(ContradictionValidationError):
            service.resolve(case.subject_id, case.case_id,
                            p07_resolution_evidence("user-correction:verified:v1"))
        self.assertEqual(repository.load_case(case.subject_id, case.case_id), case)

    def test_resolution_audit_action_reason_hashes_and_time_are_sealed(self):
        audit = self.golden.resolved.audit_history[-1]
        for change in (
            {"action": AuditAction.REOPENED},
            {"reason_code": "UNRELATED_REASON"},
            {"source_hashes": (contradiction_hash("unrelated-evidence"),)},
            {"occurred_at": audit.occurred_at + timedelta(seconds=1)},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ContradictionValidationError):
                    replace(audit, **change)
                serialized = audit.to_dict()
                serialized.update({key: (value.value if isinstance(value, AuditAction)
                                         else value.isoformat() if isinstance(value, datetime)
                                         else value) for key, value in change.items()})
                with self.assertRaises(ContradictionValidationError):
                    ContradictionAuditEntry.from_dict(serialized)

    def test_rehashed_resolution_boundary_tamper_rejected_on_reload_and_detect(self):
        _, repository, _ = build_p07_detector(self.root)
        path = repository._path(self.initial.subject_id)
        original = json.loads(path.read_text(encoding="utf-8"))
        variants = {
            "subject_id": "different-subject", "environment": "RESEARCH",
            "target_case_id": "different-case", "target_case_revision": 1,
            "target_case_hash": contradiction_hash("foreign-case"),
            "source_snapshot_hash": contradiction_hash("foreign-snapshot"),
            "detector_version": "foreign-detector", "proposition_id": "unrelated.weather",
            "scope_id": "unrelated", "target_claim_hashes": [contradiction_hash("foreign-claim")],
        }
        for field, value in variants.items():
            with self.subTest(field=field):
                document = json.loads(json.dumps(original))
                record = document["case_records"][1]
                evidence = record["audit_history"][-1]["resolution"]
                evidence[field] = value
                evidence["request_hash"] = ResolutionEvidence.from_dict(
                    {**evidence, "verified": False}).canonical_hash()
                evidence["verification_hash"] = contradiction_hash(
                    {k: v for k, v in evidence.items() if k != "verification_hash"})
                record["case_hash"] = contradiction_hash(
                    {k: v for k, v in record.items() if k != "case_hash"})
                with self.assertRaises(ContradictionValidationError):
                    ContradictionCase.from_dict(record)
                document["document_hash"] = contradiction_hash(
                    {k: v for k, v in document.items() if k != "document_hash"})
                path.write_text(json.dumps(document), encoding="utf-8")
                restarted, reloaded, _ = build_p07_detector(self.root)
                with self.assertRaises(ContradictionPersistenceError):
                    reloaded.load_case(self.initial.subject_id, self.initial.case_id)
                with self.assertRaises(ContradictionPersistenceError):
                    restarted.detect(self.golden.p06.composition)
        path.write_text(json.dumps(original), encoding="utf-8")

    def test_cached_verified_proof_cannot_cross_case_snapshot_or_revision(self):
        from continuity_engine.services.contradiction_detector_service import ContradictionDetectorService
        from continuity_engine.testing.p07_contradiction_fixture import P07StructuredClaimFixtureResolver

        proof = self.golden.resolved.audit_history[-1].resolution
        class CachedVerifier:
            def verify(self, case, evidence, *, action):
                return proof
        for index, changes in enumerate((
            {"case_id": "other-case"},
            {"source_snapshot_hash": contradiction_hash("other-snapshot")},
            {"detector_version": "other-version"},
        )):
            with self.subTest(changes=changes):
                _, repository, _ = build_p07_detector(self.root / f"proof-{index}")
                other = replace(self.initial, **changes, case_hash=None)
                repository.save_detected(other)
                service = ContradictionDetectorService(
                    P07StructuredClaimFixtureResolver(), repository,
                    resolution_evidence_verifier=CachedVerifier())
                with self.assertRaises(ContradictionValidationError):
                    service.resolve(other.subject_id, other.case_id,
                                    p07_resolution_evidence("user-correction:verified:v1"))
        with self.assertRaises(ContradictionValidationError):
            transition_case(self.golden.reopened, status=ContradictionStatus.RESOLVED,
                            audit=replace(self.golden.resolved.audit_history[-1],
                                          sequence=len(self.golden.reopened.audit_history)),
                            verification_status=VerificationStatus.COMPLETED)

    def test_all_five_basis_reject_unrelated_scope_and_target_source_drift(self):
        references = ("user-correction:verified:v1", "source-supersession:verified:v2",
                      "independent-corroboration:verified:v1", "evolution-record:verified:v1",
                      "error-source-proof:verified:v1")
        verifier = P07DeterministicResolutionEvidenceVerifier()
        target = next(c for c in self.initial.claims if c.stable_source_id == "memory:day2-argument-fact")
        for reference in references:
            for changes in (
                {"source_id": "unrelated.source"}, {"source_version": "revision:999"},
                {"source_content_hash": contradiction_hash("unrelated-content")},
                {"provenance_roots": ("event:unrelated",)},
                {"canonical_value_hash": contradiction_hash("unrelated-value")},
            ):
                with self.subTest(reference=reference, changes=changes):
                    claims = tuple(replace(c, **changes, claim_hash=None) if c is target else c
                                   for c in self.initial.claims)
                    other = replace(self.initial, claims=claims, case_hash=None)
                    with self.assertRaises(ValueError):
                        verifier.verify(other, p07_resolution_evidence(reference), action=AuditAction.RESOLVED)
            for prop, scope in (("unrelated.weather", self.initial.scope_id),
                                (self.initial.proposition_id, "unrelated")):
                with self.subTest(reference=reference, proposition=prop, scope=scope):
                    other = replace(self.initial, proposition_id=prop, scope_id=scope,
                                    claims=tuple(replace(c, proposition_id=prop, scope_id=scope, claim_hash=None)
                                                 for c in self.initial.claims), case_hash=None)
                    with self.assertRaises(ValueError):
                        verifier.verify(other, p07_resolution_evidence(reference), action=AuditAction.RESOLVED)

    def test_repository_reverifies_rehashed_evidence_record_and_version(self):
        _, repository, _ = build_p07_detector(self.root)
        path = repository._path(self.initial.subject_id)
        original = json.loads(path.read_text(encoding="utf-8"))
        # Keep only origin/resolution, so invalidity cannot be attributed to a later prefix.
        original["case_records"] = original["case_records"][:2]
        for field, value in (("basis_reference_version", "version:999"),
                             ("basis_reference_id", "user-correction:missing"),
                             ("provenance_roots", ["event:unrelated"]),
                             ("verifier_id", "untrusted-verifier")):
            with self.subTest(field=field):
                document = json.loads(json.dumps(original))
                record = document["case_records"][1]
                proof = record["audit_history"][-1]["resolution"]
                proof[field] = value
                proof["request_hash"] = ResolutionEvidence.from_dict({**proof, "verified": False}).canonical_hash()
                proof["verification_hash"] = contradiction_hash({k:v for k,v in proof.items() if k != "verification_hash"})
                record["case_hash"] = contradiction_hash({k:v for k,v in record.items() if k != "case_hash"})
                parsed = ContradictionCase.from_dict(record)
                # Self-consistent domain hashes are not a substitute for trusted repository verification.
                _, empty_repo, _ = build_p07_detector(self.root / f"append-{field}")
                empty_repo.save_detected(self.initial)
                with self.assertRaises(ContradictionValidationError):
                    empty_repo.append_transition(parsed)
                document["document_hash"] = contradiction_hash({k:v for k,v in document.items() if k != "document_hash"})
                path.write_text(json.dumps(document), encoding="utf-8")
                service, restarted, _ = build_p07_detector(self.root)
                with self.assertRaises(ContradictionPersistenceError):
                    restarted.load_case(self.initial.subject_id, self.initial.case_id)
                with self.assertRaises(ContradictionPersistenceError):
                    service.detect(self.golden.p06.composition)

    def test_legal_bound_resolve_reopen_supersede_survive_restart_and_replay(self):
        service, repository, _ = build_p07_detector(self.root)
        superseded = service.supersede(self.initial.subject_id, self.initial.case_id,
                                      p07_resolution_evidence("source-supersession:verified:v2"))
        history = repository.case_history(self.initial.subject_id, self.initial.case_id)
        for previous, current in zip(history, history[1:]):
            proof = current.audit_history[-1].resolution
            self.assertEqual(proof.target_case_hash, previous.canonical_hash())
            self.assertEqual(proof.target_case_revision, previous.revision)
            self.assertEqual(proof.target_claim_hashes, tuple(c.claim_hash for c in previous.claims))
            self.assertEqual(proof.allowed_action, current.audit_history[-1].action)
            self.assertEqual(VerifiedResolutionEvidence.from_dict(proof.to_dict()), proof)
        restarted, reloaded, _ = build_p07_detector(self.root)
        self.assertEqual(reloaded.load_case(self.initial.subject_id, self.initial.case_id), superseded)
        self.assertEqual(restarted.detect(self.golden.p06.composition).cases[0], superseded)
        self.assertEqual(len(reloaded.case_history(self.initial.subject_id, self.initial.case_id)), 4)

    def test_repository_without_trusted_verifier_cannot_load_resolved_audit(self):
        from continuity_engine.storage.json_contradiction_repository import JsonContradictionRepository
        repository = JsonContradictionRepository(self.root, environment="TEST")
        with self.assertRaises(ContradictionPersistenceError):
            repository.load_case(self.initial.subject_id, self.initial.case_id)

    def test_verified_resolution_request_hash_and_action_reuse_fail_closed(self):
        proof = self.golden.resolved.audit_history[-1].resolution
        with self.assertRaises(ContradictionValidationError):
            replace(proof, resolved_at=proof.resolved_at + timedelta(seconds=1), verification_hash=None)
        with self.assertRaises(ContradictionValidationError):
            replace(proof, allowed_action=AuditAction.REOPENED, verification_hash=None)
        with self.assertRaises(ContradictionValidationError):
            replace(proof, allowed_action=AuditAction.SUPERSEDED, verification_hash=None)


if __name__ == "__main__":
    unittest.main()
