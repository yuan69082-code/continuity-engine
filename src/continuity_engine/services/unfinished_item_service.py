"""W03 matters: one SubjectState authority, original Action Gate and Evolution.

The Scheduler may consume ``ready`` as an opportunity list. It cannot create
items or decide that the subject wants to pursue one.
"""
from datetime import datetime, timezone

from continuity_engine.domain.action import ActionIntent, ActionType, ResourceLimits, RiskLevel
from continuity_engine.domain.action_capability import InternalActionRequest
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.capability import CapabilityStatus
from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.events import ChangeOperation, Event, EventClassification, StateMutation, StateSection
from continuity_engine.domain.unfinished_item import UnfinishedItem, item_records, TERMINAL


class UnfinishedItemService:
    def __init__(self, core, *, action_repository=None, receipt_verifier=None):
        self.core = core
        self.action_repository = action_repository
        self.receipt_verifier = receipt_verifier

    def submit(self, item: UnfinishedItem, *, command_id: str, expected_revision: int,
               context=None, reason: str, legacy_binding=None):
        """Commit a subject-owned item change once, with evidence and current gates."""
        c = self.core
        if not isinstance(item, UnfinishedItem) or not isinstance(command_id,str) or not command_id.strip():
            raise StateEvolutionError('W03_ITEM_COMMAND_INVALID')
        if (item.subject_id,item.environment)!=(c.subject_id,c.environment):
            raise StateEvolutionError('W03_ITEM_BOUNDARY_MISMATCH')
        if type(expected_revision) is not int or expected_revision < 0:
            raise StateEvolutionError('W03_ITEM_REVISION_INVALID')
        if legacy_binding is not None and (not isinstance(legacy_binding,dict)
                or set(legacy_binding)!={'index','title','list_hash'}
                or type(legacy_binding['index']) is not int or legacy_binding['index']<0
                or not isinstance(legacy_binding['title'],str)
                or not isinstance(legacy_binding['list_hash'],str)):
            raise StateEvolutionError('W03_ITEM_LEGACY_BINDING_INVALID')
        event_id = 'w03-item:' + digest([c.subject_id,c.environment,command_id])[7:]
        identity_payload={'item':item.to_dict(),'expected_revision':expected_revision,
                          'reason':reason,'command_id':command_id}
        # Preserve the exact identity of commands committed by the original
        # W03 service; only an explicit migration adds a new binding.
        if legacy_binding is not None:
            identity_payload['legacy_binding']=legacy_binding
        identity=digest(identity_payload)
        history = c.subject_states.get_update_history(c.subject_id)
        prior = next((u for u in history if u.event.event_id==event_id),None)
        if prior is not None:
            if (prior.event.metadata.get('w03_command_hash')!=identity
                    or prior.before_revision!=expected_revision
                    or tuple(m.field_path for m in prior.event.mutations)!=
                       (('continuity.item_records','continuity.unfinished_items')
                        if legacy_binding is not None else ('continuity.item_records',))):
                raise StateEvolutionError('W03_ITEM_COMMAND_IDENTITY_CONFLICT')
            return prior  # Original committed fact; no new gate or revision.

        state=c.subject_states.require_active(c.subject_id,c.environment)
        if state.revision!=expected_revision:
            raise StateEvolutionError('W03_ITEM_STATE_REVISION_CHANGED')
        if context is not None and not c.current(context):
            raise StateEvolutionError('W03_ITEM_CONTEXT_STALE_OR_UNAUTHORIZED')
        now=c.clock()
        if now.tzinfo is None or item.updated_at>now.astimezone(timezone.utc).isoformat().replace('+00:00','Z'):
            raise StateEvolutionError('W03_ITEM_TRUSTED_TIME_INVALID')
        current=item_records(state.continuity.item_records,subject_id=c.subject_id,environment=c.environment)
        old=next((UnfinishedItem.from_dict(row) for row in current if row['item_id']==item.item_id),None)
        known=self._historical_items(history)
        if old is None:
            if item.item_id in known:
                raise StateEvolutionError('W03_ITEM_TERMINAL_OR_MISSING_CURRENT_RECORD')
            if item.revision!=0 or item.status in TERMINAL:
                raise StateEvolutionError('W03_ITEM_INITIAL_STATE_INVALID')
        else:
            if (old.status in TERMINAL or item.revision!=old.revision+1
                    or item.created_at!=old.created_at):
                raise StateEvolutionError('W03_ITEM_TRANSITION_INVALID')
        legacy_next=None
        if legacy_binding is not None:
            legacy=list(state.continuity.unfinished_items)
            index=legacy_binding['index']
            if (index>=len(legacy)
                    or legacy[index]!=legacy_binding['title']
                    or item.title!=legacy_binding['title']
                    or digest(legacy)!=legacy_binding['list_hash']):
                raise StateEvolutionError('W03_ITEM_LEGACY_BINDING_CHANGED')
            legacy_next=legacy[:index]+legacy[index+1:]
        if item.status not in {'CANCELLED','FAILED'}:
            self._verify_roots(item.source_roots,context=context)
        if item.status=='COMPLETED':
            self._verify_completion(item)
        intent=ActionIntent('w03-item:'+command_id,ActionType.UPDATE_STATE,
            'Subject-owned unfinished matter',reason,c.subject_id,'w03-item',1.0,
            RiskLevel.LOW,['subject_state:update'],0,now)
        gate=c.action_gate.assess_local_action(intent,subject_id=c.subject_id,
            environment=c.environment,limits=c.limits or ResourceLimits(),confirmed=False)
        if not gate.approved:
            raise StateEvolutionError('W03_ITEM_ACTION_GATE_'+str(gate.rejection_reason))
        # Terminal facts remain in the original Evolution history. Only live
        # matters consume the bounded current SubjectState collection.
        next_records=[row for row in current if row['item_id']!=item.item_id
                      and row['status'] not in TERMINAL]
        if item.status not in TERMINAL:
            next_records.append(item.to_dict())
        next_records.sort(key=lambda row:row['item_id'])
        if context is not None and not c.current(context):
            raise StateEvolutionError('W03_ITEM_CONTEXT_STALE_OR_UNAUTHORIZED')
        if item.status not in {'CANCELLED','FAILED'}:
            self._verify_roots(item.source_roots,context=context)
        mutations=[StateMutation('continuity.item_records',ChangeOperation.SET,next_records,reason)]
        if legacy_next is not None:
            mutations.append(StateMutation('continuity.unfinished_items',ChangeOperation.SET,legacy_next,reason))
        event=Event.create(event_id=event_id,occurred_at=now,source='w03.subject-item',
            event_type='unfinished_item_update',content='Subject matter state changed.',
            impact_scope=[StateSection.CONTINUITY],classification=EventClassification.STATE_CHANGE,
            mutations=mutations, reason=reason,
            metadata={'w03_command_hash':identity,'item_id':item.item_id,
                      **({'w03_terminal_record':item.to_dict()} if item.status in TERMINAL else {}),
                      **({'w03_legacy_binding':legacy_binding} if legacy_binding is not None else {})})
        return c.subject_states.apply_event(c.subject_id,event,expected_revision=expected_revision).update

    @staticmethod
    def _historical_items(history):
        """Project original Evolution facts; never persist a second item ledger."""
        known={}
        for update in history:
            event=update.event
            if event.source!='w03.subject-item':
                continue
            identifier=event.metadata.get('item_id')
            if not isinstance(identifier,str):
                continue
            terminal=event.metadata.get('w03_terminal_record')
            if terminal is not None:
                parsed=UnfinishedItem.from_dict(terminal)
                if parsed.item_id!=identifier or parsed.status not in TERMINAL:
                    raise StateEvolutionError('W03_ITEM_HISTORY_BINDING_INVALID')
                known[identifier]=parsed.to_dict()
                continue
            mutation=next((m for m in event.mutations
                           if m.field_path=='continuity.item_records'),None)
            if mutation is not None:
                row=next((r for r in mutation.value if r.get('item_id')==identifier),None)
                if row is not None:
                    known[identifier]=UnfinishedItem.from_dict(row).to_dict()
        return known

    def _verify_roots(self, roots, *, context=None):
        c=self.core
        if context is not None:
            from continuity_engine.domain.context_routing import ContextPartition
            for partition,source_id,prefix in (
                    (ContextPartition.TIMELINE,'engine.timeline','event:'),
                    (ContextPartition.MEMORY,'engine.memory','memory:')):
                if any(root.startswith(prefix) for root in roots):
                    permission=c.permission.authorize_source(context.route.plan.request,
                                                             source_id,partition)
                    if not permission.allowed:
                        raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT')
        active={entry.event.event_id for entry in c.timeline.rebuild(c.subject_id).entries
                if entry.status.value=='active'}
        for root in roots:
            if root.startswith('event:'):
                if root[6:] not in active:
                    raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT')
            elif root.startswith('memory:'):
                try:
                    memory=c.memory.load_memory(c.subject_id,root[7:])
                except Exception as exc:
                    raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT') from exc
                if (memory.subject_id!=c.subject_id or memory.environment!=c.environment
                        or not memory.is_available
                        or not c.memory.current_usable(c.subject_id,memory.memory_id)):
                    raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT')
                if memory.source_message_ids:
                    absorption=getattr(c.external_capabilities,'absorption',None)
                    if absorption is None or not absorption.memory_current(memory):
                        raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT')
                else:
                    from .memory_lifecycle_service import TimelineMemorySources
                    if TimelineMemorySources(c.timeline,c.memory,c.subject_id)(memory) is None:
                        raise StateEvolutionError('W03_ITEM_SOURCE_NOT_CURRENT')
            else:
                raise StateEvolutionError('W03_ITEM_SOURCE_UNSUPPORTED')

    def _verify_completion(self,item):
        c=self.core
        evidence=item.completion
        if evidence['kind']=='INTERNAL_EVENT':
            facts=[u.event for u in c.subject_states.get_update_history(c.subject_id)
                   if u.event.event_id==evidence['identity']]
            if (len(facts)!=1 or facts[0].canonical_hash()!=evidence['hash']
                    or facts[0].source=='w03.subject-item'
                    or facts[0].metadata.get('w03_item_result')!=item.item_id):
                raise StateEvolutionError('W03_ITEM_COMPLETION_FACT_UNVERIFIED')
            return
        if self.action_repository is None or self.receipt_verifier is None:
            raise StateEvolutionError('W03_ITEM_REALITY_COMPLETION_NOT_READY')
        request=self.action_repository.load_capability_request(evidence['identity'])
        if (not isinstance(request,InternalActionRequest)
                or (request.subject_id,request.choice.environment)!=(c.subject_id,c.environment)):
            raise StateEvolutionError('W03_ITEM_COMPLETION_REQUEST_MISMATCH')
        attempts=c.coordination.action_attempts(request,receipt_verifier=self.receipt_verifier)
        if not any(a.result.status is CapabilityStatus.SUCCEEDED and a.result.receipt is not None
                   and a.result.receipt.canonical_hash()==evidence['hash'] for a in attempts):
            raise StateEvolutionError('W03_ITEM_COMPLETION_FACT_UNVERIFIED')

    def read(self, context):
        """Read-only current matters and legacy strings; no scheduling or cognition."""
        if context is None or not self.core.current(context):
            raise StateEvolutionError('W03_ITEM_READ_CONTEXT_STALE_OR_UNAUTHORIZED')
        state=self.core.subject_states.load(self.core.subject_id)
        rows=item_records(state.continuity.item_records,subject_id=self.core.subject_id,
                          environment=self.core.environment)
        history=self.core.subject_states.get_update_history(self.core.subject_id)
        terminal=[row for row in self._historical_items(history).values()
                  if row['status'] in TERMINAL and not any(x['item_id']==row['item_id'] for x in rows)]
        rows=[*rows,*terminal[-32:]]
        source_status={}
        for row in rows:
            try:
                self._verify_roots(row['source_roots'],context=context)
            except StateEvolutionError:
                source_status[row['item_id']]='SOURCE_NOT_CURRENT'
            else:
                source_status[row['item_id']]='CURRENT'
        legacy=[{'title':title,'status':'LEGACY_UNSTRUCTURED'} for title in state.continuity.unfinished_items]
        changes=[]
        for update in history:
            event=update.event
            if event.source!='w03.subject-item':
                continue
            changes.append({'item_id':event.metadata.get('item_id'),'event_id':event.event_id,
                'update_id':update.update_id,'after_revision':update.after_revision,
                'reason':event.reason})
        result={'subject_id':self.core.subject_id,'environment':self.core.environment,
                'source_revision':state.revision,'items':rows,'source_status':source_status,
                'legacy':legacy,'change_count':len(changes),
                'change_history':tuple(changes[-32:]),'history_truncated':len(changes)>32}
        for row in rows:
            try:
                self._verify_roots(row['source_roots'],context=context)
            except StateEvolutionError:
                current_status='SOURCE_NOT_CURRENT'
            else:
                current_status='CURRENT'
            if current_status!=source_status[row['item_id']]:
                raise StateEvolutionError('W03_ITEM_SOURCE_CHANGED_BEFORE_RETURN')
        if (not self.core.current(context)
                or self.core.subject_states.load(self.core.subject_id).revision!=state.revision):
            raise StateEvolutionError('W03_ITEM_READ_CHANGED_BEFORE_RETURN')
        return result

    def ready(self, context, *, at=None, wait_satisfied=None):
        """Deterministic, fair opportunity order; blocked urgent matters cannot starve others."""
        at=at or self.core.clock()
        if at.tzinfo is None:
            raise StateEvolutionError('W03_ITEM_TRUSTED_TIME_INVALID')
        now=at.astimezone(timezone.utc)
        eligible=[]
        view=self.read(context)
        for row in view['items']:
            item=UnfinishedItem.from_dict(row)
            if view['source_status'][item.item_id]!='CURRENT':
                continue
            if not item.willing or item.status in TERMINAL or item.status in {'FAILED','DEFERRED'}:
                continue
            if item.status=='WAITING' and (wait_satisfied is None or not wait_satisfied(item)):
                continue
            age=max(0,int((now-datetime.fromisoformat(item.created_at.replace('Z','+00:00'))).total_seconds()//3600))
            deadline_score=0
            if item.due_at is not None:
                hours_left=(datetime.fromisoformat(item.due_at.replace('Z','+00:00'))-now).total_seconds()/3600
                deadline_score=(min(8,max(0,int((24-hours_left)//3))) if hours_left>0 else
                                8+min(8,int(-hours_left//24)))
            score={'LOW':0,'NORMAL':4,'URGENT':8}[item.urgency]+age+deadline_score
            eligible.append((score,item))
        eligible.sort(key=lambda pair:(-pair[0],pair[1].created_at,pair[1].item_id))
        return tuple(item for _,item in eligible)
