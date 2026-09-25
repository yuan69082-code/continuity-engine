"""W03 recognition view and commits over existing Event/Learning/Evolution.

The view has no store. An annotation is a hypothesis, never a fact or a
permission. Only the original SubjectState transition owns current cognition.
"""
from copy import deepcopy
from datetime import timezone

from continuity_engine.domain.action import ActionIntent, ActionType, ResourceLimits, RiskLevel
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.dynamic_mind import utc
from continuity_engine.domain.errors import LearningValidationError
from continuity_engine.domain.events import ChangeOperation, Event, EventClassification, StateMutation, StateSection
from continuity_engine.domain.learning import LearningRecordType, LearningValidationStatus
from continuity_engine.domain.subject_growth import growth_document


_FIELDS={'object_id','owner','aliases','scope','conclusion','polarity','valid_at','source_type'}


def _descriptor(value):
    if not isinstance(value,dict) or not _FIELDS<=set(value) or set(value)-_FIELDS-{'expires_at','corrects'}:
        raise LearningValidationError('W03_RECOGNITION_DESCRIPTOR_INVALID')
    if value['owner'] not in {'SUBJECT','USER','OTHER','RESOURCE'} or value['polarity'] not in {'SUPPORT','COUNTER'}:
        raise LearningValidationError('W03_RECOGNITION_BOUNDARY_INVALID')
    for name in ('object_id','scope','conclusion','valid_at','source_type'):
        if not isinstance(value[name],str) or not value[name].strip():
            raise LearningValidationError('W03_RECOGNITION_'+name.upper()+'_INVALID')
    if (not isinstance(value['aliases'],list) or len(value['aliases'])>16
            or any(not isinstance(a,str) or not a.strip() for a in value['aliases'])
            or len(set(value['aliases']))!=len(value['aliases'])):
        raise LearningValidationError('W03_RECOGNITION_ALIASES_INVALID')
    valid_at=utc(value['valid_at'])
    if value.get('expires_at') is not None and utc(value['expires_at'])<=valid_at:
        raise LearningValidationError('W03_RECOGNITION_EXPIRY_INVALID')
    if value.get('corrects') is not None:
        if not isinstance(value['corrects'],str) or not value['corrects'].strip():
            raise LearningValidationError('W03_RECOGNITION_CORRECTION_INVALID')
    return dict(value)


class RecognitionService:
    def __init__(self, core):
        if core.growth is None:
            raise LearningValidationError('W03_RECOGNITION_REQUIRES_ORIGINAL_LEARNING')
        self.core=core
        self.learning=core.growth.learning

    def _origin(self, learning_id):
        c=self.core
        candidate=self.learning.get_learning_event(c.subject_id,learning_id)
        origins=[r for r in self.learning.get_history(c.subject_id,learning_id)
                 if r.record_type is LearningRecordType.CANDIDATE_CREATED]
        if len(origins)!=1 or not isinstance(origins[0].original_experience,dict):
            raise LearningValidationError('W03_RECOGNITION_ORIGIN_MISSING')
        binding=origins[0].original_experience.get('p15_source_binding')
        if binding is None:
            raise LearningValidationError('W03_RECOGNITION_SOURCE_BINDING_MISSING')
        c.growth.verify_source(candidate,binding)
        entries={e.event.event_id:e.event for e in c.timeline.rebuild(c.subject_id).entries
                 if e.status.value=='active'}
        event=entries.get(binding['event_id'])
        if event is None or event.canonical_hash()!=binding['event_hash']:
            raise LearningValidationError('W03_RECOGNITION_EVENT_NOT_CURRENT')
        value=_descriptor(event.metadata.get('w03_recognition'))
        if value.get('expires_at') is not None and c.clock()>=utc(value['expires_at']):
            raise LearningValidationError('W03_RECOGNITION_SOURCE_EXPIRED')
        expected='recognition:'+digest([value['owner'],value['object_id'],value['scope'],
                                        value['conclusion'],value['polarity']])[7:]
        if (candidate.proposed_change.value!=expected or
                candidate.proposed_change.field_path!='relationship.interaction_preferences'):
            raise LearningValidationError('W03_RECOGNITION_CANDIDATE_BINDING_INVALID')
        return candidate,value,event

    def capture(self, context):
        """Capture only consumed, annotated original experiences through P15."""
        if not self.core.current(context):
            raise LearningValidationError('W03_RECOGNITION_CONTEXT_STALE')
        ids=self.core.growth.capture(context)
        found=[]
        for identity in ids:
            try:
                self._origin(identity)
            except LearningValidationError as exc:
                if str(exc)=='W03_RECOGNITION_DESCRIPTOR_INVALID':
                    continue  # Ordinary P15 learning is outside this derived view.
                raise
            found.append(identity)
        return tuple(found)

    def validate(self, learning_id, corroborating):
        ids=(learning_id,*tuple(corroborating))
        descriptors=[self._origin(identifier)[1] for identifier in ids]
        key=lambda d:(d['owner'],d['object_id'],d['scope'],d['conclusion'],d['polarity'],d.get('corrects'))
        if any(key(value)!=key(descriptors[0]) for value in descriptors):
            raise LearningValidationError('W03_RECOGNITION_INCONSISTENT_SUPPORT')
        return self.core.growth.validate(learning_id,corroborating)

    def commit(self, learning_id, *, command_id, expected_revision, reason, context=None):
        """Commit a validated subjective interpretation, never an external fact."""
        c=self.core
        event_id='w03-recognition:'+digest([c.subject_id,c.environment,command_id])[7:]
        command_hash=digest([learning_id,expected_revision,reason,command_id])
        history=c.subject_states.get_update_history(c.subject_id)
        prior=next((u for u in history if u.event.event_id==event_id),None)
        if prior is not None:
            if (prior.event.metadata.get('w03_command_hash')!=command_hash
                    or prior.before_revision!=expected_revision):
                raise LearningValidationError('W03_RECOGNITION_COMMAND_IDENTITY_CONFLICT')
            return prior
        target,value,_=self._origin(learning_id)
        if value['polarity']!='SUPPORT':
            raise LearningValidationError('W03_RECOGNITION_COUNTEREVIDENCE_NOT_CONCLUSION')
        state=c.subject_states.require_active(c.subject_id,c.environment)
        if state.revision!=expected_revision:
            raise LearningValidationError('W03_RECOGNITION_STATE_REVISION_CHANGED')
        if context is not None and not c.current(context):
            raise LearningValidationError('W03_RECOGNITION_CONTEXT_STALE')
        if target.validation_status is not LearningValidationStatus.VALIDATED:
            raise LearningValidationError('W03_RECOGNITION_CURRENT_VALIDATION_REQUIRED')
        self.learning._verify_current_support(c.subject_id,target)
        for identifier in target.evidence_learning_ids:
            self._origin(identifier)  # P15 verifies source; W03 also checks each expiry.
        now=c.clock()
        doc=deepcopy(state.relationship.objects) if state.relationship.objects is not None else {
            'version':'p15-relationships-v1','subject_id':c.subject_id,'environment':c.environment,
            'authority':'SUBJECTIVE_INTERPRETATION','entries':[]}
        key=value['owner']+':'+value['object_id']+':'+value['scope']
        old=next((entry for entry in doc['entries'] if entry['id']==key),None)
        if old is not None and value.get('corrects')!=old['interpretation']:
            raise LearningValidationError('W03_RECOGNITION_CORRECTION_BINDING_REQUIRED')
        if (old is not None and old['interpretation']==value['conclusion']
                and set(old['source_roots'])==set(target.root_evidence_ids)):
            raise LearningValidationError('W03_RECOGNITION_NO_NEW_EVIDENCE')
        entry={'id':key,'object_id':value['object_id'],'interpretation':value['conclusion'],
               'source_roots':sorted(target.root_evidence_ids),'version':old['version']+1 if old else 1,
               'updated_at':now.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
               'stances':['recognition:'+value['scope']]}
        if old is not None:
            doc['entries'].remove(old)
        doc['entries'].append(entry)
        doc=growth_document(doc,kind='relationships',subject_id=c.subject_id)
        intent=ActionIntent('w03-recognition:'+command_id,ActionType.UPDATE_STATE,
            'Evidence-backed subjective recognition',reason,c.subject_id,'recognition-update',1.0,
            RiskLevel.LOW,['subject_state:update'],0,now)
        gate=c.action_gate.assess_local_action(intent,subject_id=c.subject_id,
            environment=c.environment,limits=c.limits or ResourceLimits(),confirmed=False)
        if not gate.approved:
            raise LearningValidationError('W03_RECOGNITION_ACTION_GATE_'+str(gate.rejection_reason))
        event=Event.create(event_id=event_id,occurred_at=now,source='w03.recognition',
            event_type='recognition_change',content='Evidence-backed subjective recognition changed.',
            impact_scope=[StateSection.RELATIONSHIP],classification=EventClassification.STATE_CHANGE,
            mutations=[StateMutation('relationship.objects',ChangeOperation.SET,doc,reason)],reason=reason,
            metadata={'w03_command_hash':command_hash,'learning_id':learning_id,
                      'operation':'REPLACE' if old else 'FORM',
                      'owner':value['owner'],'object_id':value['object_id'],'scope':value['scope'],
                      'prior_version':old['version'] if old else None,
                      'prior_hash':digest(old) if old else None})
        return c.subject_states.apply_event(c.subject_id,event,expected_revision=expected_revision).update

    def withdraw(self, learning_id, *, command_id, expected_revision, reason, context=None):
        """Remove a current subjective conclusion using validated contrary roots.

        The old state and its reasons remain in the original Evolution history.
        This is not deletion of the original experiences or their Learning records.
        """
        c=self.core
        event_id='w03-recognition:'+digest([c.subject_id,c.environment,command_id])[7:]
        command_hash=digest(['WITHDRAW',learning_id,expected_revision,reason,command_id])
        history=c.subject_states.get_update_history(c.subject_id)
        prior=next((u for u in history if u.event.event_id==event_id),None)
        if prior is not None:
            if (prior.event.metadata.get('w03_command_hash')!=command_hash
                    or prior.before_revision!=expected_revision):
                raise LearningValidationError('W03_RECOGNITION_COMMAND_IDENTITY_CONFLICT')
            return prior
        target,value,_=self._origin(learning_id)
        if value['polarity']!='COUNTER' or value.get('corrects') is None:
            raise LearningValidationError('W03_RECOGNITION_BOUND_COUNTEREVIDENCE_REQUIRED')
        state=c.subject_states.require_active(c.subject_id,c.environment)
        if state.revision!=expected_revision:
            raise LearningValidationError('W03_RECOGNITION_STATE_REVISION_CHANGED')
        if context is not None and not c.current(context):
            raise LearningValidationError('W03_RECOGNITION_CONTEXT_STALE')
        if target.validation_status is not LearningValidationStatus.VALIDATED:
            raise LearningValidationError('W03_RECOGNITION_CURRENT_VALIDATION_REQUIRED')
        self.learning._verify_current_support(c.subject_id,target)
        for identifier in target.evidence_learning_ids:
            self._origin(identifier)
        doc=deepcopy(state.relationship.objects)
        if doc is None:
            raise LearningValidationError('W03_RECOGNITION_NOT_CURRENT')
        key=value['owner']+':'+value['object_id']+':'+value['scope']
        old=next((entry for entry in doc['entries'] if entry['id']==key),None)
        if old is None or old['interpretation']!=value['corrects']:
            raise LearningValidationError('W03_RECOGNITION_CORRECTION_BINDING_REQUIRED')
        doc['entries'].remove(old)
        now=c.clock()
        intent=ActionIntent('w03-recognition:'+command_id,ActionType.UPDATE_STATE,
            'Withdraw evidence-backed subjective conclusion',reason,c.subject_id,
            'recognition-withdraw',1.0,RiskLevel.LOW,['subject_state:update'],0,now)
        gate=c.action_gate.assess_local_action(intent,subject_id=c.subject_id,
            environment=c.environment,limits=c.limits or ResourceLimits(),confirmed=False)
        if not gate.approved:
            raise LearningValidationError('W03_RECOGNITION_ACTION_GATE_'+str(gate.rejection_reason))
        event=Event.create(event_id=event_id,occurred_at=now,source='w03.recognition',
            event_type='recognition_withdrawal',content='Subjective recognition withdrawn after contrary evidence.',
            impact_scope=[StateSection.RELATIONSHIP],classification=EventClassification.STATE_CHANGE,
            mutations=[StateMutation('relationship.objects',ChangeOperation.SET,doc,reason)],reason=reason,
            metadata={'w03_command_hash':command_hash,'learning_id':learning_id,
                      'operation':'WITHDRAW','owner':value['owner'],
                      'object_id':value['object_id'],'scope':value['scope'],
                      'prior_version':old['version'],'prior_hash':digest(old)})
        return c.subject_states.apply_event(c.subject_id,event,expected_revision=expected_revision).update

    def read(self, context):
        """Rebuild the view without writes; stale supports never appear current."""
        c=self.core
        if context is None or not c.current(context):
            raise LearningValidationError('W03_RECOGNITION_READ_CONTEXT_STALE')
        state=c.subject_states.load(c.subject_id)
        doc=state.relationship.objects
        entries=[]
        if doc is not None:
            growth_document(doc,kind='relationships',subject_id=c.subject_id)
        for entry in doc['entries'] if doc else ():
            if not entry['id'].startswith(('SUBJECT:','USER:','OTHER:','RESOURCE:')):
                continue
            supporting=[];counter=[];aliases=set();current=False
            for candidate in self.learning.list_learning_events(c.subject_id):
                try:
                    _,value,_=self._origin(candidate.learning_id)
                except LearningValidationError:
                    continue
                if entry['id']!=value['owner']+':'+value['object_id']+':'+value['scope']:
                    continue
                aliases.update(value['aliases'])
                origin=next(r for r in self.learning.get_history(c.subject_id,candidate.learning_id)
                            if r.record_type is LearningRecordType.CANDIDATE_CREATED)
                reference=origin.original_experience['p15_source_binding']['reference']
                row={'learning_id':candidate.learning_id,'roots':tuple(candidate.root_evidence_ids),
                     'status':candidate.validation_status.value,'conclusion':value['conclusion'],
                     'valid_at':value['valid_at'],'expires_at':value.get('expires_at'),
                     'source_type':value['source_type'],'source_version':reference['version'],
                     'source_hash':reference['content_hash'],'corrects':value.get('corrects')}
                (counter if value['polarity']=='COUNTER' else supporting).append(row)
                if (value['polarity']=='SUPPORT' and value['conclusion']==entry['interpretation']
                        and candidate.validation_status is LearningValidationStatus.VALIDATED
                        and set(candidate.root_evidence_ids)==set(entry['source_roots'])):
                    try:
                        self.learning._verify_current_support(c.subject_id,candidate)
                        for identifier in candidate.evidence_learning_ids:self._origin(identifier)
                    except LearningValidationError:
                        pass
                    else:
                        current=True
            contested=any(row['corrects']==entry['interpretation'] for row in counter)
            entries.append({'object_id':entry['object_id'],'scope':entry['id'].split(':',2)[-1],
                'aliases':tuple(sorted(aliases)),'conclusion':entry['interpretation'],
                'status':('CONTESTED' if contested and current else
                          'CURRENT' if current else 'STALE_REVIEW_REQUIRED'),
                'version':entry['version'],'roots':tuple(entry['source_roots']),
                'support':tuple(supporting),'counterevidence':tuple(counter)})
        changes=[]
        for update in c.subject_states.get_update_history(c.subject_id):
            event=update.event
            if event.source!='w03.recognition':
                continue
            metadata=event.metadata
            changes.append({'event_id':event.event_id,'update_id':update.update_id,
                'after_revision':update.after_revision,'operation':metadata.get('operation',
                    'WITHDRAW' if event.event_type=='recognition_withdrawal' else 'CHANGE'),
                'owner':metadata.get('owner'),'object_id':metadata.get('object_id'),
                'scope':metadata.get('scope'),'learning_id':metadata.get('learning_id'),
                'prior_hash':metadata.get('prior_hash'),'reason':event.reason})
        result={'subject_id':c.subject_id,'source_revision':state.revision,
                'entries':tuple(entries),'change_count':len(changes),
                'change_history':tuple(changes[-32:]),'history_truncated':len(changes)>32}
        if not c.current(context) or c.subject_states.load(c.subject_id).revision!=state.revision:
            raise LearningValidationError('W03_RECOGNITION_READ_CHANGED_BEFORE_RETURN')
        return result
