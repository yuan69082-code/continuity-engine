"""P17 transport bridge on the original E5-A request/result authority."""
from dataclasses import replace
import json

from continuity_engine.domain.action import ActionType
from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest, InternalActionResult, ReceiptQuery
from continuity_engine.domain.action_planning import ActionSpecification, digest
from continuity_engine.domain.capability import CapabilityStatus
from continuity_engine.domain.execution import BlastRadius, ExecutionError, Outcome, ROUTES, WorldCapability
from continuity_engine.domain.integration_results import format_contract_datetime
from .action_planning_service import ActionCapabilityBinding
from .continuity_core_service import CoreDecisionPolicy


class _Adapter:
    def __init__(self, service, route):
        self.service, self.route, self.adapter_id = service, route, route.adapter_id

    def query(self, request):
        return self.service.query(request)

    def execute(self, request):
        return self.service.execute(request)

    def validate_request_material(self, request):
        self.service.material(self.route,request.to_dict())

    def execution_preflight(self, request):
        route=self.service.route_for(request)
        self.service.current(request,route,'execute')
        self.service._compensation_binding(request,route)


class _Policy:
    def __init__(self, service, delegate):
        self.service, self.delegate = service, delegate or CoreDecisionPolicy()
        self.producer_id = self.delegate.producer_id

    def choose(self, operation, context, thinking, action):
        original = self.delegate.choose(operation, context, thinking, action)
        if original is None:
            return None
        steps=[]
        for step in original.steps:
            capability=self.service.selection.get(step.capability)
            if capability is None:
                steps.append(step)
                continue
            route=self.service.routes.get(capability)
            if route is None:
                raise ExecutionError('CAPABILITY_UNAVAILABLE')
            self.service.material(route, thinking.session.result.to_dict())
            steps.append(ActionSpecification(step.step_id,route.capability_ref,route.asset,
                                             step.argument_hash,step.dependencies))
        return replace(original,steps=tuple(steps))


class ExecutionService:
    def __init__(self, outbox, *, routes, adapters, boundary, broker, selection=None, limits=None, fault=None):
        self.outbox = outbox
        self.routes = {r.capability_ref:WorldCapability.from_dict(r.to_dict()) for r in routes}
        if len(self.routes)!=len(routes):
            raise ExecutionError('EXECUTION_DUPLICATE_CAPABILITY')
        self.adapters, self.boundary, self.broker = dict(adapters), boundary, broker
        self.selection = dict(selection or {})
        self.limits = limits or BlastRadius()
        self.fault = fault or (lambda point: None)
        self.core = None
        self._contexts = {}

    @staticmethod
    def port(code, callback, *args, **kwargs):
        try:
            return callback(*args,**kwargs)
        except Exception:
            raise ExecutionError(code) from None

    def material(self, route, value):
        if self.port('EXECUTION_MATERIAL_CHECK_UNAVAILABLE',self.broker.material_allowed,route,value) is not True:
            raise ExecutionError('EXECUTION_MATERIAL_REJECTED')

    def validate_input_material(self, material):
        for route in self.routes.values():
            self.material(route,material)

    def validate_thinking_material(self, perception, result):
        self.validate_input_material(self.port('EXECUTION_MATERIAL_REJECTED',result.to_dict))

    def bind(self, core):
        if (core.subject_id,core.environment)!=(self.outbox.subject_id,self.outbox.environment):
            raise ExecutionError('EXECUTION_CORE_BINDING')
        self.core=core

    def bindings(self):
        for route in self.routes.values():
            self.material(route,route.to_dict())
        return tuple(ActionCapabilityBinding(r.capability_ref,_Adapter(self,r),ActionType.USE_TOOL,
                    r.permission,r.cost,True,r.hash,r.max_attempts) for r in self.routes.values())

    def policy(self, delegate):
        return _Policy(self,delegate)

    def prepare(self, planner, choice, context):
        """Ephemeral authorization view; immutable source lives in original C1 records."""
        for step in choice.steps:
            if step.capability in self.routes:
                self._contexts[(choice.decision_id,step.step_id)] = (planner,choice,context)

    def request(self, request_id):
        # Existing E5-A repository is the sole source of request contents.
        return self.core.coordination._repository.load_capability_request(request_id)

    def route_for(self, request):
        route=self.routes.get(request.capability_type)
        if route is None:
            raise ExecutionError('CAPABILITY_UNAVAILABLE')
        binding=next(b for b in self.bindings() if b.capability==route.capability_ref)
        if ((request.subject_id,request.choice.environment,request.adapter_id,request.step.target,request.policy_hash)
                != (route.subject_id,route.environment,route.adapter_id,route.asset,binding.canonical_hash())
                or (route.subject_id,route.environment)!=(self.outbox.subject_id,self.outbox.environment)):
            raise ExecutionError('EXECUTION_REQUEST_BINDING')
        self.material(route,request.to_dict())
        if self.request(request.capability_request_id)!=request:
            raise ExecutionError('EXECUTION_LEDGER_BINDING')
        return route

    def adapter(self, route):
        adapter=self.adapters.get(route.adapter_id)
        if adapter is None or adapter.adapter_id!=route.adapter_id:
            raise ExecutionError('CAPABILITY_UNAVAILABLE')
        binding=self.port('EXECUTION_ADAPTER_BINDING',lambda:
            (adapter.subject_id,adapter.environment,adapter.world,adapter.version))
        if binding!=(route.subject_id,route.environment,route.world,route.version):
            raise ExecutionError('EXECUTION_ADAPTER_BINDING')
        return adapter

    def _entry(self, document, request, route, *, create=False):
        entry=next((e for e in document['entries'] if e['request_id']==request.capability_request_id),None)
        if entry is not None and (entry['request_hash'],entry['route_hash'])!=(request.request_hash,route.hash):
            raise ExecutionError('EXECUTION_OUTBOX_BINDING')
        if entry is None and create:
            if len(document['entries'])>=min(256,self.limits.requests):
                raise ExecutionError('RESOURCE_EXHAUSTED')
            entry=dict(request_id=request.capability_request_id,request_hash=request.request_hash,
                       route_hash=route.hash,state='PENDING',attempts=0,receipt_hash=None,reason='PENDING',links=[])
            document['entries'].append(entry)
        return entry

    def _fact(self, request, route):
        fact=self.port('EXECUTION_QUERY_UNAVAILABLE',self.adapter(route).query,request)
        if isinstance(fact,ActionReceipt):
            # Check the WHOLE receipt before any Engine persistence or diagnostics.
            self.material(route,self.port('EXECUTION_RECEIPT_REJECTED',fact.to_dict))
            self.port('EXECUTION_RECEIPT_BINDING',fact.validate_request,request)
            return fact
        return ReceiptQuery.NOT_EXECUTED if fact is ReceiptQuery.NOT_EXECUTED else ReceiptQuery.UNKNOWN

    def query(self, request):
        route=self.route_for(request)
        entry=self._entry(self.outbox.load(),request,route)
        fact=self._fact(request,route)
        if entry and entry['state']=='DELIVERED':
            if not isinstance(fact,ActionReceipt) or fact.canonical_hash()!=entry['receipt_hash']:
                raise ExecutionError('EXECUTION_DELIVERY_FACT_CONFLICT')
        if entry and entry['state']=='CANCELLED' and fact is not ReceiptQuery.NOT_EXECUTED:
            raise ExecutionError('EXECUTION_CANCEL_FACT_CONFLICT')
        return fact

    def current(self, request, route, purpose):
        if purpose=='execute' and self._stopped(request):
            raise ExecutionError('CANCELLED')
        if route.world=='REAL':
            raise ExecutionError('RECOVERABILITY_NOT_READY')
        if purpose=='execute':
            # Resource calculation may change local permission/readiness. It is
            # preparation, never the authorization snapshot for the world call.
            if self.port('RESOURCE_EXHAUSTED',self.boundary.capacity,route,request,self.limits) is not True:
                raise ExecutionError('RESOURCE_EXHAUSTED')
            scope=self._contexts.get((request.choice.decision_id,request.step_id))
            if scope is None:
                raise ExecutionError('EXECUTION_CONTEXT_REQUIRED')
            planner,choice,context=scope
            if request.choice!=choice:
                raise ExecutionError('EXECUTION_CONTEXT_BINDING')
            self.port('EXECUTION_CONTEXT_BINDING',planner._validate_input,choice,context)
            if self.port('EXECUTION_CONTEXT_CHECK_UNAVAILABLE',planner.constraints.validate_context,context) is not True:
                raise ExecutionError('CONTEXT_CHANGED_BEFORE_ACTION')
            reason,_=self.port('PLATFORM_DENIAL',planner._gate,request,planner.capabilities[request.capability_type],format_contract_datetime(self.core.clock()))
            if reason:
                raise ExecutionError(reason)
        # Read the current authorization barrier AFTER all resource/gate work.
        # In execute(), the final barrier is under the dispatch lock and applies
        # only to that synchronous dispatch, never to later requests or retries.
        # Ports must provide read-only decisions here; no distributed lease or
        # arbitrary production-time revocation guarantee is implied.
        if self.port('PLATFORM_DENIAL',self.boundary.ready,route) is not True:
            raise ExecutionError('RESEARCH_UNAVAILABLE' if route.world=='RESEARCH' else 'CAPABILITY_UNAVAILABLE')
        self.port('SUBJECT_NOT_ACTIVE',self.core.subject_states.require_active,route.subject_id,route.environment)
        if self.port('PLATFORM_DENIAL',self.broker.authorize_reference,route,at=self.core.clock(),purpose=purpose) is not True:
            raise ExecutionError('PLATFORM_DENIAL')
        if self.port('PLATFORM_DENIAL',self.boundary.authorize,route,request,purpose=purpose) is not True:
            raise ExecutionError('REALITY_DENIAL')
        if purpose=='execute' and self.port('RECOVERABILITY_NOT_READY',self.boundary.recoverable,route) is not True:
            raise ExecutionError('RECOVERABILITY_NOT_READY')

    def execute(self, request):
        route=self.route_for(request)
        # Querying past facts is deliberately independent of current permission.
        prior=self.query(request)
        if isinstance(prior,ActionReceipt):
            return prior
        if prior is not ReceiptQuery.NOT_EXECUTED:
            raise ExecutionError('EXECUTION_UNKNOWN')
        self.current(request,route,'execute')
        self._compensation_binding(request,route)
        with self.outbox.transaction() as document:
            entry=self._entry(document,request,route,create=True)
            if entry['state']=='CANCELLED':
                raise ExecutionError('EXECUTION_CANCELLED')
            fact=self._fact(request,route)
            if isinstance(fact,ActionReceipt):
                entry.update(state='DELIVERED',receipt_hash=fact.canonical_hash(),reason='VERIFIED')
                self.outbox.save(document)
                return fact
            if fact is not ReceiptQuery.NOT_EXECUTED:
                raise ExecutionError('EXECUTION_UNKNOWN')
            if entry['attempts']>=route.max_attempts:
                raise ExecutionError('EXECUTION_ATTEMPT_LIMIT')
            # Recheck under the dispatch lease, directly before external effect.
            self.current(request,route,'execute')
            self._compensation_binding(request,route)
            entry.update(state='DISPATCHING',attempts=entry['attempts']+1,reason='DISPATCHING')
            self.outbox.save(document)
            self.fault('before_world')
            try:
                receipt=self.port('NETWORK_FAILED',self.adapter(route).execute,request)
                self.material(route,self.port('EXECUTION_RECEIPT_REJECTED',receipt.to_dict))
                self.port('EXECUTION_RECEIPT_BINDING',receipt.validate_request,request)
                verified=self._fact(request,route)
                if not isinstance(verified,ActionReceipt) or verified!=receipt:
                    raise ExecutionError('EXECUTION_RECEIPT_UNVERIFIED')
            except Exception:
                entry.update(state='UNKNOWN',reason='UNKNOWN')
                self.outbox.save(document)
                raise ExecutionError('EXECUTION_RESPONSE_UNKNOWN') from None
            self.fault('after_world_before_delivery')
            entry.update(state='DELIVERED',receipt_hash=receipt.canonical_hash(),reason='VERIFIED')
            self.outbox.save(document)
            return receipt

    def _compensation_binding(self, request, route):
        if not route.compensation:
            return
        parents=[e for e in self.outbox.load()['entries'] if
                 dict(kind='COMPENSATION',request_id=request.capability_request_id) in e['links']]
        if len(parents)!=1:
            raise ExecutionError('EXECUTION_COMPENSATION_LINK_REQUIRED')
        original=self.request(parents[0]['request_id']);previous=self.route_for(original)
        fact=self.query(original)
        if (not isinstance(fact,ActionReceipt) or fact.status!='SUCCEEDED'
                or request.step.argument_hash!=digest(['compensate',fact.canonical_hash()])
                or (route.world,route.asset,route.subject_id,route.environment)!=(previous.world,previous.asset,previous.subject_id,previous.environment)):
            raise ExecutionError('EXECUTION_COMPENSATION_BINDING')

    def collect(self, run):
        for request,result in zip(run.requests,run.results):
            if request.capability_type not in self.routes or result is None:
                continue
            receipt=self.query(request)
            if not isinstance(receipt,ActionReceipt) or receipt!=result.receipt:
                raise ExecutionError('EXECUTION_RESULT_BINDING')
            route=self.route_for(request)
            with self.outbox.transaction() as document:
                entry=self._entry(document,request,route,create=True)
                if entry['state']!='DELIVERED':
                    entry.update(state='DELIVERED',receipt_hash=receipt.canonical_hash(),reason='VERIFIED')
                    self.outbox.save(document)

    def cancel(self, request_id):
        request=self.request(request_id);route=self.route_for(request)
        self.current(request,route,'cancel')
        with self.outbox.transaction() as document:
            entry=self._entry(document,request,route,create=True)
            fact=self._fact(request,route)
            if isinstance(fact,ActionReceipt):
                return Outcome.COMPLETED if fact.status=='SUCCEEDED' else Outcome.UNKNOWN
            if fact is not ReceiptQuery.NOT_EXECUTED:
                return Outcome.UNKNOWN
            if entry['state']=='DELIVERED':
                raise ExecutionError('EXECUTION_DELIVERY_FACT_CONFLICT')
            self._record_stop(request)
            if entry['state']!='CANCELLED':
                entry.update(state='CANCELLED',reason='CANCELLED')
                self.outbox.save(document)
            return Outcome.CANCELLED

    def _stopped(self, request):
        adapter=next(b.adapter for b in self.bindings() if b.capability==request.capability_type)
        return any(a.result.reason=='CANCELLED' for a in self.core.coordination.action_attempts(request,receipt_verifier=adapter))

    def _record_stop(self, request):
        """Local stop decision in the EXISTING ledger, not proof of execution failure."""
        if self._stopped(request):return
        adapter=next(b.adapter for b in self.bindings() if b.capability==request.capability_type)
        now=format_contract_datetime(self.core.clock())
        result=InternalActionResult(request,CapabilityStatus.UNKNOWN,'CANCELLED',now,
                                    gate_reasons=('DELIVERY_STOP_AFTER_NOT_EXECUTED_QUERY',))
        self.core.coordination.accept_action_result(result,received_at=now,receipt_verifier=adapter)

    def stop(self, decision_id):
        """Stop remaining steps individually; never relabel completed/unknown facts."""
        requests=self.core.coordination.action_requests_by_decision(decision_id)
        return tuple((r.capability_request_id,self.cancel(r.capability_request_id)) for r in requests
                     if r.capability_type in self.routes)

    def outcome(self, request_id):
        request=self.request(request_id);route=self.route_for(request)
        fact=self.query(request)
        if isinstance(fact,ActionReceipt):
            if fact.status=='SUCCEEDED':return Outcome.COMPLETED
            payload=self.port('EXECUTION_RESULT_UNAVAILABLE',self.adapter(route).read_result,request)
            self.material(route,payload)
            if digest(payload)!=fact.output_hash:
                raise ExecutionError('EXECUTION_RESULT_HASH')
            reason=payload.get('kind')
            if reason not in {Outcome.REALITY_DENIAL.value,Outcome.GENERATION_FAILED.value,Outcome.NETWORK_FAILED.value}:
                return Outcome.UNKNOWN
            return Outcome(reason)
        if fact is not ReceiptQuery.NOT_EXECUTED:return Outcome.UNKNOWN
        entry=self._entry(self.outbox.load(),request,route)
        if entry and entry['state']=='CANCELLED':return Outcome.CANCELLED
        adapter=next(b.adapter for b in self.bindings() if b.capability==request.capability_type)
        attempts=self.core.coordination.action_attempts(request,receipt_verifier=adapter)
        if attempts and attempts[-1].result.reason in {x.value for x in Outcome}:
            return Outcome(attempts[-1].result.reason)
        return Outcome.UNKNOWN

    def alternative(self, request_id, kind, replacement_id=None):
        if kind not in ROUTES:
            raise ExecutionError('EXECUTION_ALTERNATIVE_INVALID')
        request=self.request(request_id);route=self.route_for(request)
        self.current(request,route,'cancel')
        with self.outbox.transaction() as document:
            entry=self._entry(document,request,route,create=True)
            if kind in {'CHANGE_ROUTE','ABANDON'}:
                fact=self._fact(request,route)
                if fact is not ReceiptQuery.NOT_EXECUTED:
                    raise ExecutionError('EXECUTION_UNKNOWN_ROUTE_FORBIDDEN')
                if kind=='CHANGE_ROUTE':
                    replacement=self.request(replacement_id)
                    new=self.route_for(replacement)
                    self.current(replacement,new,'execute')
                    if replacement_id==request_id or (new.world,new.asset,new.subject_id,new.environment)!=(route.world,route.asset,route.subject_id,route.environment) or new.cost>route.cost:
                        raise ExecutionError('EXECUTION_ALTERNATIVE_SCOPE')
                self._record_stop(request)
                entry.update(state='CANCELLED',reason='CANCELLED')
            elif replacement_id is not None:
                raise ExecutionError('EXECUTION_ALTERNATIVE_INVALID')
            link=dict(kind=kind,request_id=replacement_id)
            if link not in entry['links']:
                if len(entry['links'])>=16:raise ExecutionError('EXECUTION_ALTERNATIVE_LIMIT')
                entry['links'].append(link);self.outbox.save(document)
        return kind

    def compensation(self, request_id, compensation_id):
        original=self.request(request_id);route=self.route_for(original)
        fact=self.query(original)
        if not isinstance(fact,ActionReceipt) or fact.status!='SUCCEEDED':
            raise ExecutionError('EXECUTION_COMPENSATION_FACT_REQUIRED')
        request=self.request(compensation_id);new=self.route_for(request)
        if (not new.compensation or request_id==compensation_id or request.step.argument_hash!=digest(['compensate',fact.canonical_hash()])
                or (new.world,new.asset,new.subject_id,new.environment)!=(route.world,route.asset,route.subject_id,route.environment)):
            raise ExecutionError('EXECUTION_COMPENSATION_BINDING')
        self.current(request,new,'execute')
        with self.outbox.transaction() as document:
            entry=self._entry(document,original,route,create=True)
            link=dict(kind='COMPENSATION',request_id=compensation_id)
            if link not in entry['links']:
                if len(entry['links'])>=16:raise ExecutionError('EXECUTION_ALTERNATIVE_LIMIT')
                entry['links'].append(link);self.outbox.save(document)
        # Dispatch must still go through original P08/E5-A, never direct call here.
        return compensation_id

    def results_for_context(self):
        values=[]
        for entry in self.outbox.load()['entries']:
            if entry['state']!='DELIVERED':
                continue
            request=self.request(entry['request_id']);route=self.route_for(request)
            # Research never silently becomes Main evidence.
            if route.world!=self.core.environment:
                continue
            self.current(request,route,'consume')
            adapter=next(b.adapter for b in self.bindings() if b.capability==request.capability_type)
            attempts=self.core.coordination.action_attempts(request,receipt_verifier=adapter)
            if not attempts or attempts[-1].result.status is not CapabilityStatus.SUCCEEDED:
                continue
            fact=self.query(request)
            payload=self.port('EXECUTION_RESULT_UNAVAILABLE',self.adapter(route).read_result,request)
            self.material(route,payload)
            if not isinstance(payload,dict) or set(payload)!={'request_id','request_hash','world','asset','content','kind'}:
                raise ExecutionError('EXECUTION_RESULT_SHAPE')
            if (payload['request_id'],payload['request_hash'],payload['world'],payload['asset'])!=(request.capability_request_id,request.request_hash,route.world,route.asset):
                raise ExecutionError('EXECUTION_RESULT_BINDING')
            if not isinstance(payload['content'],str) or len(json.dumps(payload).encode())>route.max_output_bytes or digest(payload)!=fact.output_hash:
                raise ExecutionError('EXECUTION_RESULT_HASH')
            self.current(request,route,'consume')
            if self.query(request)!=fact:
                raise ExecutionError('EXECUTION_RESULT_DRIFT')
            values.append((request,route,fact,payload))
        return values
