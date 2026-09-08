"""Management orchestration through the existing Action gate and Evolution.

Only SubjectState stores current lifecycle. Original Event identity is the
idempotency record; credentials are never persisted. Logical TEST deletion does
not erase state, Event history, backups, or production data.
"""
from continuity_engine.domain.action import ActionIntent, ActionType, ResourceLimits, RiskLevel
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, StateMutation, StateSection, ChangeOperation
from continuity_engine.domain.models import SubjectState
from continuity_engine.domain.subject_lifecycle import (
    LifecycleCommand, LifecycleError, LifecyclePolicy, SubjectLifecycle, lifecycle_status, transition,
)


class SubjectLifecycleService:
    def __init__(self, states, *, environment, authority, action_gate, clock,
                 policy=None, limits=None):
        if environment not in {'TEST', 'RESEARCH'}:
            raise LifecycleError('SUBJECT_ENVIRONMENT_INVALID')
        self.states, self.environment, self.authority = states, environment, authority
        self.action_gate, self.clock = action_gate, clock
        self.policy, self.limits = policy or LifecyclePolicy(), limits or ResourceLimits()

    def import_test_observation(self, command, credential, *, source_states,
                                source_authority, source_credential, allowed_types=()):
        """Explicit disposable TEST import; not production migration or fact authority."""
        if (self.environment!='TEST' or command.environment!='TEST'
                or command.data_type not in allowed_types):
            raise LifecycleError('SUBJECT_MIGRATION_POLICY_NOT_READY')
        principal=self.authority.identify(command,credential)
        source_principal=source_authority.identify(command,source_credential)
        event_id='p15-import:'+digest([command.subject_id,command.command_id])[7:]
        metadata={'command':command.to_dict(),'principal_id':principal,'source_principal_id':source_principal,
                  'source_hash':command.source_hash,'authority':'IMPORTED_OBSERVATION_NOT_VERIFIED_FACT'}
        existing=next((u for u in self.states.get_update_history(command.subject_id)
                       if u.event.event_id==event_id),None)
        if existing is not None:
            if existing.event.metadata!=metadata:raise LifecycleError('SUBJECT_MIGRATION_IDENTITY_CONFLICT')
            return existing
        target=self.states.require_active(command.subject_id,'TEST')
        source=source_states.require_active(command.source_subject_id,'TEST')
        if (target.revision!=command.expected_revision or source.revision!=command.source_revision
                or target.temporal.subject_lifecycle is None or source.temporal.subject_lifecycle is None
                or target.temporal.subject_lifecycle['owner_principal_id']!=principal
                or source.temporal.subject_lifecycle['owner_principal_id']!=source_principal):
            raise LifecycleError('SUBJECT_MIGRATION_OWNER_OR_REVISION_INVALID')
        self.authority.authorize(command,credential,at=self.clock())
        source_authority.authorize(command,source_credential,at=self.clock())
        from .timeline_service import TimelineService
        from continuity_engine.domain.timeline import TimelineEventStatus
        original=next((entry.event for entry in TimelineService(source_states._repository).rebuild(source.subject_id).entries
                       if entry.event.event_id==command.source_event_id and entry.status is TimelineEventStatus.ACTIVE),None)
        if (original is None or original.canonical_hash()!=command.source_hash or original.mutations
                or original.metadata.get('visibility')!='PUBLIC'
                or original.classification not in {EventClassification.OBSERVATION,EventClassification.FACT}):
            raise LifecycleError('SUBJECT_MIGRATION_SOURCE_NOT_ALLOWED')
        intent=ActionIntent(event_id,ActionType.UPDATE_STATE,'Explicit TEST migration',
            'Import one confirmed public observation',command.subject_id,'Append non-authoritative observation',
            1.0,RiskLevel.LOW,['subject.lifecycle'],0,self.clock())
        if not self.action_gate.assess_local_action(intent,subject_id=command.subject_id,environment='TEST',
                limits=self.limits,confirmed=True).approved:
            raise LifecycleError('SUBJECT_MIGRATION_ACTION_GATE_DENIED')
        event=Event.create(event_id=event_id,occurred_at=self.clock(),source='p15-test-import',
            source_kind=EventSourceKind.TEST,event_type='imported_public_observation',
            classification=EventClassification.OBSERVATION,content=original.content,
            impact_scope=[StateSection.CONTINUITY],mutations=[],reason='Explicit isolated TEST import',metadata=metadata)
        return self.states.apply_event(command.subject_id,event,expected_revision=command.expected_revision).update

    def submit(self, command, credential):
        command = LifecycleCommand.from_dict(command.to_dict())
        if command.environment != self.environment:
            raise LifecycleError('SUBJECT_ENVIRONMENT_MISMATCH')
        principal = self.authority.identify(command, credential)
        event_id = 'p15-lifecycle:' + digest([command.subject_id, command.command_id])[7:]
        exists = self.states._repository.exists(command.subject_id)
        history = self.states.get_update_history(command.subject_id) if exists else []
        existing = next((r for r in history if r.event.event_id == event_id), None)
        metadata = {'command': command.to_dict(), 'principal_id': principal, 'environment': self.environment}
        if existing is not None:
            if (existing.event.metadata != metadata or existing.subject_id != command.subject_id
                    or existing.event.event_type != 'subject_lifecycle'):
                raise LifecycleError('SUBJECT_COMMAND_IDENTITY_CONFLICT')
            return existing  # Original fact, not new authorization or a second revision.
        if command.operation == 'CREATE' and exists:
            raise LifecycleError('SUBJECT_IDENTITY_ALREADY_EXISTS')
        if command.operation != 'CREATE' and not exists:
            raise LifecycleError('SUBJECT_IDENTITY_MISSING')
        state = self.states.load(command.subject_id) if exists else SubjectState.create(command.subject_id, self.clock())

        def authorize(current):
            now = self.clock()
            if command.requested_at > now or current.revision != command.expected_revision:
                raise LifecycleError('SUBJECT_COMMAND_STALE_OR_FUTURE')
            if now < current.temporal.updated_at:
                raise LifecycleError('SUBJECT_CLOCK_REGRESSION')
            verified = self.authority.authorize(command, credential, at=now)
            if verified != principal:
                raise LifecycleError('SUBJECT_PRINCIPAL_CHANGED')
            value = current.temporal.subject_lifecycle
            if value is not None:
                bound = SubjectLifecycle.from_dict(value)
                if bound.environment != self.environment or (
                    command.initiator == 'OWNER' and bound.owner_principal_id != principal
                ):
                    raise LifecycleError('SUBJECT_OWNER_OR_ENVIRONMENT_MISMATCH')
            if command.initiator == 'SUBJECT':
                if principal != command.subject_id or lifecycle_status(current) != 'ACTIVE':
                    raise LifecycleError('SUBJECT_INTENT_NOT_AUTHORIZED')
            if command.operation == 'ARCHIVE' and not self.policy.archive_configured:
                raise LifecycleError('SUBJECT_ARCHIVE_POLICY_NOT_READY')
            if command.operation == 'DELETE':
                if (self.environment != 'TEST' or not self.policy.allow_test_logical_delete
                        or self.policy.delete_retention_seconds is None):
                    raise LifecycleError('SUBJECT_DELETE_POLICY_NOT_READY')
                if value is None or (now - SubjectLifecycle.from_dict(value).changed_at).total_seconds() < self.policy.delete_retention_seconds:
                    raise LifecycleError('SUBJECT_DELETE_RETENTION_NOT_ELAPSED')
            intent = ActionIntent(intent_id=event_id, action_type=ActionType.UPDATE_STATE,
                source_thought='Explicit lifecycle management command', reason=command.reason,
                target=command.subject_id, expected_effect=command.operation, confidence=1.0,
                risk_level=RiskLevel.LOW, required_permissions=['subject.lifecycle'],
                estimated_resource_cost=0, created_at=now)
            decision = self.action_gate.assess_local_action(intent, subject_id=command.subject_id,
                environment=self.environment, limits=self.limits, confirmed=True)
            if not decision.approved:
                raise LifecycleError('SUBJECT_ACTION_GATE_DENIED:' + str(decision.rejection_reason))

        authorize(state)
        is_intent = command.initiator == 'SUBJECT'
        target = ('CREATE' if command.operation == 'CREATE' else
                  lifecycle_status(state) if is_intent else transition(lifecycle_status(state), command.operation))
        value = SubjectLifecycle(command.subject_id, self.environment, principal, target,
                                 self.clock(), command.reason).to_dict()
        if state.temporal.subject_lifecycle is not None:
            value['owner_principal_id'] = state.temporal.subject_lifecycle['owner_principal_id']
        event = Event.create(event_id=event_id, occurred_at=command.requested_at,
            source='subject_lifecycle_service', source_kind=EventSourceKind.INTERNAL, event_type='subject_lifecycle',
            classification=EventClassification.INTENTION if is_intent else EventClassification.STATE_CHANGE,
            content=command.operation, impact_scope=[StateSection.TEMPORAL], reason=command.reason,
            mutations=[] if is_intent else [StateMutation('temporal.subject_lifecycle', ChangeOperation.SET,
                value, command.reason)], metadata=metadata)
        if not exists:
            authorize(state)
            result = self.states._evolver.evolve(state, event, applied_at=self.clock())
            self.states._repository.save_initial_transition(result.state, result.update)
            return result.update
        return self.states._apply_event(command.subject_id, event,
            expected_revision=command.expected_revision, lifecycle_authorization=authorize).update
