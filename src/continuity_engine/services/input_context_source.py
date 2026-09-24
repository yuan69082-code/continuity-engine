"""Current-message candidate using P05/P06 ports, never a memory authority."""
from __future__ import annotations

import json
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_routing import (
    ContextPartition, ContextSourceBatch, ContextSourceCandidate, ContextRoutingRequest,
    ContextCandidateReference,
)
from continuity_engine.domain.errors import CapabilityValidationError, ContextCompositionSourceError
from continuity_engine.domain.memory import MemoryVisibility
from .context_material_resolvers import ExactContextPayload
from .context_router_service import ContextSourceValidation


class InputContextSource:
    source_id = 'engine.current-input'
    partition = ContextPartition.LOCAL_FACT

    def __init__(self, ledger, permission, clock, subject_id, environment):
        self.ledger, self.permission, self.clock = ledger, permission, clock
        self.subject_id, self.environment = subject_id, environment
        self._preparing = {}

    def bind(self, perception, operation, record):
        record.validate_binding(operation, perception)
        self._preparing[operation.request_id] = perception

    def release(self, request_id):
        self._preparing.pop(request_id, None)

    def _material(self, request_id):
        operation = self.ledger.load_operation(request_id)
        if (operation is None or not operation.input_processing_enabled or operation.domain_progress is None
                or operation.domain_progress.input_processing is None):
            raise ContextCompositionSourceError('INPUT_SOURCE_MISSING')
        record = operation.domain_progress.input_processing
        perception = (operation.domain_progress.perception or operation.domain_progress.input_preparation
                      or self._preparing.get(request_id))
        if perception is None:
            raise ContextCompositionSourceError('INPUT_PERCEPTION_MISSING')
        record.validate_binding(operation, perception)
        if (record.manifest['subject_id'], record.manifest['environment']) != (self.subject_id, self.environment):
            raise ContextCompositionSourceError('INPUT_SOURCE_BOUNDARY')
        fact = perception.external_facts[0]
        content = json.dumps({'content': fact.content, 'reading': record.manifest['interpretation'],
                              'received_not_remembered': True}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return perception, record, fact, content

    def _candidate(self, request_id):
        perception, record, fact, content = self._material(request_id)
        return ContextSourceCandidate(self.source_id, self.partition, 'input:' + request_id,
            self.subject_id, self.environment, fact.message_version_id, digest(content), fact.occurred_at,
            MemoryVisibility.ENGINE_PRIVATE.value, 'RETRIEVED_CANDIDATE', 1.0, importance=1.0,
            tags=('current_message',), scopes=('input.current',))

    def authorize(self, request_id):
        perception, record, fact, _ = self._material(request_id)
        candidate = self._candidate(request_id)
        request = ContextRoutingRequest(request_id, perception.perception_id, self.subject_id,
            self.environment, perception.source_revision, self.clock(), ('fact',))
        ref = ContextCandidateReference(self.source_id, self.partition, candidate.stable_id,
            self.subject_id, self.environment, candidate.version, candidate.content_hash,
            candidate.authority_label, 1, 1.0, candidate.occurred_at, ('CURRENT_INPUT',))
        try:
            allowed = (self.permission.authorize_source(request, self.source_id, self.partition).allowed
                       and self.permission.authorize_candidate(request, candidate).allowed
                       and self.permission.authorize_reference(request, ref).allowed)
        except Exception:
            raise CapabilityValidationError('INPUT_PERMISSION_PORT_FAILED') from None
        if not allowed:
            raise CapabilityValidationError('INPUT_CURRENT_PERMISSION_DENIED')

    def retrieve(self, query):
        if (query.subject_id, query.environment) != (self.subject_id, self.environment):
            raise ContextCompositionSourceError('INPUT_QUERY_BOUNDARY')
        self.authorize(query.request_id)
        candidate = self._candidate(query.request_id)
        return ContextSourceBatch(self.source_id, self.partition, candidate.content_hash,
                                  (candidate,) if query.limit else ())

    def revalidate(self, query, candidate, source_version):
        batch = self.retrieve(query)
        valid = candidate in batch.candidates and batch.source_version == source_version
        return ContextSourceValidation(valid, 'INPUT_CURRENT' if valid else 'INPUT_STALE',
                                       batch.source_version, candidate.version, candidate.content_hash)

    def resolve(self, reference):
        if (reference.source_id != self.source_id or reference.partition != self.partition
                or not reference.stable_id.startswith('input:')
                or (reference.subject_id, reference.environment) != (self.subject_id, self.environment)):
            raise ContextCompositionSourceError('INPUT_REFERENCE_BOUNDARY')
        request_id = reference.stable_id[len('input:'):]
        self.authorize(request_id)
        candidate = self._candidate(request_id)
        if (reference.version, reference.content_hash) != (candidate.version, candidate.content_hash):
            raise ContextCompositionSourceError('INPUT_REFERENCE_STALE')
        _, record, fact, content = self._material(request_id)
        return ExactContextPayload(self.source_id, self.partition, reference.stable_id,
            self.subject_id, self.environment, candidate.version, candidate.content_hash,
            fact.occurred_at, content, 0.5, ('message:' + fact.message_id + ':' + fact.message_version_id,),
            conflict_markers=('INPUT_NOT_VERIFIED_FACT',))
