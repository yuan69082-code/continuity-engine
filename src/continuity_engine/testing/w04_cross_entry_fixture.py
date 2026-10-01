"""Explicit TEST accounts and apps. Thinking derives its output from real input.

This fixture proves wiring only; it makes no natural-language or real-platform
quality claim. Native simulation receipts come from the existing device port.
"""
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
import json

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.cross_entry import EntryBinding, EntryMessage
from continuity_engine.domain.environment_access import Ability, AttachmentKind, AttachmentUse
from continuity_engine.domain.execution import WorldCapability, BlastRadius
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.domain.integration_hashing import calculate_content_hash
from continuity_engine.domain.thinking import ThinkingResult
from continuity_engine.interfaces.local_integration_app import build_local_integration_app
from continuity_engine.services.continuity_core_runtime import build_continuity_core
from continuity_engine.services.continuity_core_service import ContinuityCoreGates, CoreDecisionPolicy
from continuity_engine.services.cross_entry_service import CrossEntryService, EntryDecisionPolicy
from continuity_engine.services.device_operation_service import DeviceOperationService
from continuity_engine.services.execution_service import ExecutionService
from continuity_engine.services.expression_policy_service import ExpressionPolicyService
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from .p09_core_fixture import CoreClaims
from .p17_execution_fixture import _Confirmation
from .p13_expression_fixture import FakePresentation
from .interaction import SandboxContractValidator, SandboxFirstRoundResultFactory
from .w04_device_fixture import W04DeviceFixture, SimulatedDevicePort


class EntryThinking:
    provider_id = 'w04-entry-test-input-derived-v1'

    def __init__(self):
        self.inputs = []
        self.before_return = None

    def think(self, perception, budget):
        self.inputs.append(perception)
        fragments = perception.continuity_context.composition.snapshot.fragments
        current = next((json.loads(f.content) for f in fragments if f.source_id == 'engine.current-input'), None)
        message = current['entry_provenance'] if current else None
        text = current['content'] if current else None
        items = []
        for fragment in fragments:
            if fragment.source_id == 'engine.subject-state' and fragment.stable_source_id.endswith(':continuity'):
                projection = json.loads(fragment.content).get('item_records', [])
                items = projection.get('next', []) if isinstance(projection, dict) else projection
        intent = None
        if current is None:
            from continuity_engine.domain.cross_entry import ContactIntent
            options = next((json.loads(f.content).get('message_entry_options', []) for f in fragments
                if f.source_id == 'engine.subject-state' and f.stable_source_id.endswith(':identity')), [])
            # This TEST provider decides from actual composed matter and entry
            # data. Scheduler supplies only an opportunity, no contact command.
            topic = next((item for item in items if item['status'] == 'WAITING'), None)
            candidates = [option for option in options if option['can_initiate']]
            target = candidates[-1] if candidates else None
            pursue = topic is not None and target is not None
            intent = ContactIntent(topic['item_id'], target['entry_id']).to_dict() if pursue else None
            body = topic['title'] if pursue else '当前没有需要联系的未答事项，继续内部思考。'
        else:
            topic = next((item for item in items if item['item_id'] == message['item_id']), None)
            ambiguous = topic is None and len(items) > 1 and text == '那件事怎么样了？'
            pursue = text.endswith(('？', '?')) and not ambiguous
            body = ('你指的是哪件事：' + '；'.join(item['title'] for item in items) if ambiguous else
                text if pursue else (f"关于{topic['title']}，收到：{text}" if topic else f'收到：{text}'))
        result = ThinkingResult.create(provider_id=self.provider_id, result_summary=body,
            rationale_summary='TEST decision derived from actual current input and selected topic; not semantic certification',
            generated_new_thought=True, update_subject_state=False, request_more_memory=False,
            suggest_future_user_contact=pursue, should_wait=current is None and not pursue, token_budget=budget,
            expression_mode='PURSUE' if pursue else ('SILENCE' if current is None else 'RESPOND'),
            contact_intent=intent)
        if self.before_return:
            self.before_return()
        return result


class W04EntryFixture:
    def __init__(self, root, *, runtime=None, manager=None):
        self.base = W04DeviceFixture(Path(root), runtime=runtime, manager=manager)
        self.root = Path(root)
        self.runtime, self.manager = self.base.runtime, self.base.manager
        self.access, self.repo = self.base.access, self.base.repo
        self.constraints, self.broker, self.boundary = self.base.constraints, self.base.broker, self.base.boundary
        self.outbox, self.expiry = self.base.outbox, self.base.expiry
        self.configure_allowed = self.contact_allowed = self.read_allowed = True
        self.api_available = True
        self.native_mode = False
        self.presentation = FakePresentation()
        self.confirmed_expressions = set()
        self.ports, self.devices, self.entry_routes = {}, {}, {}
        self.entries = CrossEntryService(access=self.access, clock=self.runtime.clock.now,
            authorize_configuration=lambda binding: self.configure_allowed,
            authorize_contact=lambda binding: self.contact_allowed,
            authorize_read=lambda binding: self.read_allowed)
        all_routes = list(self.base.routes)
        for name in ('A', 'B'):
            entry = 'entry:' + name
            software = 'software:' + name
            capabilities = tuple('device.message.send.' + route + ':' + digest(software)[7:23] for route in ('api', 'ui'))
            query_capability = 'device.query:' + digest(software)[7:23]
            port = SimulatedDevicePort(self.runtime.data_root / 'worlds' / ('entry-' + name),
                subject=self.state.subject_id, clock=self.runtime.clock.now)
            port.adapter_id = 'simulated-entry-' + name
            device = DeviceOperationService(access=self.access, port=port, clock=self.runtime.clock.now,
                subject_states=self.runtime.subject_states, authorize_history=lambda *a, **kw: self.read_allowed)
            self.ports[entry], self.devices[entry], self.entry_routes[entry] = port, device, capabilities
            all_routes.extend(WorldCapability(cap, 'v1', self.state.subject_id, 'TEST', 'TEST', software,
                port.adapter_id, 'credential:p17:test', cost=1, max_output_bytes=32768) for cap in (*capabilities, query_capability))
            existing = self.repo.load()
            if not any(row['attachment_id'] == 'in:' + name for row in existing['attachments']):
                original = self.base.attachment()
                now = format_contract_datetime(self.runtime.clock.now())
                common = dict(channel_id='channel:' + name, software_id=software, device_id='device:' + name,
                    account_id='subject-account:' + name, session_id='session:' + name)
                ingress = replace(original, **common, attachment_id='in:' + name, kind=AttachmentKind.MESSAGE_INGRESS,
                    purposes=('entry.read',), read_scopes=('entry:read',), abilities=())
                outbound = replace(original, **common, attachment_id='out:' + name,
                    abilities=tuple(Ability(cap, 'OUTPUT', None, None, None, None, now, original.expires_at) for cap in (*capabilities, query_capability)))
                for attachment in (ingress, outbound):
                    self.repo.register(attachment, expected_revision=self.repo.load()['revision'])
                def use(a, purpose, scope):
                    return AttachmentUse(**{k: getattr(a, k) for k in AttachmentUse.__dataclass_fields__ if k not in {'purpose', 'scope'}}, purpose=purpose, scope=scope)
                binding = EntryBinding(entry, use(ingress, 'entry.read', 'entry:read'), self.base.request()['identity']['userId'],
                    'user-account:' + name, 'subject-account:' + name, 'user-account:' + name, 'PRIVATE',
                    ('entry:A', 'entry:B'), True, True, True, now, ingress.expires_at,
                    send_use=use(outbound, 'device.act', 'device:read'))
                self.entries.configure(binding, expected_revision=self.repo.load()['revision'])
        self.entries.devices, self.entries.routes = self.devices, self.entry_routes
        self.entries.route_available = lambda entry, route: self.api_available or '.ui:' in route
        self.boundary.authorize = lambda route, request, **kw: self.boundary.allowed and request.step.target == route.asset
        def capacity(route, request, limits):
            if self.boundary.hook:
                self.boundary.hook()
            port = next((p for p in self.ports.values() if p.adapter_id == request.adapter_id), self.base.fake)
            if not self.boundary.resource_ready:
                return False
            projected, _ = port.projected_document(request, port.store.load())
            return (projected['credits'] <= limits.credits and len(projected['facts']) <= limits.requests
                    and len(projected['effects']) <= limits.messages and port.projected_size(request, projected) <= limits.storage_bytes)
        self.boundary.capacity = capacity
        adapters = {device.adapter_id: device for device in self.devices.values()}
        adapters[self.base.device.adapter_id] = self.base.device
        self.execution = ExecutionService(self.outbox, routes=tuple(all_routes), adapters=adapters,
            boundary=self.boundary, broker=self.broker, limits=BlastRadius(requests=64, credits=64, messages=64, storage_bytes=2000000))
        self.reopen()

    @property
    def state(self):
        return self.runtime.subject_states.load(self.runtime.descriptor.subject_id)

    def reopen(self):
        self.provider = EntryThinking()
        def factory(**kwargs):
            self.core = build_continuity_core(**kwargs, environment='TEST', constraints=self.constraints,
                capabilities=self.base.base.core.capabilities,
                claim_resolver=CoreClaims(), permission_policy=self.base.base.permission,
                gates=ContinuityCoreGates(input_processing=True, automatic_recall=True, essential_core=True),
                context_budget=ContextBudget(token_limit=2048), execution=self.execution,
                external_capabilities=getattr(self, 'tool_fixture', None).tools.external if hasattr(self, 'tool_fixture') else None,
                entry_continuity=self.entries, policy=EntryDecisionPolicy(self.entries, CoreDecisionPolicy()),
                dynamic_mind=self.native_mode,
                expression_policy=ExpressionPolicyService(self.presentation))
            self.core.policy = _Confirmation(self.core.policy, self)
            choose = self.core.policy.choose
            def confirmed(operation, context, thinking, action):
                if not operation.request_id.startswith('native:') and operation.operation_id not in self.confirmed_expressions:
                    grant = self.core.expression_policy.authorization_request(self.core, operation, context, thinking, action)
                    self.constraints.confirmed_ids.add(grant.idempotency_key)
                    self.confirmed_expressions.add(operation.operation_id)
                return choose(operation, context, thinking, action)
            self.core.policy.choose = confirmed
            return self.core
        self.app = build_local_integration_app(self.runtime.data_root, clock=self.runtime.clock.now,
            thinking_provider=self.provider, continuity_core_factory=factory, contract_validator=SandboxContractValidator(),
            result_factory=SandboxFirstRoundResultFactory(), available_permissions=(
                'subject_state:update', 'memory:request', 'user:contact', 'expression:emit', 'action:silence', 'test:execute'))
        self.entries.interaction = self.app.adapter.service
        self.app.adapter.service._environment_access = self.access
        self.entries.native_thinking = self.app.adapter.service._thinking
        if hasattr(self, 'tool_fixture'):
            tool = self.tool_fixture
            tool.core, tool.app, tool.execution = self.core, self.app, self.execution
        return self.app

    def bind_tools(self, tool):
        """Compose existing adapters in ONE core for causal package tests."""
        if tool.state.subject_id != self.state.subject_id or tool.runtime.data_root != self.runtime.data_root:
            raise AssertionError('TEST package identity mismatch')
        self.tool_fixture = tool
        tool.constraints = self.constraints
        tool.device = self.base.device
        class ConnectionGuard:
            def observe(_, use):
                if use.attachment_id not in {'ui:attachment', 'body:attachment'}:
                    tool.tools.observe(use)
            def __call__(_, request, *, purpose):
                from continuity_engine.domain.device_operation import DeviceCommand
                use=DeviceCommand.from_dict(request.step.input_payload).observation.use
                if use.attachment_id not in {'ui:attachment', 'body:attachment'}:
                    tool.tools(request, purpose=purpose)
        self.base.device.connection_guard = ConnectionGuard()
        old_capacity = self.boundary.capacity
        self.boundary.capacity = lambda route, request, limits: True if route.capability_ref.startswith('tool.') else old_capacity(route, request, limits)
        routes = (*self.execution.routes.values(), *(r for r in tool.routes if r.capability_ref.startswith('tool.')))
        self.execution = ExecutionService(self.outbox, routes=routes,
            adapters={**{d.adapter_id:d for d in self.devices.values()}, self.base.device.adapter_id:self.base.device,
                tool.tools.adapter_id:tool.tools}, boundary=self.boundary, broker=self.broker,
            limits=BlastRadius(requests=64, credits=64, messages=64, storage_bytes=2000000))
        tool.tools.execution = self.execution
        self.reopen()

    def start_native(self):
        from continuity_engine.domain.persistent_runtime import RuntimePolicy, RuntimeDeliveryPolicy
        from continuity_engine.services.runtime_cognition import RuntimeCognition, RuntimeSchedulerResources
        from continuity_engine.services.resource_manager import ResourceManager
        from continuity_engine.services.persistent_runtime_service import PersistentRuntimeService
        from continuity_engine.services.scheduler_service import SchedulerService
        from continuity_engine.storage.json_resource_repository import JsonResourceRepository
        from continuity_engine.storage.json_runtime_repository import JsonRuntimeRepository
        from continuity_engine.storage.json_scheduler_repository import JsonSchedulerRepository
        from .p18_runtime_fixture import TestIdentities
        self.native_mode = True
        self.reopen()
        original = self.app.adapter.service
        self.resources = ResourceManager(JsonResourceRepository(self.runtime.data_root), clock=self.runtime.clock.now)
        self.runtime_policy = RuntimePolicy()
        self.native_work = RuntimeCognition(core=self.core, awakening=original._awakening,
            perception=original._perception, thinking=original._thinking, action=original._action,
            resources=self.resources, cycle_id=self.app.binding.cycle_id, clock=self.runtime.clock.now,
            policy=self.runtime_policy, available_permissions=original._available_permissions,
            resource_limits=original._resource_limits, binding=self.app.binding,
            expression_confirmation=lambda request:self.constraints.confirmed_ids.add(request.idempotency_key))
        native_continue = self.native_work._continue
        def diagnosed(request):
            try:
                return native_continue(request)
            except Exception as exc:
                import sys, traceback
                from .p18_persistence_diagnostics import exception_chain
                print(json.dumps({'stage': 'w04-native-before-cleanup', 'task_id': request.task_id,
                    'attempt_id': request.attempt_id, 'chain': exception_chain(exc),
                    'recall': {k:v for k,v in self.core.last_trace.get('recall', {}).items()
                        if k in {'status','stop_reason','elapsed_ms','retrieved_count','model_calls','external_calls'}}}), file=sys.stderr)
                raise
        self.native_work._continue = diagnosed
        self.scheduler = SchedulerService(JsonSchedulerRepository(self.runtime.data_root), self.native_work,
            RuntimeSchedulerResources(self.native_work), clock=self.runtime.clock.now,
            retry_base_seconds=5, subject_states=self.core.subject_states, resource_scan_limit=128)
        self.native_work.scheduler = self.scheduler
        self.runtime_store = JsonRuntimeRepository(self.runtime.data_root,
            subject_id=self.state.subject_id, environment='TEST')
        self.runtime_store.initialize()
        self.host = PersistentRuntimeService(self.runtime_store, self.scheduler, self.native_work,
            self.core.subject_states, TestIdentities(self.state.subject_id),
            clock=self.runtime.clock.now, policy=self.runtime_policy)
        def current_native(route, request, *, purpose):
            if purpose == 'execute' and request.choice.decision_id.startswith('c1:'):
                link = (request.step.input_payload or {}).get('entry_delivery')
                if link and link['request_id'].startswith('native:'):
                    self.host.guard('before_native_entry_delivery')
            return self.boundary.allowed and request.step.target == route.asset
        self.boundary.authorize = current_native
        return self.host

    def continue_native(self):
        from continuity_engine.domain.scheduling import SchedulerTaskState
        if not self.native_mode:
            self.start_native()
        # Let original drive dynamics accumulate an actual need; do not lower
        # the production need threshold or manufacture a Scheduler intention.
        self.runtime.clock.advance(timedelta(minutes=15))
        before = {task.task_id for task in self.scheduler.list_tasks(subject_id=self.state.subject_id, environment='TEST')}
        with self.host.running():
            # Bounded TEST observation controller; not an Engine lifetime rule.
            for _ in range(8):
                self.host.tick()
                tasks = self.scheduler.list_tasks(subject_id=self.state.subject_id, environment='TEST')
                done = next((task for task in tasks if task.task_id not in before
                    and task.task_id.startswith('cognition:') and task.state is SchedulerTaskState.COMPLETED), None)
                if done:
                    return 'native:' + self.native_work.wake_id(done.task_id)
                from continuity_engine.domain.persistent_runtime import parse
                next_check = self.host.query()['next_check_at']
                delay = max(1, (parse(next_check) - self.runtime.clock.now()).total_seconds()) if next_check else 1
                self.runtime.clock.advance(timedelta(seconds=delay))
        raise AssertionError('TEST_NATIVE_CONTINUATION_NOT_COMPLETED:' + self.host.query()['activity'])

    def message(self, text, *, entry='entry:A', **changes):
        request = self.base.request()
        fact = request['platformFactPackage']['facts'][0]
        fact['content'], fact['contentHash'] = text, calculate_content_hash(text)
        request['requestHash'] = calculate_request_hash(request)
        binding = self.entries.binding(entry)
        now = format_contract_datetime(self.runtime.clock.now())
        role = changes.get('role', 'USER')
        message = EntryMessage(**{**dict(entry_id=entry, external_message_id=request['conversation']['messageId'],
            sender_account=binding.user_account if role == 'USER' else binding.subject_account,
            recipient_account=binding.subject_account if role == 'USER' else binding.recipient_account,
            audience=binding.audience, occurred_at=now, observed_at=now, recorded_at=now), **changes})
        return request, message

    def submit(self, text, **changes):
        self.last_request, self.last_message = self.message(text, **changes)
        return self.entries.receive(self.last_request, self.last_message)

    def advance(self):
        self.runtime.clock.advance(timedelta(seconds=1))

    def configure(self, entry='entry:B', **changes):
        prior = self.entries.binding(entry)
        binding = replace(prior, version=prior.version + 1, **changes)
        return self.entries.configure(binding, expected_revision=self.repo.load()['revision'])

    def prepare_step(self, step, decision):
        """Existing P08/P17 test producer supplies an intent, never a receipt."""
        from continuity_engine.domain.action_capability import InternalActionRequest
        from continuity_engine.domain.action_planning import ActionChoice
        from continuity_engine.services.action_planning_service import ActionPlanningService
        from continuity_engine.services.continuity_core_service import _CurrentConstraints
        from .p08_action_fixture import TestChoiceProducer
        context = self.app.ledger.load_operation(self.last_request['requestId']).domain_progress.perception.continuity_context
        snapshot = context.composition.snapshot
        now = self.runtime.clock.now()
        choice = ActionChoice(decision, 'p08-test-thinking-v1', self.state.subject_id, 'TEST',
            snapshot.snapshot_hash, snapshot.source_revision, tuple(f.fragment_id for f in snapshot.fragments),
            'ACTION_INTENT', (step,), format_contract_datetime(now), format_contract_datetime(now+timedelta(minutes=2)))
        producer = TestChoiceProducer(); producer.register(choice)
        planner = ActionPlanningService(coordination=self.core.coordination, action_gate=self.core.action_gate,
            producer=producer, constraints=_CurrentConstraints(self.core, context), capabilities=self.core.capabilities,
            clock=self.runtime.clock.now, subject_id=self.state.subject_id, environment='TEST')
        binding = planner.capabilities[step.capability]
        request = InternalActionRequest(choice, step.step_id, None, binding.adapter.adapter_id, binding.canonical_hash())
        self.constraints.confirmed_ids.add(request.idempotency_key)
        self.core.coordination.ensure_action_request(request)
        self.execution.prepare(planner, choice, context.composition)
        return request, lambda retry=False: planner.run(choice, context.composition, retry=retry)

    def delivery_notice(self, entry, send_id, status):
        """An external TEST read/delivery observation about an actual send."""
        binding = self.entries.binding(entry); port = self.ports[entry]
        if not any(row['receipt']['capability_request_id'] == send_id for row in port.store.load()['facts']):
            raise AssertionError('TEST notice requires an actual native send')
        use = binding.send_use
        claim = dict(version='w04-delivery-observation-v1', request_id=send_id, entry_id=entry,
            sender=binding.subject_account, recipient=binding.recipient_account, status=status)
        now = self.runtime.clock.now()
        row = dict(source_id='notice:'+digest([send_id,status])[7:], root_id='delivery:'+send_id, version='v1',
            readable=True, software_id=use.software_id, device_id=use.device_id, session_id=use.session_id,
            object_id=send_id, occurred_at=format_contract_datetime(now), expires_at=format_contract_datetime(self.expiry),
            content=json.dumps(claim, sort_keys=True))
        port.change(history=[*port.store.load()['history'], row])
        return row

    def query_delivery(self, entry, send_id, identity):
        from continuity_engine.domain.device_operation import DeviceCommand
        from continuity_engine.domain.environment_access import HistoryScope
        binding = self.entries.binding(entry); use = binding.send_use; device = self.devices[entry]
        scope = HistoryScope(identity, self.state.subject_id, 'TEST', send_id, use.software_id,
            use.device_id, use.session_id, None, None, (), 'permission:delivery-read', 'EXTERNAL', True, False, 4)
        command = DeviceCommand('w04-device-v1', 'query', 'delivery:'+send_id, None, None, asdict(scope), device.observe(use))
        request, run = self.prepare_step(device.step(command, capability='device.query:'+digest(use.software_id)[7:23]), identity)
        result = run(); self.execution.collect(result)
        if result.status != 'COMPLETED':
            raise AssertionError('TEST delivery observation not completed: '+result.status)
        return request
