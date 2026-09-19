"""Explicit isolated TEST composition for the continuous Engine host.

Initialization alone may create a synthetic subject. Reopen/start never reset
its state, budgets, stop decision, requests or effects. No production defaults.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError, RuntimePolicy, RuntimePrincipal, RuntimeDeliveryPolicy
from continuity_engine.domain.thinking import ThinkingResult
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.services.continuity_core_runtime import build_continuity_core
from continuity_engine.services.resource_manager import ResourceManager
from continuity_engine.services.runtime_cognition import RuntimeCognition, RuntimeSchedulerResources
from continuity_engine.services.persistent_runtime_service import PersistentRuntimeService
from continuity_engine.services.scheduler_service import SchedulerService
from continuity_engine.services.expression_policy_service import ExpressionPolicyService
from continuity_engine.services.runtime_ports import RuntimeWorldBoundary
from continuity_engine.storage.json_runtime_repository import JsonRuntimeRepository, safe_root
from continuity_engine.storage.json_resource_repository import JsonResourceRepository
from continuity_engine.storage.json_scheduler_repository import JsonSchedulerRepository
from continuity_engine.interfaces.local_integration_app import build_local_integration_app
from .p17_execution_fixture import P17Fixture, _Confirmation
from .p09_core_fixture import CoreClaims
from .interaction import SandboxContractValidator, SandboxFirstRoundResultFactory
from .persistence import atomic_write_json, read_json, SandboxActionRepository
from .sandbox import P01SandboxManager


class TestClock:
    """Explicit synthetic time; advancing rate is only a TEST controller option."""
    def __init__(self,path,frozen):self.path=path;self.frozen=frozen
    @property
    def _path(self):return self.frozen._path
    def now(self):
        d=read_json(self.path)
        elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(d['real_anchor'])).total_seconds()
        return self.frozen.now()+timedelta(seconds=elapsed*d['test_clock_rate'])
    def advance(self,seconds):self.frozen.advance(seconds if isinstance(seconds,timedelta) else timedelta(seconds=seconds))


class TestIdentities:
    def __init__(self,subject):self.subject=subject;self.allowed=True
    def resolve(self,handle):
        if self.allowed and handle=='p18-test-owner':
            return RuntimePrincipal('isolated-test-owner',self.subject,'TEST',frozenset({'PAUSE','RESUME','STOP'}))
        return None


class TestThinking:
    provider_id='p18-native-test-thinking-v1'
    def __init__(self,fixture):self.fixture=fixture;self.calls=0;self.inputs=[];self.hook=None
    def think(self,perception,budget):
        self.calls+=1;self.inputs.append(perception)
        if self.hook:self.hook()
        mode=self.fixture.mode
        return ThinkingResult.create(provider_id=self.provider_id,
            result_summary='Reflect on current internal needs and retained evidence.',
            rationale_summary='Explicit TEST subject cognition through composed current sources.',
            generated_new_thought=True,update_subject_state=False,
            request_more_memory=False,should_wait=mode=='silence',
            suggest_future_user_contact=mode=='contact',token_budget=budget)


class P18Fixture(P17Fixture):
    def __init__(self,root,*,mode='silence',tokens=100000,need_delta=0.02,test_clock_rate=0,
                 initialize=True,policy=None,delivery_policy=None):
        self.root=safe_root(root)
        self.config_path=self.root/'p18-test-profile.json'
        self._p18_ready=False;self.online=True;self.fault=lambda stage:None;self._commands={}
        exists=self.config_path.exists()
        if not exists and not initialize:raise RuntimeBoundaryError('RUNTIME_TEST_PROFILE_MISSING')
        if exists:
            d=read_json(self.config_path)
            if (d.get('version'),d.get('environment'))!=('p18-isolated-v1','TEST'):
                raise RuntimeBoundaryError('RUNTIME_TEST_PROFILE_INVALID')
            # Fail before opening any mutable runtime if the host checkpoint is
            # missing; reopening must never manufacture an initial RUNNING state.
            manager=P01SandboxManager(self.root/'s',formal_data_roots=(self.root/'formal-canary',))
            runtime=manager.open_runtime(d['sandbox_id'])
            JsonRuntimeRepository(runtime.data_root,subject_id=runtime.descriptor.subject_id,environment='TEST').load()
            super().__init__(self.root,mode=d['mode'],runtime=runtime,manager=manager)
        else:
            if self.root.exists() and any(self.root.iterdir()):raise RuntimeBoundaryError('RUNTIME_TEST_ROOT_NOT_EMPTY')
            if mode not in {'silence','contact','reflect'}:raise RuntimeBoundaryError('RUNTIME_TEST_MODE_INVALID')
            if type(test_clock_rate) not in (int,float) or not 0<=test_clock_rate<=3600:raise RuntimeBoundaryError('RUNTIME_TEST_CLOCK_INVALID')
            super().__init__(self.root,mode=mode)
            d=dict(version='p18-isolated-v1',environment='TEST',sandbox_id=self.runtime.descriptor.sandbox_id,
                mode=mode,test_clock_rate=test_clock_rate,real_anchor=datetime.now(timezone.utc).isoformat(),
                policy=asdict(policy or RuntimePolicy(need_delta=need_delta)),
                delivery_policy=asdict(delivery_policy or RuntimeDeliveryPolicy(configured=mode!='silence')))
            atomic_write_json(self.config_path,d)
        self.clock=TestClock(self.config_path,self.runtime.clock)
        self.runtime.clock=self.clock
        self.policy=RuntimePolicy(**d['policy'])
        self.delivery_policy=RuntimeDeliveryPolicy(**d['delivery_policy'])
        self.store=JsonRuntimeRepository(self.runtime.data_root,subject_id=self.state.subject_id,environment='TEST')
        if not exists:self.store.initialize()
        self._p18_ready=True
        self.reopen()
        if not exists:self.grant_test_budget(tokens)

    def reopen(self):
        if not self._p18_ready:return super().reopen()
        self.fake.clock=self.clock.now
        self.base.adapter.clock=self.clock.now
        self.provider=TestThinking(self)
        def factory(**kwargs):
            self.core=build_continuity_core(**kwargs,environment='TEST',constraints=self.constraints,
                capabilities=tuple(b for b in self.base.core.capabilities if b.capability in {'silence','expression.emit'}),
                claim_resolver=CoreClaims(),permission_policy=self.base.permission,execution=self.execution,
                dynamic_mind=True,subject_growth=True,expression_policy=ExpressionPolicyService(),context_budget=ContextBudget(token_limit=2048))
            self.core.policy=_Confirmation(self.core.policy,self)
            return self.core
        self.app=build_local_integration_app(self.runtime.data_root,clock=self.clock.now,thinking_provider=self.provider,
            continuity_core_factory=factory,contract_validator=SandboxContractValidator(),result_factory=SandboxFirstRoundResultFactory(),
            available_permissions=('subject_state:update','memory:request','user:contact','test:execute','action:silence','expression:emit'))
        original=self.app.adapter._service
        original._action._repository=SandboxActionRepository(self.runtime.data_root)
        self.resources=ResourceManager(JsonResourceRepository(self.runtime.data_root),clock=self.clock.now)
        self.work=RuntimeCognition(core=self.core,awakening=original._awakening,perception=original._perception,
            thinking=original._thinking,action=original._action,resources=self.resources,cycle_id=self.app.binding.cycle_id,
            clock=self.clock.now,policy=self.policy,available_permissions=original._available_permissions,
            resource_limits=original._resource_limits,availability=lambda:self.online,fault=lambda stage:self.fault(stage),
            binding=self.app.binding,expression_confirmation=lambda request:self.constraints.confirmed_ids.add(request.idempotency_key))
        # TEST-only structured fault evidence survives the child via stderr.
        # No exception message, repr, input body or secret is serialized.
        native_continue = self.work._continue
        def diagnosed_continue(request):
            try:
                return native_continue(request)
            except BaseException as exc:
                import json, sys, traceback
                chain = []; seen = set(); cursor = exc
                engine = Path(__file__).resolve().parents[1]
                while cursor is not None and id(cursor) not in seen:
                    seen.add(id(cursor))
                    frames = []
                    for frame in traceback.extract_tb(cursor.__traceback__):
                        path = Path(frame.filename).resolve()
                        if path.is_relative_to(engine):
                            frames.append(dict(file=path.relative_to(engine).as_posix(),
                                               line=frame.lineno, function=frame.name))
                    chain.append(dict(frames=frames, code='TEST_NATIVE_EXCEPTION'))
                    cursor = cursor.__cause__ if cursor.__suppress_context__ else cursor.__cause__ or cursor.__context__
                print(json.dumps(dict(stage='native-exception-before-cleanup',task_id=request.task_id,
                    attempt_id=request.attempt_id,chain=chain)), file=sys.stderr, flush=True)
                raise
        self.work._continue = diagnosed_continue
        self.scheduler=SchedulerService(JsonSchedulerRepository(self.runtime.data_root),self.work,
            RuntimeSchedulerResources(self.work),clock=self.clock.now,retry_base_seconds=5,
            subject_states=original._subject_states,resource_scan_limit=128)
        self.work.scheduler=self.scheduler
        self.identities=TestIdentities(self.state.subject_id)
        self.host=PersistentRuntimeService(self.store,self.scheduler,self.work,original._subject_states,self.identities,
            clock=self.clock.now,policy=self.policy)
        def last_delivery(request):
            from continuity_engine.domain.action_capability import ActionReceipt
            from continuity_engine.domain.capability import parse_capability_datetime
            # FakeWorldStore.load validates the original atomic effects/receipts.
            receipts=[ActionReceipt.from_dict(row['receipt']) for row in self.fake.store.load()['facts']]
            times=[parse_capability_datetime(r.completed_at) for r in receipts if r.effect_count
                   and r.capability_request_id!=request.capability_request_id]
            return max(times) if times else None
        self.execution.boundary=RuntimeWorldBoundary(self.boundary,guard=self.host.guard,clock=self.clock.now,
            delivery_policy=self.delivery_policy,last_delivery=last_delivery)
        return self.app

    def advance(self,seconds):self.clock.advance(seconds)

    def control(self,operation,command_id=None,handle='p18-test-owner'):
        command_id=command_id or 'control:'+uuid4().hex
        expected=self._commands.setdefault(command_id,self.store.load()['revision'])
        return self.host.control(operation,command_id=command_id,expected_revision=expected,handle=handle)

    def grant_test_budget(self,total):
        """Explicit TEST policy change, retaining all prior usage and decisions."""
        state=self.resources.get_resource_state(self.state.subject_id)
        old=state.revision
        state.token_budget=total;state.token_remaining=max(0,total-state.token_used)
        state.revision+=1;state.updated_at=self.clock.now();state.__post_init__()
        self.resources._repository.save_state(state,expected_revision=old)
