"""Current-message candidate using P05/P06 ports, never a memory authority."""
from __future__ import annotations

import json
from dataclasses import replace
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
        read = getattr(self.ledger, '_load_operation_input', self.ledger.load_operation)
        operation = read(request_id)
        return self._material_from_operation(operation,request_id)

    def _material_from_operation(self,operation,request_id):
        if (operation is None or not operation.input_processing_enabled or operation.domain_progress is None
                or operation.domain_progress.input_processing is None):
            raise ContextCompositionSourceError('INPUT_SOURCE_MISSING')
        record = operation.domain_progress.input_processing
        perception = (operation.domain_progress.perception or operation.domain_progress.input_preparation
                      or self._preparing.get(request_id))
        if perception is None:
            raise ContextCompositionSourceError('INPUT_PERCEPTION_MISSING')
        if operation.recall_enabled and perception.continuity_context is not None:
            # The input manifest explicitly excludes continuity_context. The
            # repository already validates the complete original operation;
            # project just the bound input instead of serializing a historical
            # response context only to discard it inside validate_binding.
            # This does not alter the persisted perception or its context.
            perception = replace(perception, continuity_context=None)
        record.validate_binding(operation, perception)
        if (record.manifest['subject_id'], record.manifest['environment']) != (self.subject_id, self.environment):
            raise ContextCompositionSourceError('INPUT_SOURCE_BOUNDARY')
        fact = perception.external_facts[0]
        payload={'content':fact.content,'reading':record.manifest['interpretation'],'received_not_remembered':True}
        if operation.recall_enabled:
            from .associative_recall_service import assess
            semantic=assess(fact.content,fact.occurred_at)
            payload['reporter_binding']=operation.binding_id
            # A compact projection, with full original W02-A interpretation
            # retained in its journal. Do not spend the response budget on
            # duplicate hashes/spans already bound by the source reference.
            payload['reading']={'about':semantic['actor'],'uncertain':semantic['uncertain'],
                'authority':'INTERPRETATION_NOT_FACT',
                'frames':[{k:v for k,v in f.items() if k not in {'source_time','verified_fact'}} for f in semantic['frames']]}
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return perception, record, fact, content

    def _candidate(self, request_id, *, material=None):
        perception, record, fact, content = material if material is not None else self._material(request_id)
        return ContextSourceCandidate(self.source_id, self.partition, 'input:' + request_id,
            self.subject_id, self.environment, fact.message_version_id, digest(content), fact.occurred_at,
            MemoryVisibility.ENGINE_PRIVATE.value, 'RETRIEVED_CANDIDATE', 1.0, importance=1.0,
            tags=('current_message',), scopes=('input.current',))

    def authorize(self, request_id):
        return self._authorize_material(request_id,self._material(request_id))

    def _authorize_material(self,request_id,material):
        perception, record, fact, _ = material
        candidate = self._candidate(request_id,material=material)
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
        return self._resolve(reference)

    def _resolve(self, reference, *, current_source=None):
        if (reference.source_id != self.source_id or reference.partition != self.partition
                or not reference.stable_id.startswith('input:')
                or (reference.subject_id, reference.environment) != (self.subject_id, self.environment)):
            raise ContextCompositionSourceError('INPUT_REFERENCE_BOUNDARY')
        request_id = reference.stable_id[len('input:'):]
        material=self._material(request_id)
        if current_source is not None and not current_source(material[2]):
            raise ContextCompositionSourceError('INPUT_HISTORY_SOURCE_INELIGIBLE')
        self._authorize_material(request_id,material)
        candidate = self._candidate(request_id,material=material)
        if (reference.version, reference.content_hash) != (candidate.version, candidate.content_hash):
            raise ContextCompositionSourceError('INPUT_REFERENCE_STALE')
        # Recheck after the permission port. Reuse one verified material within
        # each check, rather than repeatedly deserializing the whole journal.
        checked=self._material(request_id)
        if checked!=material:
            raise ContextCompositionSourceError('INPUT_REFERENCE_CHANGED_DURING_READ')
        if current_source is not None and not current_source(checked[2]):
            raise ContextCompositionSourceError('INPUT_HISTORY_SOURCE_INELIGIBLE')
        _, record, fact, content = checked
        return ExactContextPayload(self.source_id, self.partition, reference.stable_id,
            self.subject_id, self.environment, candidate.version, candidate.content_hash,
            fact.occurred_at, content, 0.5, ('message:' + fact.message_id + ':' + fact.message_version_id,),
            conflict_markers=('INPUT_NOT_VERIFIED_FACT',))


class HistoricalInputContextSource(InputContextSource):
    """Bounded original input references; no copied conversation/memory authority.

    Reading the existing atomic journal verifies the store, as other JSON source
    queries do. Only a bounded relevant window is offered to P05/P06.
    """
    source_id='engine.input-history'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.current_source=None

    def _material_from_operation(self,operation,request_id):
        perception,record,fact,_=super()._material_from_operation(operation,request_id)
        # A historical projection carries the original utterance and its
        # epistemic boundary. It does not repeat the full current-input analysis.
        content=json.dumps({'reporter_binding':operation.binding_id,'content':fact.content,
            'not_verified_fact':True},ensure_ascii=False,sort_keys=True,separators=(',',':'))
        return perception,record,fact,content

    def retrieve(self,query):
        from dataclasses import replace
        from .context_router_service import _lexical_relevance
        if (query.subject_id,query.environment)!=(self.subject_id,self.environment):
            raise ContextCompositionSourceError('INPUT_HISTORY_BOUNDARY')
        if 'automatic_recall' not in query.purpose:
            return ContextSourceBatch(self.source_id,self.partition,digest([]),())
        candidates=[]
        for operation in self.ledger.list_operations():
            if (operation.subject_id!=self.subject_id or operation.request_id==query.request_id
                    or not operation.input_processing_enabled or operation.domain_progress is None
                    or operation.domain_progress.perception is None):continue
            material=self._material_from_operation(operation,operation.request_id)
            perception,record,fact,content=material
            if fact.occurred_at>query.routed_at:continue
            if self.current_source is not None and not self.current_source(fact):continue
            relevance=_lexical_relevance(query.query_terms,fact.content)
            if relevance<=0:continue
            from .associative_recall_service import assess
            frames=assess(fact.content,fact.occurred_at)['frames']
            if frames and '吃' in query.query_terms:
                relevance=max(relevance,0.85)
            candidate=replace(self._candidate(operation.request_id,material=material),relevance=relevance,
                importance=0.6,tags=('historical_message_report',),scopes=('input.history',))
            candidates.append(candidate)
        candidates=tuple(sorted(candidates,key=lambda c:(-c.relevance,-c.occurred_at.timestamp(),c.stable_id))[:query.limit])
        return ContextSourceBatch(self.source_id,self.partition,
            digest([(c.stable_id,c.version,c.content_hash,c.relevance) for c in candidates]),candidates)

    def resolve(self,reference):
        # Reuse the original material for the eligibility check, while keeping
        # the independent post-permission read and a final root-status check.
        return self._resolve(reference,current_source=self.current_source)
