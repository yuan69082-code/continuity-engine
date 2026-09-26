"""Pre-answer association over the existing P05/P06 sources.

The local interpreter is deliberately bounded: it reports utterance semantics,
not verified world facts. Unknown grammar retains uncertainty. No provider calls.
"""
from dataclasses import replace
import json
import re
import time

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.associative_recall import RecallPolicy, seal_record, validate_record
from continuity_engine.domain.context_routing import (
    CandidateManifest, ContextRouteResult, ContextRouteStatus, ContextTrace,
    RetrievalBudget, RoutingSignal,
)
from continuity_engine.domain.errors import CapabilityValidationError
from .input_processing_service import interpret


def assess(content, occurred_at):
    """Clause/predicate scope precedes retrieval expansion; aliases are not facts.

    Meal grammar is a supported local domain, not a general Chinese NLU claim.
    Generic topic queries remain uncertain and cannot supply preference evidence.
    """
    reading=interpret(content)
    text=content.strip()
    quoted=any(c in text for c in '“”「」"') or reading['nature']=='QUOTED'
    actor=reading['about']
    # Bind event modality to the clause, never to a hit on one Chinese character.
    clauses=re.split(r'[。！？!?；;，,]',text)
    frames=[]
    for clause in filter(None,clauses):
        local=interpret(clause)
        match=re.search(r'(想|打算|准备)?(再|又|正在|在)?(吃过|吃了|吃|进食|用餐|嗦|享用)(.*)',clause)
        preference=re.search(r'(不爱|不喜欢|喜欢|爱)(?:吃)?(.+)',clause)
        if not match and not preference:
            continue
        compound_scope=bool(re.search(r'不是不|不得不|不能不|并非不|不无',clause))
        negated=(None if compound_scope else True if preference and preference.group(1) in {'不爱','不喜欢'} else local['negated'])
        desire=bool(match and match.group(1)) or local['nature']=='DESIRE'
        not_done=bool(re.search(r'(?:没|没有|未)(?:有)?吃',clause))
        target=(preference.group(2) if preference else match.group(4)).strip('了呢呀啊 ')
        target=re.split(r'但|而且|因为|所以',target)[0]
        target=target.replace('螺丝粉','螺蛳粉').replace('午餐','午饭').replace('米饭','饭')
        historical=bool(re.search(r'去年|以前|过去|曾经',clause))
        frames.append(dict(actor=local['about'],object=target or '进食',event='meal' if match else 'preference',
            modality=('QUOTED' if quoted else 'UNCERTAIN' if negated is None or local['nature'] in {'HYPOTHETICAL','QUESTION'} else
                'NOT_CONSUMED_REPORT' if not_done else 'NEGATED_INTENT' if desire and negated else 'INTENDED' if desire else
                'NEGATIVE_PREFERENCE_REPORT' if preference and negated else
                'POSITIVE_PREFERENCE_REPORT' if preference else
                'NEGATED_REPORT' if negated else 'CONSUMPTION_REPORT'),
            time=('HISTORICAL_UNRESOLVED' if historical else 'SOURCE_TIME'),
            source_time=occurred_at.isoformat(),verified_fact=False))
    greeting=bool(re.fullmatch(r'(你好|您好|谢谢|好的|嗯|早上好|晚安)[。！! ]*',text))
    terms=[]
    for f in frames:
        if f['object']!='进食': terms.append(f['object'])
    if any(f['event']=='meal' for f in frames):
        # A concrete same-event link justifies looking at meals, even when the
        # object differs. This does not infer hunger or a stable preference.
        terms.extend(('吃','饭','进食','用餐','午餐','螺丝粉' if '螺蛳粉' in terms else 'meal'))
    elif not frames and not greeting:
        terms.extend(re.findall(r'[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}',text))
    if '螺蛳粉' in terms and '螺丝粉' not in terms:
        terms.append('螺丝粉')
    return dict(version='w02-utterance-assessment-v1',authority='INTERPRETATION_NOT_FACT',
        content_hash=digest(content),actor=actor,frames=frames,
        uncertain=reading['uncertain'] or quoted or not frames or any(f['modality']=='UNCERTAIN' for f in frames),
        query_terms=list(dict.fromkeys(terms)),
        reason='NO_RELEVANT_CUE' if greeting else 'EVENT_AND_OBJECT' if frames else 'UNCERTAIN_TOPIC',
        assumptions=['SOURCE_TIME_IS_NOT_PROOF_OF_EVENT_TIME','HUNGER_NOT_DETERMINED'])


class AssociativeRecallService:
    def __init__(self, core, *, policy=None, timer=None):
        self.core=core
        self.policy=policy or RecallPolicy()
        self.timer=timer or time.monotonic

    def prepare(self, perception, operation, save, *, attention=None):
        from contextlib import ExitStack
        # Parse reuse is local to this preparation and exact current bytes.
        # Permission callbacks and post-callback reads are NOT cached.
        with ExitStack() as stack:
            ledgers={id(b.source.ledger):b.source.ledger for b in self.core.router._bindings
                     if hasattr(getattr(b.source,'ledger',None),'_verified_operation_reads')}
            for ledger in ledgers.values():stack.enter_context(ledger._verified_operation_reads())
            # The external candidate path verifies original E5-A requests and
            # receipts repeatedly while routing and composing. Reuse their
            # validated parse only for identical current bytes in this one
            # preparation; each access still rechecks current permissions,
            # provider facts and source roots.
            external=getattr(self.core,'external_capabilities',None)
            capability_ledger=getattr(getattr(getattr(external,'core',None),'coordination',None),
                                      '_repository',None)
            if capability_ledger is not None and hasattr(capability_ledger,'_verified_capability_reads'):
                stack.enter_context(capability_ledger._verified_capability_reads())
            return self._prepare(perception,operation,save,attention=attention)

    def _prepare(self, perception, operation, save, *, attention=None):
        core=self.core; policy=self.policy; start=self.timer()
        if perception.external_facts:
            fact=perception.external_facts[0]
            assessment=assess(fact.content,fact.occurred_at)
        else:
            assessment=assess(' '.join((*perception.current_focus.topics,perception.current_focus.summary)),perception.perceived_at)
            assessment['actor']='SUBJECT_INTERNAL_CUE'
            for frame in assessment['frames']:frame['actor']='SUBJECT_INTERNAL_CUE'
        history=getattr(getattr(operation,'domain_progress',None),'recall_progress',())
        if history and history[-1]['status']=='READY':
            # A READY record only accompanies the original durable perception.
            raise CapabilityValidationError('RECALL_PREPARATION_REQUIRED')
        rounds=[]; routes=[]; seen=set(); used=0; terms=tuple(assessment['query_terms'])
        stop='NO_RELEVANT_CUE' if not terms else 'NO_NEW_ASSOCIATION'
        composition=None; route=None; preferences=[]; saved_failure=False
        try:
            for depth in range(policy.max_rounds):
                remaining=policy.candidate_limit-used
                if remaining<=0:
                    stop='RETRIEVAL_BUDGET_EXHAUSTED';break
                bindings=core.router._bindings
                round_limit=min(policy.per_round_limit,remaining)
                # Existing P05 total range remains unchanged; per-source caps
                # keep the actual cumulative work within the W02 budget.
                if round_limit<6+len(bindings)-1:
                    stop='RETRIEVAL_BUDGET_EXHAUSTED';break
                caps={b.source.source_id:(6 if b.source.source_id=='engine.subject-state' else 1) for b in bindings}
                left=round_limit-sum(caps.values())
                order=sorted((k for k in caps if k!='engine.subject-state'),
                    key=lambda k:({'engine.memory':0,'engine.input-history':1,'engine.timeline':2,
                                   'engine.derived-summary':3,'engine.current-input':4}.get(k,5),k))
                while left>0 and order:
                    for key in order:
                        if left<=0:break
                        caps[key]+=1;left-=1
                budget=RetrievalBudget(policy.candidate_limit,
                    tuple(caps.items()))
                if (self.timer()-start)*1000>=policy.latency_ms:
                    stop='RECALL_TIMEOUT';break
                current=core.router.route(perception,request_id=operation.request_id,
                    environment=core.environment,budget=budget,
                    recall_terms=terms,attention=attention)
                routes.append(current);used+=current.trace.budget_used
                problems=sorted({s.reason_code for s in current.trace.source_traces
                    if s.status.value in {'UNAVAILABLE','REJECTED'}})
                rounds.append(dict(depth=depth,query_hash=digest(terms),
                    route_hash=current.canonical_hash(),retrieved=current.trace.budget_used,
                    source_outcomes=[s.to_dict() for s in current.trace.source_traces],
                    reasons=problems,candidate_decisions=[d.to_dict() for d in current.trace.candidate_decisions],
                    window_at_limit=[s.source_id for s in current.trace.source_traces
                                     if s.requested_limit and s.candidate_count==s.requested_limit],associations=[]))
                if (self.timer()-start)*1000>=policy.latency_ms:
                    stop='RECALL_TIMEOUT';break
                if problems or current.trace.route_status is not ContextRouteStatus.COMPLETE:
                    stop='RECALL_SOURCE_UNAVAILABLE';break
                route=self._merge(routes, attention=attention)
                self._authorize(route)
                composition=core.composer.compose(route,budget=core.context_budget)
                if (self.timer()-start)*1000>=policy.latency_ms:
                    stop='RECALL_TIMEOUT';break
                if composition.snapshot is None or not composition.snapshot.consumable:
                    stop='RECALL_CONTEXT_UNAVAILABLE';break
                if not terms: break
                historical=[f for f in composition.snapshot.fragments
                    if f.source_id not in {'engine.subject-state','engine.current-input'}]
                roots={r for f in historical for r in f.provenance_roots}
                if len(roots)>=policy.sufficient_roots:
                    stop='SUFFICIENT_MATERIAL';break
                next_terms=[]
                for fragment in historical:
                    key=(fragment.source_id,fragment.stable_source_id,fragment.version,fragment.content_hash)
                    if key in seen:continue
                    seen.add(key)
                    material=fragment.content
                    if fragment.source_id=='engine.input-history':
                        material=json.loads(material)['content']
                    related=assess(material,fragment.occurred_at)
                    for frame in related['frames']:
                        if (frame['event']=='meal' and any(f['event']=='meal' for f in assessment['frames'])
                                and frame['object'] not in terms):
                            next_terms.append(frame['object'])
                            rounds[-1]['associations'].append(dict(source=fragment.stable_source_id,
                                hash=fragment.content_hash,reason='SHARED_EVENT',term_hash=digest(frame['object'])))
                fresh=tuple(dict.fromkeys(t for t in next_terms if t not in terms))
                if not fresh:
                    rejected={d.reason_code for d in current.trace.candidate_decisions if d.status.value=='REJECTED'}
                    stop=('REPEATED_ASSOCIATION' if depth else 'NO_NEW_ASSOCIATION' if historical else
                          'CANDIDATES_NOT_USABLE' if rejected-{'BELOW_RELEVANCE_THRESHOLD'} else
                          'RELEVANCE_INSUFFICIENT' if rejected else 'NO_MATCH')
                    break
                terms=tuple(dict.fromkeys((*terms,*fresh)))
            else: stop='ASSOCIATION_BUDGET_EXHAUSTED'
            blocked=stop in {'RECALL_TIMEOUT','RECALL_SOURCE_UNAVAILABLE','RECALL_CONTEXT_UNAVAILABLE'} or composition is None
            if not blocked:
                preferences=self._preference_candidates(route,operation,perception,assessment) if perception.external_facts else []
                if (self.timer()-start)*1000>=policy.latency_ms:
                    blocked=True;stop='RECALL_TIMEOUT'
            record=seal_record(dict(version='w02-recall-v1',request_id=operation.request_id,
                operation_id=operation.operation_id,subject_id=core.subject_id,environment=core.environment,
                perception_hash=digest(perception.to_dict()),policy=policy.to_dict(),assessment=assessment,
                rounds=rounds,status='BLOCKED' if blocked else 'READY',stop_reason=stop,
                elapsed_ms=round((self.timer()-start)*1000,3),retrieved_count=used,
                model_calls=0,external_calls=0,preference_candidates=preferences,
                snapshot_hash=None if blocked else composition.snapshot.snapshot_hash))
            validate_record(record,operation=operation,perception=perception)
            if blocked:
                save(record)
                saved_failure=True
                raise CapabilityValidationError(stop)
            return route,composition,record
        except Exception as exc:
            if not saved_failure:
                failure=seal_record(dict(version='w02-recall-v1',request_id=operation.request_id,
                    operation_id=operation.operation_id,subject_id=core.subject_id,environment=core.environment,
                    perception_hash=digest(perception.to_dict()),policy=policy.to_dict(),assessment=assessment,
                    rounds=rounds,status='BLOCKED',stop_reason='RECALL_PREPARATION_FAILED',
                    elapsed_ms=round((self.timer()-start)*1000,3),retrieved_count=used,
                    model_calls=0,external_calls=0,snapshot_hash=None,preference_candidates=[]))
                try:save(failure)
                except Exception:exc.add_note('RECALL_FAILURE_RECORD_NOT_SAVED')
            raise

    def _preference_candidates(self,route,operation,perception,assessment):
        """Use P04 derived views for an UNCONFIRMED candidate, never a trait.

        P15's structured Learning annotations are not fabricated from prose.
        A candidate view can support later legitimate learning; it cannot itself
        grant a SubjectState mutation or automatically confirm a preference.
        """
        from .memory_consolidation_service import MemoryConsolidationService
        core=self.core
        objects={f['object'] for f in assessment['frames'] if f['actor']=='SELF_REPORTED'
                 and f['modality'] in {'CONSUMPTION_REPORT','POSITIVE_PREFERENCE_REPORT'} and f['object']!='进食'}
        if not objects:return []
        history=next((b.source for b in core.router._bindings if b.source.source_id=='engine.input-history'),None)
        if history is None:return []
        # Match the reporting speaker through the existing ingress binding,
        # not the word "I" in an arbitrary Event or a derived summary.
        reports={}
        relevant_events=set()
        for ref in route.manifest.candidates:
            if ref.source_id=='engine.memory':
                m=core.memory.load_memory(core.subject_id,ref.stable_id)
                relevant_events.update(m.source_event_ids)
        checked_operations={}
        for prior in history.ledger.list_operations():
            if prior.binding_id!=operation.binding_id or not prior.input_processing_enabled:continue
            p=(prior.domain_progress.perception or prior.domain_progress.input_preparation) if prior.domain_progress else None
            if p is None:continue
            fact=p.external_facts[0]
            if fact.source_event_id not in relevant_events:continue
            material=history._material_from_operation(prior,prior.request_id)
            history._authorize_material(prior.request_id,material)
            checked_operations[prior.request_id]=prior
            reports[fact.source_event_id]=fact
        # This is one bounded candidate pass, not a cross-request cache. Read
        # the authoritative journal again after ALL permission callbacks; only
        # unchanged original records can support the candidate. Permissions
        # remain per-reference and the subsequent source resolvers still run.
        current_operations={p.request_id:p for p in history.ledger.list_operations()}
        if any(current_operations.get(key)!=prior for key,prior in checked_operations.items()):
            raise CapabilityValidationError('RECALL_CANDIDATE_SOURCE_CHANGED')
        entries={e.event.event_id:e for e in core.timeline.rebuild(core.subject_id).entries if e.status.value=='active'}
        evidence=[]
        for ref in route.manifest.candidates:
            if ref.source_id!='engine.memory':continue
            payload=core.composer._bindings[ref.source_id].resolver.resolve(ref)
            if len(payload.provenance_roots)!=1 or not payload.provenance_roots[0].startswith('event:'):continue
            root=payload.provenance_roots[0]; event_id=root[6:]
            fact=reports.get(event_id);entry=entries.get(event_id)
            if fact is None or entry is None or fact.content!=entry.event.content:continue
            reading=assess(fact.content,fact.occurred_at)
            for frame in reading['frames']:
                if frame['actor']=='SELF_REPORTED' and frame['object'] in objects:
                    evidence.append((ref,root,frame))
        results=[]
        for obj in sorted(objects):
            items={root:(ref,frame) for ref,root,frame in evidence if frame['object']==obj}
            supports={r:v for r,v in items.items() if v[1]['modality'] in {'CONSUMPTION_REPORT','POSITIVE_PREFERENCE_REPORT'}}
            counter={r:v for r,v in items.items() if v[1]['modality']=='NEGATIVE_PREFERENCE_REPORT'}
            positive=any(v[1]['modality']=='POSITIVE_PREFERENCE_REPORT' for v in supports.values())
            enough=len(supports)>=self.policy.preference_minimum_roots
            eligible=enough and (positive or not self.policy.preference_require_positive_report) and not counter
            result=dict(object=obj,actor_binding=operation.binding_id,independent_roots=sorted(supports),
                counter_roots=sorted(counter),status='UNCONFIRMED_CANDIDATE' if eligible else 'INSUFFICIENT_OR_CONTRADICTORY',
                confirmed=False,rule=self.policy.to_dict(),authority='DERIVED_CANDIDATE_NOT_FACT')
            if eligible:
                self._authorize(route)
                if core.subject_states.load(core.subject_id).revision!=operation.input_revision:
                    raise CapabilityValidationError('RECALL_CANDIDATE_REVISION_CHANGED')
                core.subject_states.require_active(core.subject_id,core.environment)
                text=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))
                class CandidateView:
                    def generate(self,memories):return text
                consolidation=MemoryConsolidationService(core.memory,clock=core.clock,summary_generator=CandidateView())
                identity='w02-preference:'+digest([core.subject_id,operation.binding_id,obj,self.policy.to_dict()])[7:]
                summary=consolidation.generate_summary(core.subject_id,summary_id=identity,
                    summary_type='w02.unconfirmed-preference',scope='reported-preference',
                    source_memory_ids=sorted({v[0].stable_id for v in supports.values()}),confidence=0.0)
                result['summary_id']=summary.summary_id
                result['summary_hash']=summary.canonical_hash()
            results.append(result)
        return results

    def _authorize(self, route):
        for ref in route.manifest.candidates:
            if not self.core.permission.authorize_reference(route.plan.request,ref).allowed:
                raise CapabilityValidationError('RECALL_REFERENCE_DENIED')

    @staticmethod
    def _merge(routes, *, attention=None):
        first=routes[0]; refs={}
        for route in routes:
            for ref in route.manifest.candidates:
                key=(ref.source_id,ref.stable_id)
                if key in refs and (refs[key].version,refs[key].content_hash)!=(ref.version,ref.content_hash):
                    raise CapabilityValidationError('RECALL_SOURCE_CHANGED_DURING_ASSOCIATION')
                refs.setdefault(key,ref)
        signals=tuple(RoutingSignal('recall-pass:'+str(i),'automatic_recall',r.canonical_hash(),1.0)
                      for i,r in enumerate(routes))
        plan=replace(first.plan,signals=(*first.plan.signals,*signals))
        def response_priority(ref):
            # Composer still protects the authoritative identity/relationship/
            # continuity core. Rank current communication and relevant evidence
            # ahead of incidental state sections; P14 mind input stays required.
            if ref.source_id=='engine.current-input':return 0
            if attention is not None and ref.source_id=='engine.subject-state' and ref.stable_id.endswith(':intentions'):return 0
            if ref.source_id in {'engine.input-history','engine.memory'}:return 1
            if ref.source_id=='engine.timeline':return 2
            return 3
        manifest=CandidateManifest(plan.request.request_id,plan.canonical_hash(),tuple(
            replace(ref,rank=i,explanation_codes=(*ref.explanation_codes,'PRE_RESPONSE_RELEVANCE_ORDER')) for i,ref in enumerate(sorted(refs.values(),
                key=lambda x:(response_priority(x),-x.score,x.source_id,x.stable_id)),1)))
        trace=replace(first.trace,route_plan_hash=plan.canonical_hash(),manifest_hash=manifest.manifest_hash,
            source_traces=tuple(s for r in routes for s in r.trace.source_traces),
            partition_traces=tuple(s for r in routes for s in r.trace.partition_traces),
            candidate_decisions=tuple(s for r in routes for s in r.trace.candidate_decisions),
            budget_used=sum(r.trace.budget_used for r in routes))
        return ContextRouteResult(plan,manifest,trace)
