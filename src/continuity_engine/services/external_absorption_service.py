"""W02-C dispositions over independently receipted P16 results and current roots.

The P16 cache is only a rebuildable projection. E5-A remains the request/result
authority and the provider's current root port remains the source authority.
"""
from dataclasses import dataclass, replace
from datetime import timedelta
import re

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.external_absorption import (
    AbsorptionDecision, ExternalAbsorptionRecord, ExternalRootProof,
)
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.domain.memory import (
    MemoryEvidenceType, MemoryKind, MemoryRecord, MemoryTimeRange,
)
from continuity_engine.domain.errors import ContextCompositionSourceError, LearningValidationError
from .context_router_service import MemoryContextSource, DerivedSummaryContextSource


# This only catches an external material's claim to *control-plane* authority.
# It does not classify feelings, beliefs, truth, or ordinary subject expression.
_CONTROL_CLAIM = re.compile(
    # Require a command boundary and an explicit control-plane request. Mere
    # discussion such as “我不想改变人格” is ordinary untrusted material.
    r'(?:^|[。！？.!?\n:：“"「])\s*(?:请|务必|必须|马上|立即|现在)?\s*'
    r'(?:授权我|授予我|赋予我|允许我|跳过|绕过|修改我的|改变我的|修改人设|改变人设)'
    r'.{0,16}(?:权限|人设|人格|系统指令|安全检查)'
    r'|(?:^|[.!?\n:"“])\s*(?:please\s+)?'
    r'(?:grant me|give me|allow me|bypass|ignore|change my)'
    r'.{0,24}(?:permission|persona|system instruction|safety check)',
    re.I,
)
_EXTERNAL_MEMORY_PREFIX = 'External material reported: '


@dataclass(frozen=True)
class ExternalAbsorptionPolicy:
    """Explicit TEST/RESEARCH corroboration policy; no production default."""
    minimum_independent_roots: int
    minimum_confidence: float

    def __post_init__(self):
        if (type(self.minimum_independent_roots) is not int or not 2 <= self.minimum_independent_roots <= 8
                or type(self.minimum_confidence) not in (int, float)
                or not 0 <= self.minimum_confidence <= 1):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_POLICY_INVALID')


class ExternalAbsorptionService:
    def __init__(self, root_port, *, policy=None):
        self.root_port = root_port
        self.policy = policy
        self.external = None

    def bind(self, external):
        self.external = external

    def _proof(self, root_id):
        try:
            value = self.root_port.read_root(root_id)
            return ExternalRootProof.from_dict(value.to_dict())
        except Exception:
            # External diagnostics and exception chains can contain secrets.
            raise ExternalCapabilityError('EXTERNAL_ROOT_PROOF_UNAVAILABLE') from None

    def _decide(self, candidate, descriptor, *, historical=None):
        proofs = []
        for root in candidate.roots:
            try:
                proof = self._proof(root)
            except ExternalCapabilityError:
                return AbsorptionDecision(candidate.source_id, candidate.source_version,
                    candidate.content_hash, candidate.roots, tuple(digest('missing:'+r) for r in candidate.roots),
                    'NEEDS_EVIDENCE', 'ROOT_PROOF_UNAVAILABLE')
            proofs.append(proof)
        hashes = tuple(p.binding_hash for p in proofs)
        now = self.external.core.clock()
        disposition, reason = 'CANDIDATE', 'ROOT_CURRENT_EXTERNAL_CANDIDATE_NOT_FACT'
        if any((p.root_id, p.connector_id, p.descriptor_hash, p.subject_id, p.environment, p.read_scope) !=
               (root, descriptor.connector_id, digest(descriptor.to_dict()), descriptor.subject_id,
                descriptor.environment, descriptor.permission)
               for p, root in zip(proofs, candidate.roots)):
            disposition, reason = 'CONFLICT', 'ROOT_IDENTITY_OR_SCOPE_CONFLICT'
        elif any(p.status != 'ACTIVE' for p in proofs):
            disposition, reason = 'NOT_ADOPTED', 'ROOT_WITHDRAWN_OR_DELETED'
        elif any((now < parse_capability_datetime(p.observed_at)
                  or now >= parse_capability_datetime(p.valid_until)) for p in proofs):
            disposition, reason = 'NOT_ADOPTED', 'ROOT_TIME_INVALID'
        elif any(p.version != candidate.source_version or candidate.content_hash not in p.material_hashes
                 for p in proofs):
            disposition, reason = 'CONFLICT', 'ROOT_VERSION_OR_HASH_CONFLICT'
        elif any(p.material_role == 'INSTRUCTION' for p in proofs) or _CONTROL_CLAIM.search(candidate.content):
            disposition, reason = 'NOT_ADOPTED', 'EXTERNAL_CONTROL_CLAIM_HAS_NO_AUTHORITY'
        recovered_missing_proof = (historical is not None
                                   and historical.disposition == 'NEEDS_EVIDENCE'
                                   and historical.reason == 'ROOT_PROOF_UNAVAILABLE'
                                   and disposition == 'CANDIDATE')
        if recovered_missing_proof:
            # The receipted result is unchanged. A current proof can close the
            # original wait without another provider execution or request ID.
            reason = 'ROOT_PROOF_RECOVERED_CURRENT'
        elif historical is not None and (disposition, hashes) != (historical.disposition, historical.proof_hashes):
            # Changed source proof cannot silently upgrade or rebind an earlier
            # candidate. The original observation and its reasons remain intact.
            disposition, reason = 'NOT_ADOPTED', 'ROOT_CHANGED_SINCE_ACQUISITION'
        return AbsorptionDecision(candidate.source_id, candidate.source_version, candidate.content_hash,
                                  candidate.roots, hashes, disposition, reason)

    def assess(self, request, result, descriptor):
        acquired = self.external.core.clock()
        decisions = tuple(self._decide(candidate, descriptor) for candidate in result.candidates)
        record = ExternalAbsorptionRecord(request.capability_request_id, request.request_hash,
            digest(result.to_dict()), result.subject_id, result.environment,
            acquired.isoformat().replace('+00:00','Z'), decisions)
        record.validate_result(result)
        return record

    def current(self, request, result, stored):
        record = ExternalAbsorptionRecord.from_dict(stored)
        record.validate_result(result)
        if (record.request_id, record.request_hash, record.subject_id, record.environment) != (
                request.capability_request_id, request.request_hash, request.subject_id, request.choice.environment):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_BINDING')
        descriptor = self.external.descriptor_for(request)
        return replace(record, decisions=tuple(self._decide(candidate, descriptor, historical=decision)
                                               for candidate, decision in zip(result.candidates, record.decisions)))

    def current_root(self, root, expected_hash=None):
        try:
            proof = self._proof(root)
            descriptor = next((d for d, enabled in self.external.registry.descriptors()
                               if enabled and d.connector_id == proof.connector_id
                               and digest(d.to_dict()) == proof.descriptor_hash
                               and d.subject_id == proof.subject_id and d.environment == proof.environment
                               and d.permission == proof.read_scope), None)
            if descriptor is None:
                return False
            self.external.require_current(descriptor, 'consume')
            now = self.external.core.clock()
            return (proof.status == 'ACTIVE'
                    and proof.subject_id == self.external.core.subject_id
                    and proof.environment == self.external.core.environment
                    and parse_capability_datetime(proof.observed_at) <= now < parse_capability_datetime(proof.valid_until)
                    and (expected_hash is None or proof.binding_hash == expected_hash))
        except ExternalCapabilityError:
            return False

    def memory_current(self, memory):
        roots = [r for r in memory.source_message_ids if r.startswith('external:')]
        if not roots:
            return True
        if memory.evidence_type is not MemoryEvidenceType.EXTERNAL or len(roots) != len(memory.source_message_ids):
            return False
        # The root binding intentionally permits additional same-root renderings.
        # A durable P04 memory must still be supported by its *particular*
        # rendering at every read, including after a partial material withdrawal.
        if not memory.content.startswith(_EXTERNAL_MEMORY_PREFIX):
            return False
        material_hash = digest(memory.content[len(_EXTERNAL_MEMORY_PREFIX):])
        for root in roots:
            try:
                proof = self._proof(root)
            except ExternalCapabilityError:
                return False
            if ('w02c-proof:' + digest([root, proof.binding_hash])[7:] not in memory.tags
                    or material_hash not in proof.material_hashes
                    or not self.current_root(root, proof.binding_hash)):
                return False
        return True

    def summary_current(self, summary, memory_repository):
        return all(self.memory_current(memory_repository.load_memory(summary.subject_id, mid))
                   for mid in summary.source_memory_ids)

    def outcome(self, request_id):
        """Minimal read-only status: only IDs, hashes and current reason codes."""
        for request, result, record in self.external.absorbed():
            if request.capability_request_id == request_id:
                return {'request_id': request_id, 'result_hash': record.result_hash,
                        'decisions': [d.to_dict() for d in record.decisions]}
        return None

    def adopt_corroborated(self, source_id, content_hash, *, reason):
        """Explicit P04 consolidation of a labeled external report, never a state write.

        A policy must be injected by the isolated host. Absence is NOT_READY.
        Original candidate and current independent root proofs are checked again.
        """
        if self.policy is None:
            raise ExternalCapabilityError('EXTERNAL_LONG_TERM_POLICY_NOT_READY')
        if not isinstance(reason, str) or not reason.strip():
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_REASON_REQUIRED')
        rows = []
        for request, result, record in self.external.absorbed():
            for candidate, decision in zip(result.candidates, record.decisions):
                if (candidate.source_id == source_id and candidate.content_hash == content_hash
                        and decision.disposition == 'CANDIDATE'
                        and candidate.confidence >= self.policy.minimum_confidence):
                    rows.append((request, candidate))
        roots = {}
        for request, candidate in rows:
            for root in candidate.roots:
                proof = self._proof(root)
                if not self.current_root(root, proof.binding_hash):
                    raise ExternalCapabilityError('EXTERNAL_ROOT_NOT_CURRENT')
                roots[root] = proof
        if len(roots) < self.policy.minimum_independent_roots:
            raise ExternalCapabilityError('EXTERNAL_INDEPENDENT_EVIDENCE_INSUFFICIENT')
        if any(d.disposition == 'CONFLICT' and c.source_id == source_id
               for _, result, record in self.external.absorbed()
               for c, d in zip(result.candidates, record.decisions)):
            raise ExternalCapabilityError('EXTERNAL_EVIDENCE_CONFLICT')
        candidate = rows[0][1]
        now = self.external.core.clock()
        occurred = min(parse_capability_datetime(c.observed_at) for _, c in rows)
        message_roots = sorted(roots)
        memory = MemoryRecord(
            memory_id='w02c-memory:' + digest([source_id, content_hash, message_roots])[7:],
            subject_id=self.external.core.subject_id, environment=self.external.core.environment,
            kind=MemoryKind.SEMANTIC, evidence_type=MemoryEvidenceType.EXTERNAL,
            content=_EXTERNAL_MEMORY_PREFIX + candidate.content,
            root_evidence_ids=['message:' + r for r in message_roots],
            source_message_ids=message_roots, occurred_at=occurred, observed_at=now,
            recorded_at=now, consolidated_at=now, confidence=min(c.confidence for _, c in rows),
            importance=0.5, activation=0.0, scope='w02c.external:' + digest(source_id)[7:],
            time_range=MemoryTimeRange(occurred, occurred),
            consolidation_id='w02c-consolidation:' + digest([source_id, content_hash, message_roots])[7:],
            tags=['external', *('w02c-proof:' + digest([r, p.binding_hash])[7:] for r, p in roots.items())],
        )
        # P04 owns the durable record and duplicate/lineage rules. A failure
        # leaves the original P16 fact and candidate available for inspection.
        return self.external.core.consolidation.consolidate(memory)


class ExternalAwareMemorySource(MemoryContextSource):
    def __init__(self, repository, *, environment, absorption):
        super().__init__(repository, environment=environment)
        self.absorption = absorption

    def _query(self, query):
        # Fetch a bounded larger window before invalid-root filtering so stale
        # top hits do not hide every usable lower-ranked memory.
        expanded=replace(query,limit=min(256,max(query.limit*4,query.limit+16)))
        return [m for m in super()._query(expanded) if self.absorption.memory_current(m)][:query.limit]


class ExternalAwareSummarySource(DerivedSummaryContextSource):
    def __init__(self, repository, *, environment, absorption):
        super().__init__(repository, environment=environment)
        self.absorption = absorption

    def _query(self, query):
        expanded=replace(query,limit=min(256,max(query.limit*4,query.limit+16)))
        return [s for s in super()._query(expanded)
                if self.absorption.summary_current(s, self._repository)][:query.limit]


class ExternalAwareMaterialResolver:
    def __init__(self, delegate, repository, absorption, *, summary=False):
        self.delegate, self.repository, self.absorption, self.summary = delegate, repository, absorption, summary
        self.source_id, self.partition = delegate.source_id, delegate.partition

    def resolve(self, ref):
        payload = self.delegate.resolve(ref)
        if self.summary:
            item = self.repository.load_summary(ref.subject_id, ref.stable_id)
            valid = self.absorption.summary_current(item, self.repository)
        else:
            item = self.repository.load_memory(ref.subject_id, ref.stable_id)
            valid = self.absorption.memory_current(item)
        if not valid:
            raise ContextCompositionSourceError('EXTERNAL_DERIVED_ROOT_NO_LONGER_CURRENT')
        return payload


def external_aware_learning_repository(base_class, data_dir, absorption):
    """Keep P15's original repository and current-support check, adding root read."""
    class Repository(base_class):
        def memory_support_snapshot(self, subject_id, memory_id, environment=None):
            snapshot = super().memory_support_snapshot(subject_id, memory_id, environment)
            if snapshot is not None:
                from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
                memory = JsonMemoryRepository(data_dir, environment=snapshot['environment']).load_memory(subject_id, memory_id)
                if not absorption.memory_current(memory):
                    raise LearningValidationError('EXTERNAL_MEMORY_SUPPORT_WITHDRAWN')
            return snapshot
    return Repository(data_dir)
