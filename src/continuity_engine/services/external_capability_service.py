"""P16 on the original C1/P08/E5-A path; no independent request/result authority."""
from dataclasses import replace
from datetime import timedelta
from continuity_engine.domain.action import ActionType
from continuity_engine.domain.action_planning import ActionChoice,ActionSpecification,digest
from continuity_engine.domain.action_capability import ActionReceipt,ReceiptQuery,InternalActionRequest
from continuity_engine.domain.capability import parse_capability_datetime,CapabilityStatus
from continuity_engine.domain.external_capabilities import QueryInput,ProviderResult,ExternalCapabilityError,KINDS
from continuity_engine.domain.subject_lifecycle import LifecycleError
from continuity_engine.domain.integration_results import format_contract_datetime
from .action_planning_service import ActionCapabilityBinding
from .continuity_core_service import CoreDecisionPolicy


class _Adapter:
    def __init__(self,service,descriptor):
        self.service,self.descriptor=service,descriptor;self.adapter_id=descriptor.adapter_id
    def query(self,request):
        self.service.check_request(request,self.descriptor)
        try:fact=self.service.provider(self.descriptor).query_receipt(request)
        except Exception:raise ExternalCapabilityError('EXTERNAL_RECEIPT_UNAVAILABLE') from None
        self.service.check_receipt(fact,request,self.descriptor)
        return fact
    def execute(self,request):
        s=self.service;s.check_request(request,self.descriptor);s.require_current(self.descriptor,'execute')
        # The only dispatch authorization is P08's current Context/Action gate.
        try:fact=s.provider(self.descriptor).execute_query(request,self.descriptor)
        except Exception:raise ExternalCapabilityError('EXTERNAL_RESPONSE_UNKNOWN') from None
        s.check_receipt(fact,request,self.descriptor)
        return fact


class _Policy:
    def __init__(self,service,delegate):
        self.s,self.delegate=service,delegate or CoreDecisionPolicy();self.producer_id=self.delegate.producer_id
    def choose(self,operation,context,thinking,action):
        original=self.delegate.choose(operation,context,thinking,action)
        result=thinking.session.result
        if original is None or not result.request_more_memory:return original
        query=self.s.parse_query(result.additional_memory_query)
        existing=self.s.core.coordination.action_requests_by_decision(original.decision_id)
        # Historical selection remains fixed. Registry replacement never retargets a pending request.
        if existing:
            first=existing[0];d=self.s.descriptor_for(first)
            self.s.check_request(first,d)
        else:
            d=self.s.select(query.kind)
        if not self.s.material_allowed(d,query.to_dict()):raise ExternalCapabilityError('EXTERNAL_INPUT_REJECTED')
        steps=tuple(ActionSpecification(step.step_id,d.capability_ref,d.key,digest(query.to_dict()),step.dependencies,query.to_dict())
            if step.capability=='memory.lookup' else step for step in original.steps)
        choice=replace(original,steps=steps)
        if existing and any(r.choice!=choice for r in existing):raise ExternalCapabilityError('EXTERNAL_HISTORY_INPUT_CONFLICT')
        return choice


class ExternalCapabilityService:
    def __init__(self,registry,*,broker,permissions,providers):
        self.registry,self.broker,self.permissions,self.providers=registry,broker,permissions,dict(providers)
        self.core=None;self.calls={'select':0,'consume':0,'cache':0};self.last_outcome=None;self.last_trace_entry=None
        self.projection_audit={}
    def bind(self,core):
        if (core.subject_id,core.environment)!=(self.registry.subject_id,self.registry.environment):
            raise ExternalCapabilityError('EXTERNAL_CORE_BINDING')
        self.core=core
    def provider(self,d):
        port=self.providers.get(d.key)
        if port is None:raise ExternalCapabilityError('EXTERNAL_PROVIDER_NOT_READY')
        return port
    @staticmethod
    def _port(code,call,*args,**kwargs):
        # External diagnostics are not trusted material, including exception chains.
        try:return call(*args,**kwargs)
        except Exception:raise ExternalCapabilityError(code) from None
    def material_allowed(self,d,value):
        return self._port('EXTERNAL_MATERIAL_CHECK_UNAVAILABLE',self.broker.material_allowed,d,value) is True
    def authorize_reference(self,d,*,at,purpose):
        return self._port('EXTERNAL_CREDENTIAL_CHECK_UNAVAILABLE',self.broker.authorize_reference,d,at=at,purpose=purpose) is True
    def authorize_permission(self,d,*,at,purpose):
        return self._port('EXTERNAL_PERMISSION_CHECK_UNAVAILABLE',self.permissions.authorize,d,at=at,purpose=purpose) is True
    def validate_thinking_material(self,perception,result):
        """Optional C1 pre-persistence boundary, also used for original-result replay.

        This checks credential-class material only. It does not grant current
        execution permission: revocation must still allow safe fact recovery.
        Disabled historical descriptors retain their original material boundary.
        """
        value=self._port('EXTERNAL_INPUT_REJECTED',lambda: result.to_dict())
        self.validate_input_material(value)
    def validate_input_material(self,value):
        """Also guard the original C1 model-result ingress before E5-A append."""
        for d,_ in self.registry.descriptors():
            if not self.material_allowed(d,value):raise ExternalCapabilityError('EXTERNAL_INPUT_REJECTED')
    def check_receipt(self,fact,request,d):
        if isinstance(fact,ActionReceipt):
            value=self._port('EXTERNAL_RECEIPT_MATERIAL_REJECTED',fact.to_dict)
            if not self.material_allowed(d,value):raise ExternalCapabilityError('EXTERNAL_RECEIPT_MATERIAL_REJECTED')
            fact.validate_request(request)
    def register(self,d,*,expected_revision):
        c=self.core;c.subject_states.require_active(c.subject_id,c.environment)
        if (d.subject_id,d.environment)!=(c.subject_id,c.environment):raise ExternalCapabilityError('EXTERNAL_BOUNDARY')
        if (not self.material_allowed(d,d.to_dict()) or not self.authorize_reference(d,at=c.clock(),purpose='register')
                or not self.authorize_permission(d,at=c.clock(),purpose='register')):
            raise ExternalCapabilityError('EXTERNAL_REGISTRATION_DENIED')
        self.registry.register(d,expected_revision=expected_revision)
    def bindings(self):
        return tuple(ActionCapabilityBinding(d.capability_ref,_Adapter(self,d),ActionType.REQUEST_MEMORY,
            d.permission,0,True,d.version,d.max_attempts) for d,_ in self.registry.descriptors())
    def policy(self,delegate):return _Policy(self,delegate)
    @staticmethod
    def parse_query(value):
        if not isinstance(value,str):raise ExternalCapabilityError('EXTERNAL_INFORMATION_NEED_REQUIRED')
        head,sep,query=value.partition(':')
        return QueryInput(head,query) if sep and head in KINDS else QueryInput('memory',value)
    def select(self,kind):
        self.calls['select']+=1
        for d,enabled in sorted(self.registry.descriptors(),key=lambda item:item[0].key,reverse=True):
            if enabled and d.kind==kind:
                self.require_current(d,'select');return d
        raise ExternalCapabilityError('EXTERNAL_CAPABILITY_UNAVAILABLE')
    def require_current(self,d,purpose):
        current,enabled=self.registry.get(d.key)
        if current!=d or not enabled:raise ExternalCapabilityError('EXTERNAL_CONNECTOR_REVOKED')
        c=self.core
        try:c.subject_states.require_active(c.subject_id,c.environment)
        except LifecycleError as exc:
            if str(exc)!='SUBJECT_NOT_ACTIVE':raise
            raise ExternalCapabilityError('EXTERNAL_SUBJECT_NOT_ACTIVE') from None
        if (d.subject_id,d.environment)!=(c.subject_id,c.environment):raise ExternalCapabilityError('EXTERNAL_BOUNDARY')
        if c.clock()>=parse_capability_datetime(d.expires_at):raise ExternalCapabilityError('EXTERNAL_CONNECTOR_EXPIRED')
        if not self.authorize_permission(d,at=c.clock(),purpose=purpose):raise ExternalCapabilityError('EXTERNAL_PERMISSION_DENIED')
        if not self.authorize_reference(d,at=c.clock(),purpose=purpose):raise ExternalCapabilityError('EXTERNAL_CREDENTIAL_REFERENCE_DENIED')
    def descriptor_for(self,request):
        return self.registry.get(request.step.target)[0]
    def check_request(self,r,d):
        query=QueryInput.from_dict(r.step.input_payload)
        if not self.material_allowed(d,query.to_dict()):raise ExternalCapabilityError('EXTERNAL_INPUT_REJECTED')
        binding=ActionCapabilityBinding(d.capability_ref,_Adapter(self,d),ActionType.REQUEST_MEMORY,d.permission,0,True,d.version,d.max_attempts)
        if (r.adapter_id,r.policy_hash,r.subject_id,r.choice.environment,r.step.capability,r.step.target,query.kind,r.step.argument_hash)!=(
                d.adapter_id,binding.canonical_hash(),d.subject_id,d.environment,d.capability_ref,d.key,d.kind,digest(query.to_dict())):
            raise ExternalCapabilityError('EXTERNAL_REQUEST_BINDING')
    def _verified(self,r,*,consume):
        d=self.descriptor_for(r);self.check_request(r,d)
        attempts=self.core.coordination.action_attempts(r,receipt_verifier=_Adapter(self,d))
        if not attempts or attempts[-1].result.status is not CapabilityStatus.SUCCEEDED:
            raise ExternalCapabilityError('EXTERNAL_RESULT_NOT_SUCCEEDED')
        if consume:self.require_current(d,'consume')
        try:value=ProviderResult.from_dict(self.provider(d).read_result(r).to_dict())
        except Exception:raise ExternalCapabilityError('EXTERNAL_RESULT_REJECTED') from None
        value.validate_request(r,d)
        if digest(value.to_dict())!=attempts[-1].result.receipt.output_hash:
            raise ExternalCapabilityError('EXTERNAL_RESULT_HASH_CONFLICT')
        if not self.material_allowed(d,value.to_dict()):raise ExternalCapabilityError('EXTERNAL_MATERIAL_REJECTED')
        now=self.core.clock()
        if consume:
            for item in value.candidates:
                if (parse_capability_datetime(item.observed_at)>now or now>=parse_capability_datetime(item.expires_at)
                        or now>=parse_capability_datetime(item.observed_at)+timedelta(seconds=d.cache_seconds)):
                    raise ExternalCapabilityError('EXTERNAL_RESULT_EXPIRED')
            self.require_current(d,'consume')
        return value
    def collect(self,run):
        for r,result in zip(run.requests,run.results):
            if not r.step.capability.startswith('external.'):continue
            # Replayed facts may be valid while the old payload is no longer consumable.
            try:value=self._verified(r,consume=True)
            except ExternalCapabilityError as exc:
                if str(exc) not in ('EXTERNAL_RESULT_EXPIRED','EXTERNAL_CONNECTOR_REVOKED','EXTERNAL_CONNECTOR_EXPIRED',
                                    'EXTERNAL_PERMISSION_DENIED','EXTERNAL_CREDENTIAL_REFERENCE_DENIED','EXTERNAL_SUBJECT_NOT_ACTIVE'):raise
                # _verified already checked the original independent receipt. Lack
                # of current access forbids payload use, not historical fact recovery.
                self.last_outcome='CONSUMPTION_DENIED'
                self.last_trace_entry={'status':self.last_outcome,'request_id':r.capability_request_id,'candidate_count':0,
                    'authority':'retrieved_candidate','snapshot_hash':r.choice.snapshot_hash}
                continue
            self.last_outcome=value.status
            self.calls['cache']+=1;self.registry.cache(value,at=format_contract_datetime(self.core.clock()))
            self.last_trace_entry={'status':value.status,'request_id':r.capability_request_id,
                'candidate_count':len(value.candidates),'authority':'retrieved_candidate','snapshot_hash':r.choice.snapshot_hash}
    def cached(self):
        self.calls['consume']+=1;values=[]
        for entry in self.registry.cached():
            r=self.core.coordination._repository.load_capability_request(entry['request_id'])
            if not isinstance(r,InternalActionRequest):raise ExternalCapabilityError('EXTERNAL_CACHE_REQUEST_MISSING')
            try:value=self._verified(r,consume=True)
            except ExternalCapabilityError as exc:
                if str(exc) in ('EXTERNAL_RESULT_EXPIRED','EXTERNAL_CONNECTOR_REVOKED','EXTERNAL_CONNECTOR_EXPIRED','EXTERNAL_PERMISSION_DENIED','EXTERNAL_CREDENTIAL_REFERENCE_DENIED','EXTERNAL_SUBJECT_NOT_ACTIVE'):
                    continue
                raise
            if value.to_dict()!=entry['result']:raise ExternalCapabilityError('EXTERNAL_CACHE_RESULT_CONFLICT')
            values.append((r,value))
        return tuple(values)
