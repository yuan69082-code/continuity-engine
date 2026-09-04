from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.context_composition import ContextAuthority, ContextBudget
from continuity_engine.domain.contradiction import (
    ClaimProjection, ClaimPolarity, ClaimEvidenceType, ClaimDomain, ClaimDisposition,
    ContradictionStatus, ResolutionEvidence, ResolutionBasisKind,
    VerifiedResolutionEvidence, AuditAction, contradiction_hash,
)
from continuity_engine.domain.errors import ContradictionValidationError
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification
from continuity_engine.testing.p09_core_fixture import P09Fixture, P09_TIME
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.storage.json_contradiction_repository import JsonContradictionRepository


class RegisteredProof:
    """A TEST proof registry bound to sources before detection, never to model text."""
    def __init__(self):
        self.targets = {}

    def register(self, subject, memories):
        self.subject = subject
        self.targets = {m.memory_id: (f"revision:{m.revision}", m.canonical_hash(),
            tuple(m.root_evidence_ids), contradiction_hash(value)) for m, value in memories}
        self.evidence = ResolutionEvidence("p09-proof", subject, "TEST", ResolutionBasisKind.ERROR_SOURCE_PROOF,
            "test:independent-error-proof", (contradiction_hash("registered synthetic error proof"),),
            "VERIFIED_ERROR_SOURCE_PROOF", P09_TIME)

    def verify(self, case, evidence, *, action):
        if (evidence.canonical_hash() != self.evidence.canonical_hash() or action is not AuditAction.RESOLVED
                or case.subject_id != self.subject or case.environment != "TEST"
                or case.proposition_id != "c1.fixture.claim" or case.scope_id != "c1.fixture.scope"):
            raise ValueError("unregistered evidence or wrong target")
        applicable = [c for c in case.claims if c.stable_source_id in self.targets]
        if {c.stable_source_id for c in applicable} != set(self.targets):
            raise ValueError("missing target source")
        for claim in applicable:
            if ((claim.source_version, claim.source_content_hash, claim.provenance_roots,
                 claim.canonical_value_hash) != self.targets[claim.stable_source_id]
                    or claim.authority is not ContextAuthority.CONFIRMED_MEMORY
                    or claim.source_id != "engine.memory"):
                raise ValueError("target version/hash/provenance drift")
        return VerifiedResolutionEvidence(
            resolution_id=evidence.resolution_id, subject_id=self.subject, environment="TEST",
            basis=evidence.basis, basis_reference_id=evidence.basis_reference_id,
            basis_reference_version="version:1", source_hashes=evidence.source_hashes,
            provenance_roots=("test:independent-error-proof",), reason_code=evidence.reason_code,
            resolved_at=evidence.resolved_at, verifier_id="p09-registered-proof-v1",
            request_hash=evidence.canonical_hash(), target_case_id=case.case_id,
            target_case_revision=case.revision, target_case_hash=case.canonical_hash(),
            source_snapshot_hash=case.source_snapshot_hash, detector_version=case.detector_version,
            proposition_id=case.proposition_id, scope_id=case.scope_id,
            target_claim_hashes=tuple(c.claim_hash for c in case.claims),
            applicable_claim_hashes=tuple(c.claim_hash for c in applicable), allowed_action=action)


class Claims:
    def project(self, fragment):
        values = {"memory:claim-old": "old", "memory:claim-new": "new"}
        value = values.get(fragment.stable_source_id)
        if fragment.authority is ContextAuthority.DERIVED_SUMMARY:
            value = "derived mixed"
        if value is None:
            return None
        return ClaimProjection("c1.fixture.claim", value, ClaimPolarity.AFFIRMS,
            ClaimEvidenceType.EXPERIENTIAL if fragment.authority is ContextAuthority.CONFIRMED_MEMORY
            else ClaimEvidenceType.ANALYTICAL, ClaimDomain.FACTUAL, "c1.fixture.scope")


class P09ContradictionTests(unittest.TestCase):
    def test_normal_chain_isolates_claims_trusted_resolution_never_advances_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            proof = RegisteredProof()
            f = P09Fixture(Path(directory), resolution_verifier=proof,
                context_budget=ContextBudget(core_fragment_limit=15, token_limit=4096))
            f.event("claim-old", content="continuity old synthetic claim")
            f.event("claim-new", content="continuity new synthetic claim")
            f.submit()  # Normal consolidation produces source records before the proof is registered.
            subject = f.runtime.descriptor.subject_id
            proof.register(subject, [(f.core.memory.load_memory(subject, "memory:claim-old"), "old"),
                                     (f.core.memory.load_memory(subject, "memory:claim-new"), "new")])
            f.core.detector._resolver = Claims()
            before_state = tree_inventory_hash(f.runtime.data_root / "subject-state")
            request = f.request()
            f.submit(request)
            context = f.context(request)
            self.assertEqual(len(context.contradictions.cases), 1)
            case = context.contradictions.cases[0]
            self.assertIs(case.status, ContradictionStatus.PENDING_VERIFICATION)
            self.assertTrue(any(d.disposition is ClaimDisposition.ISOLATED for d in case.dispositions))
            self.assertEqual(tree_inventory_hash(f.runtime.data_root / "subject-state"), before_state)
            with self.assertRaises(ContradictionValidationError):
                f.core.detector.resolve(subject, case.case_id, replace(proof.evidence,
                    basis_reference_id="unregistered-proof", verified=True))
            resolved = f.core.detector.resolve(subject, case.case_id, proof.evidence)
            self.assertIs(resolved.status, ContradictionStatus.RESOLVED)
            self.assertEqual(tree_inventory_hash(f.runtime.data_root / "subject-state"), before_state)
            restored = JsonContradictionRepository(f.runtime.data_root, environment="TEST",
                resolution_evidence_verifier=proof).load_case(subject, case.case_id)
            self.assertEqual(restored, resolved)
            f.event("explicit-legal-followup", classification=EventClassification.STATE_CHANGE, mutations=(
                StateMutation("relationship.current_status", ChangeOperation.SET, "explicit fixture followup",
                              "Separate authorized P01 Evolution, not a contradiction writer."),))
            self.assertEqual(f.runtime.subject_state().revision, 2)
            self.assertFalse(f.core.current(context))

    def test_repeated_summary_recall_never_promotes_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            f = P09Fixture(Path(directory), context_budget=ContextBudget(core_fragment_limit=15, token_limit=4096))
            f.event("summary-a")
            f.event("summary-b")
            subject = f.runtime.descriptor.subject_id
            for _ in range(3):
                request = f.request()
                f.submit(request)
                fragments = f.context(request).composition.snapshot.fragments
                summaries = [x for x in fragments if x.source_id == "engine.derived-summary"]
                self.assertTrue(summaries)
                self.assertTrue(all(x.authority is ContextAuthority.DERIVED_SUMMARY
                                    and not x.direct_state_write_allowed for x in summaries))
            self.assertEqual(f.runtime.subject_state().revision, 1)
            self.assertEqual(len(f.core.memory.list_summaries(subject)), 1)


if __name__ == "__main__":
    unittest.main()
