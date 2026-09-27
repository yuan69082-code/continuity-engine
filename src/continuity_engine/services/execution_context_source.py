"""Verified result observations projected through existing Router/Composer."""
import json
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.context_routing import ContextPartition, ContextSourceBatch, ContextSourceCandidate
from continuity_engine.domain.errors import ContextCompositionSourceError
from continuity_engine.domain.memory import MemoryVisibility
from .context_router_service import ContextSourceValidation
from .context_material_resolvers import ExactContextPayload


def history_context_request_id(capability_request_id):
    """Bounded routing identity for one receipt; this is not an authorization."""
    return 'device-history:' + digest(['execution-result', capability_request_id])


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
        target=(next((key for key in items if query.request_id==history_context_request_id(key[len('execution:'):])),None)
                if query.request_id.startswith('device-history:') else None)
        # Use the existing candidate relevance/activation contract, before the
        # source limit as well as Router ranking. Keep all other candidates and
        # their conflict/provenance material eligible under the original budget.
        ordered=sorted(items.items(),key=lambda item:(item[0]!=target,item[0]))
        return ContextSourceBatch(self.source_id,self.partition,version,tuple(ContextSourceCandidate(
            self.source_id,self.partition,key,query.subject_id,query.environment,route.hash,digest(content),
            parse_capability_datetime(fact.completed_at),MemoryVisibility.ENGINE_PRIVATE.value,'RETRIEVED_CANDIDATE',
            1.0 if key==target else 0.95,
            importance=1.0 if key==target else 0.8,activation=1.0 if key==target else 0.0,
            tags=('execution','simulation'),scopes=('execution.consume',))
            for key,(route,fact,content) in ordered[:query.limit]))

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
        roots = ('execution:'+fact.capability_request_id,)
        if route.capability_ref.startswith('device.query'):
            # Device result structure/scope/hash has already been verified by
            # the bound adapter. Re-reading is not a new independent source.
            payload = json.loads(content)['observation']
            result = json.loads(payload['content'])
            roots = tuple(sorted({'external-history:' + row['root_id'] for row in result['records']})) or roots
        return ExactContextPayload(self.source_id,self.partition,ref.stable_id,ref.subject_id,ref.environment,
            route.hash,digest(content),parse_capability_datetime(fact.completed_at),content,0.8,
            roots,conflict_markers=('SIMULATED_RESULT_OBSERVATION',))
