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

    def __init__(self, service, *, entry_selective=False):
        self.service=service
        self.entry_selective=entry_selective

    def items(self, subject, environment, request_id=None):
        if (subject,environment)!=(self.service.core.subject_id,self.service.core.environment):
            raise ContextCompositionSourceError('EXECUTION_CONTEXT_BOUNDARY')
        items={}
        for request,route,fact,payload in self.service.results_for_context(request_id=request_id):
            content=json.dumps({'observation':payload,'receipt_hash':fact.canonical_hash(),
                                'authority':'RESULT_OBSERVATION','simulation':True},ensure_ascii=False,sort_keys=True)
            items['execution:'+request.capability_request_id]=(route,fact,content)
        return items

    def _entry_version(self):
        # Original reliable-delivery index, not a cached permission/result.
        # A new/changed receipt or route invalidates the whole routed set.
        return digest([self.service.outbox.load(),
            sorted((name, route.hash) for name, route in self.service.routes.items())])

    def _entry_candidates(self, query):
        """Plan bounded reads, not facts or grants, from original authorities.

        Entire E5-A still validates before projecting. An index entry is not
        eligible material until items() rechecks the native fact, permissions
        and source. Ineligible candidates do not consume the returned limit.
        """
        requests=self.service.core.coordination._repository._load_capability_document(
            _projection=lambda requests,attempts:{r.capability_request_id:r for r in requests})
        rows=[]
        for ordinal,entry in enumerate(self.service.outbox.load()['entries']):
            if entry['state']!='DELIVERED':continue
            request=requests.get(entry['request_id'])
            if request is None:
                raise ContextCompositionSourceError('EXECUTION_INDEX_REQUEST_MISSING')
            route=self.service.route_for(request)
            if route.world!=self.service.core.environment:continue
            target=query.request_id==history_context_request_id(request.capability_request_id)
            rows.append((not target,not route.capability_ref.startswith('device.query'),-ordinal,request.capability_request_id))
        return [row[-1] for row in sorted(rows)]

    def _retrieve(self, query, request_id=None):
        version = self._entry_version() if self.entry_selective else None
        if self.entry_selective and request_id is None:
            items={}
            for candidate_id in self._entry_candidates(query):
                if len(items)>=query.limit:break
                items.update(self.items(query.subject_id,query.environment,candidate_id))
        else:
            items=self.items(query.subject_id,query.environment,request_id)
        if self.entry_selective and self._entry_version() != version:
            raise ContextCompositionSourceError('EXECUTION_SOURCE_CHANGED')
        version=version or digest([(key,digest(value[2])) for key,value in sorted(items.items())])
        target=(next((key for key in items if query.request_id==history_context_request_id(key[len('execution:'):])),None)
                if query.request_id.startswith('device-history:') else None)
        # Use the existing candidate relevance/activation contract, before the
        # source limit as well as Router ranking. Keep all other candidates and
        # their conflict/provenance material eligible under the original budget.
        def selection(item):
            key,(route,fact,content)=item
            # In the opt-in entry continuation, an acquired query observation
            # supplies response material; a click/send receipt only establishes
            # an effect. Do not let arbitrary receipt IDs exclude all queried
            # material before Router can evaluate it. Explicit targets win.
            information=self.entry_selective and route.capability_ref.startswith('device.query')
            return (key!=target,not information,
                -parse_capability_datetime(fact.completed_at).timestamp() if self.entry_selective else 0,key)
        ordered=sorted(items.items(),key=selection)
        return ContextSourceBatch(self.source_id,self.partition,version,tuple(ContextSourceCandidate(
            self.source_id,self.partition,key,query.subject_id,query.environment,route.hash,digest(content),
            parse_capability_datetime(fact.completed_at),MemoryVisibility.ENGINE_PRIVATE.value,'RETRIEVED_CANDIDATE',
            1.0 if key==target or self.entry_selective and route.capability_ref.startswith('device.query') else 0.95,
            importance=1.0 if key==target or self.entry_selective and route.capability_ref.startswith('device.query') else 0.8,
            activation=1.0 if key==target or self.entry_selective and route.capability_ref.startswith('device.query') else 0.0,
            tags=('execution','simulation'),scopes=('execution.consume',))
            for key,(route,fact,content) in ordered[:query.limit]))

    def retrieve(self, query):
        return self._retrieve(query)

    def revalidate(self, query, candidate, source_version):
        # Each candidate still goes through current permissions, two source
        # gates, native result/hash and E5-A facts. Unselected results are not
        # recursively consumed again; their immutable index remains bound.
        batch=self._retrieve(query, candidate.stable_id[len('execution:'):] if
            self.entry_selective and candidate.stable_id.startswith('execution:') else None)
        current=next((c for c in batch.candidates if c.stable_id==candidate.stable_id),None)
        return ContextSourceValidation(current==candidate and source_version==batch.source_version,
                'EXECUTION_REVALIDATED',batch.source_version,current.version if current else 'missing',
                current.content_hash if current else candidate.content_hash)

    def resolve(self, ref):
        if ref.source_id!=self.source_id or ref.partition!=self.partition:
            raise ContextCompositionSourceError('EXECUTION_REFERENCE_BINDING')
        item=self.items(ref.subject_id,ref.environment, ref.stable_id[len('execution:'):] if self.entry_selective and ref.stable_id.startswith('execution:') else None).get(ref.stable_id)
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
