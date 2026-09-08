"""P16 exact candidate projection into the original P05/P06 boundaries."""
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.context_routing import ContextPartition,ContextSourceBatch,ContextSourceCandidate
from continuity_engine.domain.errors import ContextCompositionSourceError,ContextRoutingSourceError
from continuity_engine.domain.memory import MemoryVisibility
from .context_router_service import ContextSourceValidation
from .context_material_resolvers import ExactContextPayload


class ExternalContextSource:
    source_id='engine.external-candidates'
    partition=ContextPartition.MEMORY
    def __init__(self,service):self.service=service
    def _items(self,subject,environment):
        if (subject,environment)!=(self.service.registry.subject_id,self.service.registry.environment):
            raise ContextCompositionSourceError('EXTERNAL_CONTEXT_BOUNDARY')
        result=[]
        for request,value in self.service.cached():
            for candidate in value.candidates:
                # Roots retain provider identity across wrappers and connector replacements.
                descriptor=self.service.descriptor_for(request)
                stable='external-candidate:'+digest([value.connector_id,value.descriptor_hash,candidate.source_id,candidate.source_version,candidate.content_hash])[7:]
                content=__import__('json').dumps({'kind':request.step.input_payload['kind'],'candidate':candidate.to_dict(),
                    'connector':value.connector_id,'connector_version':descriptor.version,'descriptor_hash':value.descriptor_hash,
                    'capability_ref':descriptor.capability_ref,'permission':descriptor.permission},ensure_ascii=False,sort_keys=True,separators=(',',':'))
                result.append((stable,candidate,content))
        dedup={};seen=set();duplicate_wrappers=0
        for stable,candidate,content in sorted(result,key=lambda x:(x[0],x[1].observed_at)):
            # Identical evidence through multiple wrappers is one candidate.
            # Different content or genuine roots remain visible, never a winner.
            evidence=(tuple(sorted(candidate.roots)),candidate.source_id,candidate.source_version,
                      candidate.content_hash,candidate.confidence,candidate.uncertainty)
            if evidence in seen:
                duplicate_wrappers+=1;continue
            seen.add(evidence);dedup.setdefault(stable,(candidate,content))
        self.service.projection_audit={'duplicate_wrappers':duplicate_wrappers,'candidate_count':len(dedup),
            'independent_root_count':len({root for c,_ in dedup.values() for root in c.roots})}
        return dedup
    def retrieve(self,query):
        items=self._items(query.subject_id,query.environment)
        version='p16:'+digest([(k,digest(v[1])) for k,v in sorted(items.items())])[7:]
        selected=list(sorted(items.items()))[:query.limit]
        return ContextSourceBatch(self.source_id,self.partition,version,tuple(ContextSourceCandidate(
            self.source_id,self.partition,k,query.subject_id,query.environment,c.source_version,digest(content),
            parse_capability_datetime(c.observed_at),MemoryVisibility.ENGINE_PRIVATE.value,'RETRIEVED_CANDIDATE',
            0.95 if any(t.casefold() in c.content.casefold() for t in query.query_terms) else 0.4,
            importance=c.confidence,tags=('external',),scopes=('external.query',)) for k,(c,content) in selected))
    def revalidate(self,query,candidate,source_version):
        batch=self.retrieve(query);current=next((x for x in batch.candidates if x.stable_id==candidate.stable_id),None)
        valid=current is not None and current==candidate and batch.source_version==source_version
        return ContextSourceValidation(valid,'EXTERNAL_CURRENT' if valid else 'EXTERNAL_STALE',batch.source_version,
            current.version if current else 'missing',current.content_hash if current else candidate.content_hash)
    def resolve(self,ref):
        if ref.source_id!=self.source_id or ref.partition!=self.partition:raise ContextCompositionSourceError('EXTERNAL_REFERENCE_BINDING')
        item=self._items(ref.subject_id,ref.environment).get(ref.stable_id)
        if item is None:raise ContextCompositionSourceError('EXTERNAL_MATERIAL_MISSING')
        c,content=item
        if ref.version!=c.source_version or ref.content_hash!=digest(content):raise ContextCompositionSourceError('EXTERNAL_REFERENCE_STALE')
        return ExactContextPayload(self.source_id,self.partition,ref.stable_id,ref.subject_id,ref.environment,c.source_version,
            digest(content),parse_capability_datetime(c.observed_at),content,c.confidence,c.roots,
            conflict_markers=('EXTERNAL_UNVERIFIED',) if c.uncertainty!='DISPUTED_EXTERNAL' else ('EXTERNAL_DISPUTED',))
