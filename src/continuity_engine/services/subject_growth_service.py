"""Long-term growth on original Learning records and SubjectState Evolution."""
from copy import deepcopy
from dataclasses import replace
import json
from threading import RLock

from continuity_engine.domain.action import ActionIntent, ActionType, ResourceLimits, RiskLevel
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_routing import ContextCandidateReference, ContextRoutingRequest
from continuity_engine.domain.dynamic_mind import timestamp
from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.domain.events import Event, StateMutation, ChangeOperation
from continuity_engine.domain.learning import LearningRecordType, LearningValidationStatus
from continuity_engine.domain.subject_growth import growth_document
from .learning_service import LearningService

_GROWTH_LOCK = RLock()  # Local orchestration, never a distributed or secondary ledger.


class SubjectGrowthService:
    def __init__(self, core, repository, *, authority=None, fault=None):
        self.core, self.repository, self.authority, self.fault = core, repository, authority, fault
        self.learning = LearningService(repository, clock=core.clock, current_source_verifier=self.verify_source)

    def verify_source(self, candidate, binding):
        c=self.core
        if candidate.subject_id!=c.subject_id:
            raise LearningValidationError('GROWTH_SOURCE_SUBJECT_MISMATCH')
        reference=ContextCandidateReference.from_dict(binding['reference'])
        request=ContextRoutingRequest.from_dict(binding['request'])
        request=replace(request, routed_at=c.clock(), source_revision=c.subject_states.load(c.subject_id).revision)
        if ((reference.subject_id,reference.environment)!=(c.subject_id,c.environment)
                or (request.subject_id,request.environment)!=(c.subject_id,c.environment)
                or not c.permission.authorize_source(request,reference.source_id,reference.partition).allowed
                or not c.permission.authorize_reference(request,reference).allowed):
            raise LearningValidationError('GROWTH_SOURCE_PERMISSION_DENIED')
        try:
            payload=c.composer._bindings[reference.source_id].resolver.resolve(reference)
        except Exception as exc:
            raise LearningValidationError('GROWTH_SOURCE_NO_LONGER_CURRENT') from exc
        if payload.content_hash!=reference.content_hash or payload.version!=reference.version:
            raise LearningValidationError('GROWTH_SOURCE_IDENTITY_CHANGED')
        roots=tuple(binding['roots'])
        if tuple(payload.provenance_roots)!=roots:
            raise LearningValidationError('GROWTH_ROOT_BINDING_CHANGED')
        origins=[r for r in self.learning.get_history(c.subject_id,candidate.learning_id)
                 if r.record_type is LearningRecordType.CANDIDATE_CREATED]
        if len(origins)!=1 or set(origins[0].root_evidence_ids)!=set(roots):
            raise LearningValidationError('GROWTH_CANDIDATE_ROOT_FORGERY')
        # A valid wrapper never upgrades its roots or their current availability.
        events={e.event.event_id:e.event for e in c.timeline.rebuild(c.subject_id).entries if e.status.value=='active'}
        active=set(events)
        if any(root.startswith('event:') and root[6:] not in active for root in roots):
            raise LearningValidationError('GROWTH_ROOT_NO_LONGER_ACTIVE')
        event=events.get(binding['event_id'])
        if (event is None or event.canonical_hash()!=binding['event_hash']
                or candidate.source_event_id!=event.event_id
                or candidate.proposed_change.field_path!=event.metadata['learning_field_path']
                or candidate.proposed_change.value!=event.metadata['learning_value']):
            raise LearningValidationError('GROWTH_EXPERIENCE_BINDING_CHANGED')

    def capture(self, context):
        """Extract only structured experience annotations from consumed raw Event material."""
        c=self.core
        if not c.current(context):raise LearningValidationError('GROWTH_CONTEXT_STALE')
        entries={e.event.event_id:e.event for e in c.timeline.rebuild(c.subject_id).entries if e.status.value=='active'}
        existing={e.learning_id:e for e in self.learning.list_learning_events(c.subject_id)}
        refs={r.stable_id:r for r in context.route.manifest.candidates}
        added=[]
        for fragment in context.composition.snapshot.fragments:
            roots=list(fragment.provenance_roots)
            if fragment.source_id not in {'engine.timeline','engine.memory'} or fragment.missing_markers or fragment.conflict_markers:
                continue
            if len(roots)!=1 or not roots[0].startswith('event:'):continue
            event=entries.get(roots[0][6:])
            if event is None:continue
            metadata=event.metadata
            keys={'learning_observation','learning_hypothesis','learning_field_path','learning_value'}
            if not keys<=set(metadata):continue
            identity='p15-learning:'+digest([c.subject_id,roots[0]])[7:]
            if identity in existing:
                added.append(identity); continue
            reference=refs[fragment.stable_source_id]
            binding={'reference':reference.to_dict(),'request':context.route.plan.request.to_dict(),'roots':roots,
                     'event_id':event.event_id,'event_hash':event.canonical_hash()}
            result=self.learning.create_candidate(c.subject_id,learning_id=identity,source_event_id=event.event_id,
                source_memory_id=None,related_state_revision=context.composition.snapshot.source_revision,
                observation=metadata['learning_observation'],hypothesis=metadata['learning_hypothesis'],
                proposed_change=StateMutation(metadata['learning_field_path'],ChangeOperation.APPEND,
                    metadata['learning_value'],'Explicit experience-backed growth candidate'),
                confidence=metadata.get('learning_confidence',0.5),
                original_experience={'p15_source_binding':binding},reason='Consumed annotated experience',
                source='p15-c1-experience',root_evidence_ids=roots)
            added.append(result.learning_event.learning_id)
        return tuple(added)

    def validate(self, learning_id, corroborating):
        self.core.subject_states.require_active(self.core.subject_id,self.core.environment)
        corroborating=tuple(corroborating)
        for identifier in (learning_id,*corroborating):
            history=self.learning.get_history(self.core.subject_id,identifier)
            origins=[r for r in history if r.record_type is LearningRecordType.CANDIDATE_CREATED]
            if len(origins)!=1 or not isinstance(origins[0].original_experience,dict) or 'p15_source_binding' not in origins[0].original_experience:
                raise LearningValidationError('GROWTH_REQUIRES_CURRENT_CAPTURED_EVIDENCE')
        return self.learning.validate_learning(self.core.subject_id,learning_id,corroborating,
            reason='Current independent consistent experience',source='p15-growth')

    def submit(self, command, credential):
        with _GROWTH_LOCK:
            return self._submit(command,credential)

    def _submit(self,command,credential):
        c=self.core
        if (command.subject_id,command.environment)!=(c.subject_id,c.environment) or self.authority is None:
            raise LearningValidationError('GROWTH_MANAGEMENT_NOT_CONFIGURED_OR_UNBOUND')
        principal=self.authority.identify(command,credential)
        operation={'command':command.to_dict(),'principal_id':principal}
        history=self.learning.get_history(c.subject_id)
        for resolved in history:
            resolution=resolved.growth_resolution
            replacement=resolution['replacement_command'] if resolution else None
            if replacement is not None and replacement['command_id']==command.command_id:
                original=next(r for r in history if r.record_id==resolution['prepared_record_id'])
                if replacement!=command.to_dict() or original.growth_operation['principal_id']!=principal:
                    raise LearningValidationError('GROWTH_REPLACEMENT_IDENTITY_CONFLICT')
        records=[r for r in history
                 if r.growth_operation is not None and r.growth_operation['command']['command_id']==command.command_id]
        if len(records)>1 or records and records[0].growth_operation!=operation:
            raise LearningValidationError('GROWTH_COMMAND_IDENTITY_CONFLICT')
        record=records[0] if records else None
        if record is not None:
            event=self._preparation_event(record)
            resolution=self._resolution(record)
            actual=self._actual_fact(record)
            if resolution is not None and resolution.growth_resolution['outcome']=='SUPERSEDED':
                if actual is not None:raise LearningValidationError('GROWTH_SUPERSEDED_FACT_CONFLICT')
                raise LearningValidationError('GROWTH_COMMAND_SUPERSEDED')
            if actual is not None:
                self._finish_record(record,'COMMITTED')
                return actual
            if resolution is not None:
                raise LearningValidationError('GROWTH_COMMITTED_FACT_MISSING')
        state=c.subject_states.require_active(c.subject_id,c.environment)
        if record is not None and self.learning._field_value(state,record.field_path)!=record.before_value:
            raise LearningValidationError('GROWTH_PENDING_BEFORE_VALUE_CHANGED')
        def authorize():
            current=c.subject_states.require_active(c.subject_id,c.environment)
            if current.revision!=command.expected_revision:
                raise LearningValidationError('GROWTH_STATE_REVISION_CHANGED')
            if self.authority.authorize(command,credential,at=c.clock())!=principal:
                raise LearningValidationError('GROWTH_PRINCIPAL_CHANGED')
            lifecycle=current.temporal.subject_lifecycle
            if lifecycle is not None and lifecycle['owner_principal_id']!=principal:
                raise LearningValidationError('GROWTH_OWNER_MISMATCH')
            intent=ActionIntent('growth:'+command.command_id,ActionType.UPDATE_STATE,
                'Explicit growth confirmation',command.reason,c.subject_id,command.operation,1.0,
                RiskLevel.LOW,['subject_state:update'],0,c.clock())
            decision=c.action_gate.assess_local_action(intent,subject_id=c.subject_id,environment=c.environment,
                limits=c.limits or ResourceLimits(),confirmed=True)
            if not decision.approved:raise LearningValidationError('GROWTH_ACTION_GATE_DENIED')
        authorize()
        target=self.learning.get_learning_event(c.subject_id,command.learning_id)
        if command.operation=='SOLIDIFY':
            if target.validation_status is not LearningValidationStatus.VALIDATED:
                raise LearningValidationError('GROWTH_CURRENT_VALIDATION_REQUIRED')
            self.learning._verify_current_support(c.subject_id,target)
        if record is None:
            for prior in history:
                if prior.growth_operation is None or prior.learning_id!=command.learning_id:continue
                self._preparation_event(prior)
                resolution=self._resolution(prior)
                actual=self._actual_fact(prior)
                if resolution is not None:
                    if (resolution.growth_resolution['outcome']=='COMMITTED')!=(actual is not None):
                        raise LearningValidationError('GROWTH_RESOLUTION_FACT_CONFLICT')
                    continue
                if actual is not None:
                    self._finish_record(prior,'COMMITTED')
                    continue
                if (prior.growth_operation['command']['operation']!=command.operation
                        or prior.growth_operation['principal_id']!=principal):
                    raise LearningValidationError('GROWTH_PENDING_OPERATION_CONFLICT')
                authorize()
                self._finish_record(prior,'SUPERSEDED',replacement=command)
                if self.fault:self.fault('after_pending_superseded')
            state=c.subject_states.require_active(c.subject_id,c.environment)
            target=self.learning.get_learning_event(c.subject_id,command.learning_id)
            authorize()
            if command.operation=='SOLIDIFY':
                change=self.learning.solidify_learning(c.subject_id,command.learning_id,state,
                    trait_name=str(target.proposed_change.value),trait_description=target.hypothesis,
                    reason=command.reason,source='p15-growth',confirmed=True,
                    expected_revision=command.expected_revision,growth_operation=operation)
            else:
                change=self.learning.rollback_learning(c.subject_id,command.learning_id,command.trait_id,state,
                    reason=command.reason,source='p15-growth',confirmed=True,
                    expected_revision=command.expected_revision,growth_operation=operation)
            event=change.event
            record=change.record
            if self.fault:self.fault('after_learning_record')
        authorize()
        if command.operation=='SOLIDIFY':
            target=self.learning.get_learning_event(c.subject_id,command.learning_id)
            confidence=min(target.confidence,self.learning._verify_current_support(c.subject_id,target))
            if (target.validation_status is not LearningValidationStatus.VALIDATED
                    or confidence!=event.metadata['learning_confidence']
                    or len(target.root_evidence_ids)!=event.metadata['evidence_count']):
                raise LearningValidationError('GROWTH_PENDING_SUPPORT_CHANGED_RECONFIRM')
        update=c.subject_states.apply_event(c.subject_id,event,expected_revision=command.expected_revision).update
        if self.fault:self.fault('after_evolution')
        self._finish_record(record,'COMMITTED')
        return update

    def _preparation_event(self, record):
        record.__post_init__()
        command=record.growth_operation['command']
        event=Event.from_dict(record.pending_state_event)
        target=self.learning.get_learning_event(record.subject_id,record.learning_id)
        trait=self.learning.get_trait(record.subject_id,record.trait_id)
        expected=(target.proposed_change if command['operation']=='SOLIDIFY' else
                  StateMutation(trait.field_path,ChangeOperation.REMOVE,trait.current_value,command['reason']))
        if (event.mutations!=[expected] or record.field_path!=trait.field_path
                or event.metadata.get('learning_id')!=record.learning_id
                or trait.current_value!=str(target.proposed_change.value)
                or record.reason!=command['reason']):
            raise LearningValidationError('GROWTH_PENDING_MUTATION_BINDING_INVALID')
        return event

    def _actual_fact(self, record):
        event=self._preparation_event(record)
        actual=next((u for u in self.core.subject_states.get_update_history(record.subject_id)
                     if u.event.event_id==event.event_id),None)
        if actual is not None and (actual.event.canonical_dict()!=event.canonical_dict()
                or actual.before_revision!=record.growth_operation['command']['expected_revision']
                or actual.after_revision!=actual.before_revision+1 or len(actual.changes)!=1
                or actual.changes[0].before!=record.before_value or actual.changes[0].after!=record.after_value):
            raise LearningValidationError('GROWTH_EVOLUTION_FACT_CONFLICT')
        return actual

    def _resolution(self, record):
        resolutions=[r for r in self.learning.get_history(record.subject_id,record.learning_id)
                     if r.growth_resolution is not None
                     and r.growth_resolution['prepared_record_id']==record.record_id]
        if len(resolutions)>1:raise LearningValidationError('GROWTH_DUPLICATE_RESOLUTION')
        return resolutions[0] if resolutions else None

    def _finish_record(self, record, outcome, replacement=None):
        """Append a resolution in the existing Learning audit; never mutate SubjectState."""
        actual=self._actual_fact(record)
        if (outcome=='COMMITTED')!=(actual is not None):
            raise LearningValidationError('GROWTH_RESOLUTION_REQUIRES_ORIGINAL_FACT_CHECK')
        existing=self._resolution(record)
        if existing is not None:
            if existing.growth_resolution['outcome']!=outcome:
                raise LearningValidationError('GROWTH_RESOLUTION_CONFLICT')
            return existing
        target=self.learning.get_learning_event(record.subject_id,record.learning_id)
        trait=self.learning.get_trait(record.subject_id,record.trait_id)
        solidify=record.growth_operation['command']['operation']=='SOLIDIFY'
        target.revision+=1
        trait.revision+=1;trait.last_updated_at=self.core.clock()
        if outcome=='COMMITTED':
            trait.active=solidify
            if not solidify:target.validation_status=LearningValidationStatus.REVOKED
            kind=LearningRecordType.CONSOLIDATED if solidify else LearningRecordType.ROLLED_BACK
            reason=record.reason
        else:
            trait.active=not solidify
            # Old P15 preparations prematurely revoked the candidate; undo only
            # that still-current pending projection, never a later rejection.
            history=[r for r in self.learning.get_history(record.subject_id,record.learning_id)
                     if r.growth_resolution is None]
            if (not solidify and history[-1].record_id==record.record_id
                    and record.record_type is LearningRecordType.ROLLED_BACK):
                target.validation_status=history[-2].validation_status
            kind=LearningRecordType.GROWTH_SUPERSEDED
            reason='Unsubmitted preparation superseded by current confirmed command '+replacement.command_id
        resolution={'prepared_record_id':record.record_id,'prepared_hash':digest(record.to_dict()),
            'outcome':outcome,'replacement_command':replacement.to_dict() if replacement else None}
        resolved=self.learning._record_for(target,record_type=kind,validation_status=target.validation_status,
            permanently_consolidated=trait.active,before_value=record.before_value,after_value=record.after_value,
            reason=reason,source='p15-growth-resolution',trait_id=record.trait_id,state_event_id=record.state_event_id,
            growth_resolution=resolution)
        self.repository.save_change(record.subject_id,target,resolved,trait)
        return resolved

    def process(self,perception,result):
        """Derive interpretations from actual P14 appraisals, never Provider state text."""
        c=self.core; context=perception.continuity_context
        if not context.growth_enabled or not c.current(context):
            raise LearningValidationError('GROWTH_CONTEXT_STALE_OR_DISABLED')
        self.capture(context)
        if context.mind is None:return result
        state=c.subject_states.load(c.subject_id)
        mind=context.mind['proposal']; mutations=list(result.proposed_mutations)
        for kind,path,before in [('narrative','identity.self_narrative',state.identity.self_narrative),
                                  ('relationships','relationship.objects',state.relationship.objects)]:
            doc=deepcopy(before) if before is not None else dict(version='p15-'+kind+'-v1',
                subject_id=c.subject_id,environment=c.environment,authority='SUBJECTIVE_INTERPRETATION',entries=[])
            for episode in mind['episodes']:
                if not episode['source_keys']:continue
                if kind=='relationships' and episode is not max(
                        (e for e in mind['episodes'] if e['object']==episode['object']),
                        key=lambda e:(e['updated_at'],e['id'])):
                    continue
                key=episode['id'] if kind=='narrative' else episode['object']
                old=next((e for e in doc['entries'] if e['id']==key),None)
                related=[e for e in mind['episodes'] if e['object']==episode['object']]
                roots=sorted({r for e in (related if kind=='relationships' else [episode]) for r in e['source_keys']})
                entry=dict(id=key,object_id=episode['object'],interpretation=episode['interpretation'],
                    source_roots=roots,version=1,updated_at=episode['updated_at'])
                if kind=='relationships':
                    entry['stances']=sorted({e['kind'] for e in related} | {
                        d['kind'] for d in mind['dispositions'] if d['object']==episode['object']})
                if old is not None:
                    if all(old[k]==entry[k] for k in entry if k not in {'version','updated_at'}):continue
                    entry['version']=old['version']+1
                    doc['entries'].remove(old)
                doc['entries'].append(entry)
            if doc['entries'] and doc!=before:
                mutations.append(StateMutation(path,ChangeOperation.SET,growth_document(doc,kind=kind),
                    'Subjective continuity from bound appraised experiences; not a factual assertion.'))
        return replace(result,proposed_mutations=mutations,update_subject_state=bool(mutations))
