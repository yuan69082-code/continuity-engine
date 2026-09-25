"""P16 exact candidate projection into the original P05/P06 boundaries."""
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.context_routing import ContextPartition,ContextSourceBatch,ContextSourceCandidate
from continuity_engine.domain.errors import ContextCompositionSourceError,ContextRoutingSourceError
from continuity_engine.domain.memory import MemoryVisibility
from .context_router_service import ContextSourceValidation, _lexical_relevance
from .context_material_resolvers import ExactContextPayload


class ExternalContextSource:
    source_id='engine.external-candidates'
    partition=ContextPartition.MEMORY
    def __init__(self,service):self.service=service
    def _items(self,subject,environment):
        if (subject,environment)!=(self.service.registry.subject_id,self.service.registry.environment):
            raise ContextCompositionSourceError('EXTERNAL_CONTEXT_BOUNDARY')
        result=[];status_counts={}
        absorbed=self.service.absorption is not None
        rows=self.service.absorbed() if absorbed else tuple((r,v,None) for r,v in self.service.cached())
        for request,value,record in rows:
            for index,candidate in enumerate(value.candidates):
                decision=record.decisions[index] if record is not None else None
                status=decision.disposition if decision is not None else 'LEGACY_CANDIDATE'
                status_counts[status]=status_counts.get(status,0)+1
                if absorbed and status not in ('CANDIDATE','CONFLICT'):
                    continue
                # Roots retain provider identity across wrappers and connector replacements.
                descriptor=self.service.descriptor_for(request)
                stable='external-candidate:'+digest([value.connector_id,value.descriptor_hash,candidate.source_id,candidate.source_version,candidate.content_hash])[7:]
                material={'kind':request.step.input_payload['kind'],'candidate':candidate.to_dict(),
                    'connector':value.connector_id,'connector_version':descriptor.version,'descriptor_hash':value.descriptor_hash,
                    'capability_ref':descriptor.capability_ref,'permission':descriptor.permission}
                if absorbed:
                    material.update(disposition=status,request_id=request.capability_request_id,
                                    root_proof_hashes=list(decision.proof_hashes))
                content=__import__('json').dumps(material,ensure_ascii=False,sort_keys=True,separators=(',',':'))
                result.append((stable,candidate,content,status))
        dedup={};seen=set();duplicate_wrappers=0;same_root_variants=set()
        if absorbed:
            variants={}
            for stable,candidate,content,status in result:
                variants.setdefault((candidate.source_id,tuple(sorted(candidate.roots))),[]).append(candidate)
            same_root_variants={key for key,values in variants.items() if len({x.content_hash for x in values})>1}
            canonical={key:next((x.content_hash for x in values
                                 if all(x.content_hash==self.service.absorption._proof(root).canonical_hash
                                        for root in x.roots)),values[0].content_hash)
                       for key,values in variants.items()}
        for stable,candidate,content,status in sorted(result,key=lambda x:(x[0],x[1].observed_at)):
            # Identical evidence through multiple wrappers is one candidate.
            # Different content or genuine roots remain visible, never a winner.
            key=(candidate.source_id,tuple(sorted(candidate.roots)))
            if absorbed and key in same_root_variants and candidate.content_hash != canonical[key]:
                # The independent root did not multiply. Its canonical
                # rendering wins; alternate wrappers remain in the audit.
                duplicate_wrappers+=1
                continue
            evidence=(tuple(sorted(candidate.roots)),candidate.source_id,candidate.source_version,
                      candidate.content_hash,candidate.confidence,candidate.uncertainty)
            if evidence in seen:
                duplicate_wrappers+=1;continue
            seen.add(evidence);dedup.setdefault(stable,(candidate,content,status))
        audit={'duplicate_wrappers':duplicate_wrappers,'candidate_count':len(dedup),
            'independent_root_count':len({root for c,_,_ in dedup.values() for root in c.roots})}
        if absorbed:audit.update(dispositions=status_counts,same_root_variant_groups=len(same_root_variants))
        self.service.projection_audit=audit
        return dedup
    def retrieve(self,query):
        items=self._items(query.subject_id,query.environment)
        version='p16:'+digest([(k,digest(v[1])) for k,v in sorted(items.items())])[7:]
        selected=list(sorted(items.items()))
        if self.service.absorption is not None:
            # W02-B supplies the current response's bounded, normalized query
            # terms. An obtained external candidate alone is not a reason to
            # consume it in this answer. P05 still ranks the resulting set.
            terms=tuple(t.casefold() for t in query.query_terms if t.strip())
            selected=[(key,item) for key,item in selected
                      if _lexical_relevance(terms,item[0].content,item[0].source_id)>0]
            selected.sort(key=lambda row:(-
                _lexical_relevance(terms,row[1][0].content,row[1][0].source_id),row[0]))
        selected=selected[:query.limit]
        return ContextSourceBatch(self.source_id,self.partition,version,tuple(ContextSourceCandidate(
            self.source_id,self.partition,k,query.subject_id,query.environment,c.source_version,digest(content),
            parse_capability_datetime(c.observed_at),MemoryVisibility.ENGINE_PRIVATE.value,'RETRIEVED_CANDIDATE',
            (0.95 if _lexical_relevance(query.query_terms,c.content,c.source_id)>0 else 0.4),
            importance=c.confidence,tags=('external',status) if self.service.absorption is not None else ('external',),
            scopes=('external.query',)) for k,(c,content,status) in selected))
    def revalidate(self,query,candidate,source_version):
        batch=self.retrieve(query);current=next((x for x in batch.candidates if x.stable_id==candidate.stable_id),None)
        valid=current is not None and current==candidate and batch.source_version==source_version
        return ContextSourceValidation(valid,'EXTERNAL_CURRENT' if valid else 'EXTERNAL_STALE',batch.source_version,
            current.version if current else 'missing',current.content_hash if current else candidate.content_hash)
    def resolve(self,ref):
        if ref.source_id!=self.source_id or ref.partition!=self.partition:raise ContextCompositionSourceError('EXTERNAL_REFERENCE_BINDING')
        item=self._items(ref.subject_id,ref.environment).get(ref.stable_id)
        if item is None:raise ContextCompositionSourceError('EXTERNAL_MATERIAL_MISSING')
        c,content,status=item
        if ref.version!=c.source_version or ref.content_hash!=digest(content):raise ContextCompositionSourceError('EXTERNAL_REFERENCE_STALE')
        return ExactContextPayload(self.source_id,self.partition,ref.stable_id,ref.subject_id,ref.environment,c.source_version,
            digest(content),parse_capability_datetime(c.observed_at),content,c.confidence,c.roots,
            conflict_markers=('EXTERNAL_CONFLICT',) if status=='CONFLICT' else
                ('EXTERNAL_UNVERIFIED',) if c.uncertainty!='DISPUTED_EXTERNAL' else ('EXTERNAL_DISPUTED',))
