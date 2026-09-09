"""Verified result observations projected through existing Router/Composer."""
import json
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.context_routing import ContextPartition, ContextSourceBatch, ContextSourceCandidate
from continuity_engine.domain.errors import ContextCompositionSourceError
from continuity_engine.domain.memory import MemoryVisibility
from .context_router_service import ContextSourceValidation
from .context_material_resolvers import ExactContextPayload


class ExecutionContextSource:
    source_id = 'engine.execution-results'
    partition = ContextPartition.MEMORY

    def __init__(self, service):
        self.service=service

    def items(self, subject, environment):
        if (subject,environment)!=(self.service.core.subject_id,self.service.core.environment):
            raise ContextCompositionSourceError('EXECUTION_CONTEXT_BOUNDARY')
        items={}
        for request,route,fact,payload in self.service.results_for_context():
            content=json.dumps({'observation':payload,'receipt_hash':fact.canonical_hash(),
                                'authority':'RESULT_OBSERVATION','simulation':True},ensure_ascii=False,sort_keys=True)
            items['execution:'+request.capability_request_id]=(route,fact,content)
        return items

    def retrieve(self, query):
        items=self.items(query.subject_id,query.environment)
        version=digest([(key,digest(value[2])) for key,value in sorted(items.items())])
        return ContextSourceBatch(self.source_id,self.partition,version,tuple(ContextSourceCandidate(
            self.source_id,self.partition,key,query.subject_id,query.environment,route.hash,digest(content),
            parse_capability_datetime(fact.completed_at),MemoryVisibility.ENGINE_PRIVATE.value,'RETRIEVED_CANDIDATE',
            0.95,importance=0.8,tags=('execution','simulation'),scopes=('execution.consume',))
            for key,(route,fact,content) in sorted(items.items())[:query.limit]))

    def revalidate(self, query, candidate, source_version):
        batch=self.retrieve(query)
        current=next((c for c in batch.candidates if c.stable_id==candidate.stable_id),None)
        return ContextSourceValidation(current==candidate and source_version==batch.source_version,
                'EXECUTION_REVALIDATED',batch.source_version,current.version if current else 'missing',
                current.content_hash if current else candidate.content_hash)

    def resolve(self, ref):
        if ref.source_id!=self.source_id or ref.partition!=self.partition:
            raise ContextCompositionSourceError('EXECUTION_REFERENCE_BINDING')
        item=self.items(ref.subject_id,ref.environment).get(ref.stable_id)
        if item is None:
            raise ContextCompositionSourceError('EXECUTION_MATERIAL_MISSING')
        route,fact,content=item
        if ref.version!=route.hash or ref.content_hash!=digest(content):
            raise ContextCompositionSourceError('EXECUTION_REFERENCE_STALE')
        return ExactContextPayload(self.source_id,self.partition,ref.stable_id,ref.subject_id,ref.environment,
            route.hash,digest(content),parse_capability_datetime(fact.completed_at),content,0.8,
            ('execution:'+fact.capability_request_id,),conflict_markers=('SIMULATED_RESULT_OBSERVATION',))
