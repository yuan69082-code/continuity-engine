from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from continuity_engine.domain.context_composition import (
    CompositionStatus,
    ContextCompositionResult,
    composition_hash,
)
from continuity_engine.domain.contradiction import (
    ClaimDisposition,
    ClaimDomain,
    ClaimEvidenceType,
    ClaimPolarity,
    ClaimProjection,
    ContradictionDetectionStatus,
    ContradictionKind,
    ContradictionStatus,
)
from continuity_engine.domain.errors import ContradictionValidationError
from continuity_engine.services.contradiction_detector_service import (
    ContradictionDetectorService,
)
from continuity_engine.testing.p06_context_fixture import run_p06_golden_scenario
from continuity_engine.testing.p07_contradiction_fixture import (
    P07DeterministicSourceVersionVerifier,
    P07StructuredClaimFixtureResolver,
    build_p07_detector,
    run_p07_golden_scenario,
)


class _ByFragmentResolver:
    def __init__(self, values):
        self.values = values

    def project(self, fragment):
        return self.values.get(fragment.fragment_id)


class P07ContradictionDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.p06 = run_p06_golden_scenario(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_golden_detects_isolates_resolves_restarts_and_reopens_without_writes(self):
        golden = run_p07_golden_scenario(self.root / "golden")
        case = golden.detection.cases[0]
        self.assertEqual(golden.version, "p07-contradiction-golden-v1")
        self.assertEqual(case.kind, ContradictionKind.COGNITIVE)
        self.assertEqual(case.status, ContradictionStatus.PENDING_VERIFICATION)
        self.assertEqual(golden.resolved.status, ContradictionStatus.RESOLVED)
        self.assertEqual(golden.reloaded.canonical_hash(), golden.resolved.canonical_hash())
        self.assertEqual(golden.reopened.status, ContradictionStatus.REOPENED)
        self.assertEqual(golden.subject_document_hash_before, golden.subject_document_hash_after)
        self.assertEqual(golden.memory_document_hash_before, golden.memory_document_hash_after)
        self.assertEqual(golden.p06_hash_before, golden.p06_hash_after)

    def test_p06_non_complete_result_is_rejected_without_claim_reads(self):
        resolver = P07StructuredClaimFixtureResolver()
        service = ContradictionDetectorService(resolver)
        trace = replace(
            self.p06.composition.trace,
            status=CompositionStatus.INCOMPLETE,
            trace_hash=None,
        )
        result = service.detect(
            ContextCompositionResult(
                CompositionStatus.INCOMPLETE,
                trace,
                error_code="REQUIRED_MATERIAL_MISSING",
            )
        )
        self.assertEqual(result.status, ContradictionDetectionStatus.REJECTED)
        self.assertEqual(resolver.calls, [])

    def test_p06_manifest_hash_mismatch_fails_before_claim_resolution(self):
        resolver = P07StructuredClaimFixtureResolver()
        service = ContradictionDetectorService(resolver)
        value = self.p06.composition.to_dict()
        value["snapshot"]["manifest_hash"] = "sha256:" + "1" * 64
        canonical = dict(value["snapshot"])
        canonical.pop("snapshot_hash")
        value["snapshot"]["snapshot_hash"] = composition_hash(canonical)
        tampered = ContextCompositionResult.from_dict(value)
        with self.assertRaisesRegex(ContradictionValidationError, "BINDING"):
            service.detect(tampered)
        self.assertEqual(resolver.calls, [])

    def test_cross_subject_or_environment_binding_fails_closed(self):
        resolver = P07StructuredClaimFixtureResolver()
        service = ContradictionDetectorService(resolver)
        snapshot = self.p06.composition.snapshot
        fragments = tuple(
            replace(item, subject_id="another-subject") for item in snapshot.fragments
        )
        altered = replace(
            snapshot,
            subject_id="another-subject",
            fragments=fragments,
            snapshot_hash=None,
        )
        composition = ContextCompositionResult(
            CompositionStatus.COMPLETE,
            self.p06.composition.trace,
            altered,
        )
        with self.assertRaisesRegex(ContradictionValidationError, "BINDING"):
            service.detect(composition)

    def test_unstructured_text_is_unassessed_not_guessed(self):
        resolver = P07StructuredClaimFixtureResolver(
            {key: None for key in [item.stable_source_id for item in self.p06.composition.snapshot.fragments]}
        )
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(result.cases, ())
        self.assertEqual(result.trace.evaluated_count, 0)
        self.assertEqual(result.trace.unassessed_count, result.trace.fragment_count)

    def test_same_claim_is_deduplicated_without_false_contradiction(self):
        same = ClaimProjection(
            "shared.proposition",
            True,
            ClaimPolarity.AFFIRMS,
            ClaimEvidenceType.EXPERIENTIAL,
            ClaimDomain.FACTUAL,
            "shared:scope",
        )
        ids = [item.stable_source_id for item in self.p06.composition.snapshot.fragments[:2]]
        resolver = P07StructuredClaimFixtureResolver({ids[0]: same, ids[1]: same})
        resolver._mapping = {ids[0]: same, ids[1]: same}
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(result.cases, ())

    def test_different_proposition_and_time_scope_do_not_false_positive(self):
        first, second = self.p06.composition.snapshot.fragments[:2]
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "weather.rain", True, "AFFIRMS", "external", "FACTUAL", "day:one"
                ),
                second.fragment_id: ClaimProjection(
                    "weather.rain", False, "DENIES", "external", "FACTUAL", "day:two"
                ),
            }
        )
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(result.cases, ())

    def test_epistemic_and_evidential_kinds_are_deterministic(self):
        first, second = self.p06.composition.snapshot.fragments[4:6]
        base = {
            first.fragment_id: ClaimProjection(
                "fact.answer", "yes", "AFFIRMS", "experiential", "FACTUAL", "same"
            ),
            second.fragment_id: ClaimProjection(
                "fact.answer", "no", "AFFIRMS", "experiential", "FACTUAL", "same"
            ),
        }
        epistemic = ContradictionDetectorService(_ByFragmentResolver(base)).detect(
            self.p06.composition
        )
        self.assertEqual(epistemic.cases[0].kind, ContradictionKind.EPISTEMIC)
        evidential_map = dict(base)
        evidential_map[first.fragment_id] = replace(
            base[first.fragment_id], evidence_type=ClaimEvidenceType.ANALYTICAL
        )
        evidential_map[second.fragment_id] = replace(
            base[second.fragment_id], evidence_type=ClaimEvidenceType.EXTERNAL
        )
        evidential = ContradictionDetectorService(
            _ByFragmentResolver(evidential_map)
        ).detect(self.p06.composition)
        self.assertEqual(evidential.cases[0].kind, ContradictionKind.EVIDENTIAL)

    def test_love_and_hate_psychological_ambivalence_is_explicitly_excluded(self):
        first, second = self.p06.composition.snapshot.fragments[:2]
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "psychological.relationship", "love", "AFFIRMS", "experiential", "PSYCHOLOGICAL", "now"
                ),
                second.fragment_id: ClaimProjection(
                    "psychological.relationship", "hate", "AFFIRMS", "experiential", "PSYCHOLOGICAL", "now"
                ),
            }
        )
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(result.cases, ())
        self.assertEqual(result.trace.psychological_excluded_count, 2)

    def test_derived_summary_conflict_is_isolated_and_never_promoted(self):
        service, _, _ = build_p07_detector(self.root)
        result = service.detect(self.p06.composition)
        summary_claim = next(
            item
            for item in result.cases[0].claims
            if item.authority.value == "derived_summary"
        )
        disposition = next(
            item for item in result.cases[0].dispositions if item.claim_id == summary_claim.claim_id
        )
        self.assertEqual(disposition.disposition, ClaimDisposition.ISOLATED)
        self.assertEqual(summary_claim.authority.value, "derived_summary")

    def test_user_correction_or_revocation_remains_evidence_not_direct_state_change(self):
        first, second = self.p06.composition.snapshot.fragments[4:6]
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "profile.name", "old", "AFFIRMS", "analytical", "COGNITIVE", "current"
                ),
                second.fragment_id: ClaimProjection(
                    "profile.name", "corrected", "AFFIRMS", "external", "FACTUAL", "current"
                ),
            }
        )
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(result.cases[0].kind, ContradictionKind.EVIDENTIAL)
        self.assertFalse(result.direct_state_write_allowed)
        self.assertFalse(result.evolution_commit_allowed)

    def test_same_source_new_version_with_explicit_supersession_is_not_conflict(self):
        first, second = self.p06.composition.snapshot.fragments[:2]
        new_second = replace(
            second,
            fragment_id="sha256:" + "2" * 64,
            source_id=first.source_id,
            stable_source_id=first.stable_source_id,
            version="revision:3",
            content_hash="sha256:" + "3" * 64,
            content="new version",
        )
        fragments = list(self.p06.composition.snapshot.fragments)
        fragments[1] = new_second
        snapshot = replace(
            self.p06.composition.snapshot,
            fragments=tuple(fragments),
            snapshot_hash=None,
        )
        composition = ContextCompositionResult(
            CompositionStatus.COMPLETE,
            self.p06.composition.trace,
            snapshot,
        )
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "versioned.fact", "old", "AFFIRMS", "external", "FACTUAL", "same"
                ),
                new_second.fragment_id: ClaimProjection(
                    "versioned.fact",
                    "new",
                    "AFFIRMS",
                    "external",
                    "FACTUAL",
                    "same",
                    (first.fragment_id,),
                ),
            }
        )
        result = ContradictionDetectorService(
            resolver,
            supersession_verifier=P07DeterministicSourceVersionVerifier(),
        ).detect(composition)
        self.assertEqual(result.cases, ())

    def test_older_claim_cannot_self_report_supersession_of_newer_claim(self):
        first, second = self.p06.composition.snapshot.fragments[:2]
        newer = replace(
            second,
            fragment_id="sha256:" + "2" * 64,
            source_id=first.source_id,
            stable_source_id=first.stable_source_id,
            version="revision:3",
            content_hash="sha256:" + "3" * 64,
            content="new version",
        )
        fragments = list(self.p06.composition.snapshot.fragments)
        fragments[1] = newer
        snapshot = replace(
            self.p06.composition.snapshot,
            fragments=tuple(fragments),
            snapshot_hash=None,
        )
        composition = ContextCompositionResult(
            CompositionStatus.COMPLETE,
            self.p06.composition.trace,
            snapshot,
        )
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "versioned.fact",
                    "old",
                    "AFFIRMS",
                    "external",
                    "FACTUAL",
                    "same",
                    (newer.fragment_id,),
                ),
                newer.fragment_id: ClaimProjection(
                    "versioned.fact",
                    "new",
                    "AFFIRMS",
                    "external",
                    "FACTUAL",
                    "same",
                ),
            }
        )
        with self.assertRaises(ContradictionValidationError):
            ContradictionDetectorService(resolver).detect(composition)

    def test_repository_never_persists_plaintext_canonical_values(self):
        secret = "Authorization: Bearer p07-sensitive-credential"
        first, second = self.p06.composition.snapshot.fragments[:2]
        resolver = _ByFragmentResolver(
            {
                first.fragment_id: ClaimProjection(
                    "secret.fact", secret, "AFFIRMS", "external", "FACTUAL", "same"
                ),
                second.fragment_id: ClaimProjection(
                    "secret.fact", "different", "AFFIRMS", "external", "FACTUAL", "same"
                ),
            }
        )
        service, repository, _ = build_p07_detector(
            self.root / "secret-persistence", resolver=resolver
        )
        result = service.detect(self.p06.composition)
        self.assertEqual(len(result.cases), 1)
        payload = repository._path(result.cases[0].subject_id).read_text(encoding="utf-8")
        self.assertNotIn(secret, payload)
        self.assertNotIn("canonical_value", json.loads(payload)["case_records"][0]["claims"][0])

    def test_repository_seals_long_secret_and_scalar_values_across_restart(self):
        values = (
            "credential=" + "sensitive-" * 256,
            "Bearer p07-secret-token-value",
            9876543210123456789,
            True,
            None,
        )
        for index, value in enumerate(values):
            with self.subTest(index=index, value_type=type(value).__name__):
                first, second = self.p06.composition.snapshot.fragments[:2]
                resolver = _ByFragmentResolver(
                    {
                        first.fragment_id: ClaimProjection(
                            f"sealed.scalar.{index}",
                            value,
                            "AFFIRMS",
                            "external",
                            "FACTUAL",
                            "same",
                        ),
                        second.fragment_id: ClaimProjection(
                            f"sealed.scalar.{index}",
                            f"different-{index}",
                            "AFFIRMS",
                            "external",
                            "FACTUAL",
                            "same",
                        ),
                    }
                )
                root = self.root / f"sealed-scalar-{index}"
                service, repository, _ = build_p07_detector(root, resolver=resolver)
                detected = service.detect(self.p06.composition)
                path = repository._path(detected.cases[0].subject_id)
                payload = path.read_text(encoding="utf-8")
                document = json.loads(payload)
                for claim in document["case_records"][0]["claims"]:
                    self.assertNotIn("canonical_value", claim)
                    self.assertRegex(claim["canonical_value_hash"], r"^sha256:[0-9a-f]{64}$")
                if isinstance(value, str):
                    self.assertNotIn(value, payload)
                _, restarted, _ = build_p07_detector(root, resolver=resolver)
                restored = restarted.load_case(
                    detected.cases[0].subject_id, detected.cases[0].case_id
                )
                self.assertEqual(restored.canonical_hash(), detected.cases[0].canonical_hash())

    def test_supersession_missing_same_version_cross_source_and_mutual_fail_closed(self):
        first, second = self.p06.composition.snapshot.fragments[:2]

        def composition_for(candidate):
            fragments = list(self.p06.composition.snapshot.fragments)
            fragments[1] = candidate
            snapshot = replace(
                self.p06.composition.snapshot,
                fragments=tuple(fragments),
                snapshot_hash=None,
            )
            return ContextCompositionResult(
                CompositionStatus.COMPLETE,
                self.p06.composition.trace,
                snapshot,
            )

        same_version = replace(
            second,
            fragment_id="sha256:" + "4" * 64,
            source_id=first.source_id,
            stable_source_id=first.stable_source_id,
            version=first.version,
            content_hash="sha256:" + "5" * 64,
        )
        cross_source = replace(
            same_version,
            fragment_id="sha256:" + "6" * 64,
            source_id="different.source",
            stable_source_id="different:stable",
            version="revision:3",
        )
        scenarios = (
            (
                "missing",
                second,
                ("sha256:" + "9" * 64,),
                (),
            ),
            (
                "same-version",
                same_version,
                (),
                (first.fragment_id,),
            ),
            (
                "cross-source",
                cross_source,
                (),
                (first.fragment_id,),
            ),
            (
                "mutual",
                replace(same_version, version="revision:3"),
                (same_version.fragment_id,),
                (first.fragment_id,),
            ),
        )
        for name, candidate, first_targets, second_targets in scenarios:
            with self.subTest(name=name):
                resolver = _ByFragmentResolver(
                    {
                        first.fragment_id: ClaimProjection(
                            "versioned.invalid",
                            "old",
                            "AFFIRMS",
                            "external",
                            "FACTUAL",
                            "same",
                            first_targets,
                        ),
                        candidate.fragment_id: ClaimProjection(
                            "versioned.invalid",
                            "new",
                            "AFFIRMS",
                            "external",
                            "FACTUAL",
                            "same",
                            second_targets,
                        ),
                    }
                )
                with self.assertRaises(ContradictionValidationError):
                    ContradictionDetectorService(
                        resolver,
                        supersession_verifier=P07DeterministicSourceVersionVerifier(),
                    ).detect(composition_for(candidate))

    def test_trusted_supersession_binding_rejects_cross_boundary_and_reverse_direction(self):
        old, template = self.p06.composition.snapshot.fragments[:2]
        new = replace(
            template,
            source_id=old.source_id,
            stable_source_id=old.stable_source_id,
            version="revision:3",
            occurred_at=old.occurred_at,
        )
        verifier = P07DeterministicSourceVersionVerifier()
        self.assertTrue(verifier.verify(new, old))
        self.assertFalse(verifier.verify(old, new))
        self.assertFalse(verifier.verify(replace(new, subject_id="other-subject"), old))
        self.assertFalse(verifier.verify(replace(new, environment="RESEARCH"), old))

    def test_missing_required_resolution_evidence_cannot_be_hidden_by_optional_success(self):
        service, _, _ = build_p07_detector(self.root)
        case = service.detect(self.p06.composition).cases[0]
        with self.assertRaises(ContradictionValidationError):
            service.resolve(case.subject_id, case.case_id, None)

    def test_detector_fault_is_attributed_to_p07_and_does_not_write_repository(self):
        fragment = self.p06.composition.snapshot.fragments[0]
        resolver = P07StructuredClaimFixtureResolver(fail_fragment_id=fragment.fragment_id)
        service, repository, _ = build_p07_detector(self.root, resolver=resolver)
        with self.assertRaisesRegex(ContradictionValidationError, "P07_CLAIM_RESOLVER_FAILED"):
            service.detect(self.p06.composition)
        self.assertEqual(repository.list_cases(self.p06.composition.snapshot.subject_id), [])

    def test_detection_is_deterministic_across_restart_and_clock_changes(self):
        first_service, _, _ = build_p07_detector(self.root)
        first = first_service.detect(self.p06.composition)
        second_service, _, _ = build_p07_detector(self.root)
        second = second_service.detect(self.p06.composition)
        self.assertEqual(first.canonical_hash(), second.canonical_hash())

    def test_detector_reads_each_snapshot_fragment_once_and_never_reroutes(self):
        resolver = P07StructuredClaimFixtureResolver()
        result = ContradictionDetectorService(resolver).detect(self.p06.composition)
        self.assertEqual(len(resolver.calls), len(self.p06.composition.snapshot.fragments))
        self.assertEqual(len(set(resolver.calls)), len(resolver.calls))
        self.assertEqual(result.trace.fragment_count, len(resolver.calls))

    def test_candidate_missing_and_upstream_notice_counts_remain_distinct(self):
        result = ContradictionDetectorService(
            P07StructuredClaimFixtureResolver()
        ).detect(self.p06.composition)
        self.assertEqual(
            result.trace.candidate_missing_count,
            self.p06.composition.trace.missing_count,
        )
        self.assertEqual(
            result.trace.upstream_notice_count,
            self.p06.composition.trace.upstream_notice_count,
        )
        self.assertEqual(result.trace.candidate_missing_count, 0)
        self.assertEqual(result.trace.upstream_notice_count, 5)

    def test_conflict_marker_without_structured_claim_never_creates_case(self):
        snapshot = self.p06.composition.snapshot
        first = replace(
            snapshot.fragments[0], conflict_markers=("UNTRUSTED_CONFLICT_MARKER",)
        )
        altered = replace(
            snapshot,
            fragments=(first,) + snapshot.fragments[1:],
            snapshot_hash=None,
        )
        composition = ContextCompositionResult(
            CompositionStatus.COMPLETE,
            self.p06.composition.trace,
            altered,
        )
        result = ContradictionDetectorService(_ByFragmentResolver({})).detect(composition)
        self.assertEqual(result.cases, ())
        self.assertEqual(result.trace.evaluated_count, 0)


if __name__ == "__main__":
    unittest.main()
