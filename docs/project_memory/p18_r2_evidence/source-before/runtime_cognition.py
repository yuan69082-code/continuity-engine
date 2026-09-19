"""Native P14/C1 work on original Scheduler, Wake, ThinkSession and E5-A records."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL,uuid5

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.dynamic_mind import MindState
from continuity_engine.domain.errors import StateNotFoundError
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError, RuntimeDeferred, RuntimeNeed
from continuity_engine.domain.resources import ResourceRequest, ResourceSessionType
from continuity_engine.domain.scheduling import NotificationReceipt, NotificationStatus, stable_attempt_id
from continuity_engine.domain.thinking import ThinkingDepth, TokenBudget
from .resource_aware_wake_scheduler import ResourceAwareWakeScheduler
from .wake_perception_thinking_action_service import WakePerceptionThinkingActionService


class RuntimeBudgets:
    """Reopen an existing reservation, never allocate the same session twice."""
    def __init__(self,resources,guard):self.resources=resources;self.guard=guard
    def allocate(self,request):
        self.guard('before_budget')
        old=[u for u in self.resources.get_usage_history(request.subject_id) if u.session_id==request.session_id]
        if old:
            if len(old)!=1 or old[0].session_type is not ResourceSessionType.THINKING or old[0].model_name!=request.model_name:
                raise RuntimeBoundaryError('RUNTIME_BUDGET_BINDING')
            # A saved reservation is not a new budget window. Native recovery
            # refuses an uncertain prior ThinkSession instead of replaying it.
            state=self.resources.get_resource_state(request.subject_id)
            return TokenBudget(state.token_budget,max(state.token_remaining,old[0].estimated_tokens),old[0].estimated_tokens,request.depth)
        return self.resources.allocate(request)


class RuntimeThinkingBoundary:
    """No arbitrary Provider diagnostic enters original ThinkSession errors."""
    def __init__(self,provider):self.provider=provider;self.provider_id=provider.provider_id
    def think(self,perception,budget):
        try:return self.provider.think(perception,budget)
        except Exception:raise RuntimeBoundaryError('RUNTIME_THINKING_PROVIDER_UNAVAILABLE') from None


class RuntimeSchedulerResources:
    def __init__(self,work):self.work=work
    def preview(self,request):
        work=self.work
        task=next((t for t in work.scheduler.list_tasks(subject_id=work.subject_id,environment=work.environment)
                   if stable_attempt_id(t.task_id,t.attempt_count+1)==request.session_id),None)
        if task is None:raise RuntimeBoundaryError('RUNTIME_RESOURCE_TASK_BINDING')
        cognition=task.task_id.startswith('cognition:')
        expected=replace(request,estimated_tokens=320 if cognition else 0,estimated_compute=2 if cognition else 1)
        result=work.resources.preview(expected)
        if cognition and work.availability() is not True:
            return replace(result,allowed=False,defer=True,allocated_tokens=0,allocated_compute=0)
        return result


class RuntimeCognition:
    def __init__(self,*,core,awakening,perception,thinking,action,resources,cycle_id,clock,policy,
                 available_permissions,resource_limits,availability=lambda:True,fault=None,binding=None,
                 expression_confirmation=None):
        self.core=core;self.awakening=awakening;self.thinking=thinking;self.resources=resources
        self.subject_id=core.subject_id;self.environment=core.environment;self.clock=clock;self.policy=policy
        self.cycle_id=cycle_id;self.scheduler=None;self.guard=lambda stage:None
        self.availability=availability;self.fault=fault or (lambda stage:None)
        self.binding=binding;self.expression_confirmation=expression_confirmation;self.expression_trace=None
        if core.mind is None:raise RuntimeBoundaryError('RUNTIME_CONTINUOUS_MIND_REQUIRED')
        if awakening.get_cycle(cycle_id).subject_id!=self.subject_id:raise RuntimeBoundaryError('RUNTIME_CYCLE_BINDING')
        self.native=WakePerceptionThinkingActionService(awakening,perception,thinking,action,core.subject_states,
            available_permissions=available_permissions,resource_limits=resource_limits,clock=clock,continuity_core=core,
            runtime_guard=lambda stage:self.guard(stage),native_dispatch=True,fault=lambda stage:self.fault(stage),
            native_expression=self._expression)
        thinking._token_budgets=RuntimeBudgets(resources,lambda stage:self.guard(stage))
        thinking._provider=RuntimeThinkingBoundary(thinking._provider)
        self.wake=ResourceAwareWakeScheduler(awakening,resources,clock=clock)

    def _expression(self,wake,thinking,action):
        policy=self.core.expression_policy
        if policy is None:return
        if self.binding is None:raise RuntimeBoundaryError('RUNTIME_EXPRESSION_BINDING_REQUIRED')
        p=thinking.perception;s=thinking.session
        operation=SimpleNamespace(subject_id=self.subject_id,operation_id='native:'+wake.session_id,
            request_id='native:'+wake.session_id,request_hash=digest(p.to_dict()),
            binding_id=self.binding.binding_id,binding_version=self.binding.binding_version,input_revision=p.source_revision,
            domain_progress=SimpleNamespace(perception=p,think_session_id=s.think_id,thinking_result_id=s.result.result_id,action=action))
        if self.expression_confirmation is not None:
            self.expression_confirmation(policy.authorization_request(self.core,operation,p.continuity_context,thinking,action))
        self.guard('before_native_expression')
        policy.compose(self.core,operation,thinking,action)
        # Trace contains modes, hashes and reasons only, never the private body.
        self.expression_trace=policy.last_trace

    def needs(self,at):
        state=self.core.subject_states.require_active(self.subject_id,self.environment)
        mind=MindState.from_dict(state.intentions.dynamic_mind) if state.intentions.dynamic_mind is not None else MindState.create(self.subject_id,self.environment,state.temporal.created_at)
        needs=[]
        # Pure P14 projection tells whether elapsed internal needs changed enough
        # to warrant cognition. Scheduler receives only kind/identity/due/priority.
        if at>=mind.updated_at+timedelta(seconds=self.policy.minimum_spacing_seconds):
            proposal=self.core.mind.dynamics.advance(mind,at=at)
            delta=max(abs(proposal.state.drives[k]-mind.drives[k]) for k in mind.drives)
            if delta>=self.policy.need_delta:
                basis=[self.subject_id,self.environment,state.revision,digest(mind.to_dict())]
                needs.append(RuntimeNeed('cognition:'+digest(basis)[7:],'cognition',mind.updated_at+timedelta(seconds=self.policy.minimum_spacing_seconds),10))
        known={m.memory_id for m in self.core.memory.list_memories(self.subject_id,include_inactive=True)}
        missing=[e for e in self.core.timeline.rebuild(self.subject_id).entries if 'memory:'+e.event.event_id not in known and e.status.value=='active']
        if missing:
            entry=min(missing,key=lambda e:(e.event.recorded_at,e.event.event_id))
            needs.append(RuntimeNeed(self._memory_identity(entry.event.event_id),'maintenance',entry.event.recorded_at,20))
        return tuple(needs)

    def _memory_identity(self,event_id):
        return 'maintenance:'+digest([self.subject_id,self.environment,event_id])[7:]

    def _bind(self,request):
        if (request.subject_id,request.environment,request.cycle_id)!=(self.subject_id,self.environment,self.cycle_id):
            raise RuntimeBoundaryError('RUNTIME_NOTIFICATION_BINDING')
        task=self.scheduler.get(request.task_id,subject_id=self.subject_id,environment=self.environment)
        if (task.last_attempt_id,task.cycle_id,task.wake_reason,task.source_event_id)!=(request.attempt_id,request.cycle_id,request.wake_reason,request.source_event_id):
            raise RuntimeBoundaryError('RUNTIME_TASK_ATTEMPT_BINDING')
        if self.awakening.get_cycle(self.cycle_id).subject_id!=self.subject_id:raise RuntimeBoundaryError('RUNTIME_CYCLE_BINDING')
        return task

    def _receipt(self,request,status):
        return NotificationReceipt('runtime-receipt:'+digest([request.task_id,request.attempt_id,status.value])[7:],
            request.task_id,request.attempt_id,self.subject_id,self.environment,status,self.clock(),'NATIVE_FACT_VERIFIED' if status is NotificationStatus.DELIVERED else 'NATIVE_FACT_UNCONFIRMED')

    @staticmethod
    def wake_id(task_id):return str(uuid5(NAMESPACE_URL,'p18-wake|'+task_id))

    def _session(self,request):
        identity=str(uuid5(NAMESPACE_URL,'p14-think|'+self.wake_id(request.task_id)))
        try:return self.thinking.get_session(self.subject_id,identity)
        except StateNotFoundError:return None

    def _maintenance(self,request,*,query=False):
        # Actual original Memory facts prove completion, not absence from a
        # currently recomputed pending set. Revocation cannot fake completion.
        entry=next((e for e in self.core.timeline.rebuild(self.subject_id).entries
                    if self._memory_identity(e.event.event_id)==request.task_id),None)
        if entry is None:return self._receipt(request,NotificationStatus.UNKNOWN)
        memories=self.core.memory.list_memories(self.subject_id,include_inactive=True)
        done=any(m.memory_id=='memory:'+entry.event.event_id and
                 entry.event.event_id in m.source_event_ids and 'event:'+entry.event.event_id in m.root_evidence_ids for m in memories)
        if done:return self._receipt(request,NotificationStatus.DELIVERED)
        if query:return self._receipt(request,NotificationStatus.NOT_DELIVERED)
        if entry.status.value!='active':raise RuntimeDeferred('RUNTIME_MEMORY_SOURCE_INACTIVE')
        self.guard('before_memory_resources')
        session='memory:'+request.task_id
        if not any(u.session_id==session for u in self.resources.get_usage_history(self.subject_id)):
            allocation=self.resources.request_memory(self.subject_id,session,reason='Bounded native C1 memory maintenance.',estimated_tokens=0,estimated_compute=1)
            if allocation.decision.defer:return self._receipt(request,NotificationStatus.NOT_DELIVERED)
        self.guard('before_memory_write')
        self.core._consolidate_events()
        return self._maintenance(request,query=True)

    def dispatch(self,request):
        self._bind(request)
        if request.task_id.startswith('maintenance:'):return self._maintenance(request)
        self.guard('before_native_wake')
        session_id=self.wake_id(request.task_id)
        detail='Native P18 internal computation opportunity.'
        try:saved=self.awakening.get_session(self.subject_id,session_id)
        except StateNotFoundError:saved=None
        if saved is None:
            usage=[u for u in self.resources.get_usage_history(self.subject_id) if u.session_id==session_id]
            if usage:
                if len(usage)!=1 or usage[0].session_type is not ResourceSessionType.OTHER:raise RuntimeBoundaryError('RUNTIME_WAKE_RESERVATION_BINDING')
                self.guard('after_wake_resources')
                self.awakening.wake_manual(self.cycle_id,detail=detail,session_id=session_id,preserve_recovery_context=True)
            else:
                wake=self.wake.wake_manual(self.cycle_id,detail=detail,session_id=session_id,
                    preserve_recovery_context=True,before_dispatch=lambda stage:self.guard(stage))
                if wake.deferred:return self._receipt(request,NotificationStatus.NOT_DELIVERED)
        return self._continue(request)

    def _continue(self,request):
        result=self.native.wake_manual(self.cycle_id,detail='Native P18 internal computation opportunity.',
            session_id=self.wake_id(request.task_id),depth=ThinkingDepth.LOW)
        if result.thinking is not None:
            session=result.thinking.session
            usage=[u for u in self.resources.get_usage_history(self.subject_id) if u.session_id==session.think_id]
            if usage and usage[0].actual_tokens is None:
                self.resources.record_actual_usage(self.subject_id,session.think_id,usage[0].estimated_tokens)
        self.fault('before_runtime_receipt')
        return self._receipt(request,NotificationStatus.DELIVERED)

    def query(self,request):
        task=self._bind(request)
        if request.task_id.startswith('maintenance:'):return self._maintenance(request,query=True)
        session=self._session(request)
        if session is None:return self._receipt(request,NotificationStatus.NOT_DELIVERED)
        if not session.completed_successfully:
            # A lost/incomplete provider execution is never proof of nonexecution.
            return self._receipt(request,NotificationStatus.UNKNOWN)
        if task.cancel_requested_at is not None and session.state_update_id is None:
            return self._receipt(request,NotificationStatus.UNKNOWN)
        try:return self._continue(request)
        except Exception:return self._receipt(request,NotificationStatus.UNKNOWN)
