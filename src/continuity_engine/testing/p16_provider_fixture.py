"""Versioned local P16 ports. No SDK, network, real credential, or production data."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import RLock
import json
from continuity_engine.domain.action_capability import ActionReceipt,ReceiptQuery
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.external_capabilities import ProviderDescriptor,ProviderResult,ExternalCandidate,ExternalCapabilityError,KINDS
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.domain.thinking import ThinkingResult
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.interfaces.local_integration_app import build_local_integration_app
from continuity_engine.services.external_capability_service import ExternalCapabilityService
from continuity_engine.services.continuity_core_runtime import build_continuity_core
from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
from .p08_action_fixture import _validate_fixture_root
from .p09_core_fixture import P09Fixture,CoreClaims,CoreConstraints
from .interaction import SandboxContractValidator,SandboxFirstRoundResultFactory
from .persistence import atomic_write_json,read_json

_FAKE_LOCK=RLock()
SECRET_MARKER='P16_SYNTHETIC_SECRET_DO_NOT_PERSIST'


class FakeBroker:
    """Reference-only control. Synthetic secret is never returned as a credential."""
    def __init__(self,path,clock):self.path,self.clock=path,clock
    def authorize_reference(self,d,*,at,purpose):
        row=read_json(self.path)
        return (row['subject_id']==d.subject_id and row['environment']==d.environment and row['broker_allowed']
            and d.credential_ref in row['credential_refs'] and row['credential_bindings'].get(d.credential_ref)==d.connector_id
            and at<__import__('datetime').datetime.fromisoformat(row['expires_at']))
    def material_allowed(self,d,value):
        text=json.dumps(value,ensure_ascii=False)
        return SECRET_MARKER not in text


class FakePermissions:
    def __init__(self,path):self.path=path
    def authorize(self,d,*,at,purpose):
        row=read_json(self.path)
        return row['permission_allowed'] and (row['subject_id'],row['environment'])==(d.subject_id,d.environment)


class FakeQueryProvider:
    def __init__(self,path,control,clock):
        _validate_fixture_root(path.parent)
        self.path,self.control,self.clock=path,control,clock
        self.query_calls=0;self.execute_calls=0;self.result_hook=None;self.candidate_hook=None
        if not path.exists():atomic_write_json(path,{'version':'p16-fake-receipts-v1','facts':[],'hash':digest([])})
    def facts(self):
        value=read_json(self.path)
        if value['version']!='p16-fake-receipts-v1' or value['hash']!=digest(value['facts']):raise ExternalCapabilityError('FAKE_FACTS_CORRUPT')
        return value['facts']
    def query_receipt(self,r):
        self.query_calls+=1;mode=read_json(self.control)['mode']
        if mode=='query_exception':raise RuntimeError(SECRET_MARKER)
        if mode=='unknown':return ReceiptQuery.UNKNOWN
        if mode=='untyped_not_executed':return 'NOT_EXECUTED'
        for entry in self.facts():
            fact=ActionReceipt.from_dict(entry['receipt'])
            if fact.capability_request_id==r.capability_request_id:fact.validate_request(r);return fact
        return ReceiptQuery.NOT_EXECUTED
    def execute_query(self,r,d):
        self.execute_calls+=1
        with _FAKE_LOCK:
            prior=self.query_receipt(r)
            if isinstance(prior,ActionReceipt):return prior
            if prior is not ReceiptQuery.NOT_EXECUTED:raise ExternalCapabilityError('FAKE_UNKNOWN')
            mode=read_json(self.control)['mode']
            if mode=='timeout_unknown':raise TimeoutError(SECRET_MARKER)
            now=self.clock();query=r.step.input_payload['query']
            status={'offline':'OFFLINE','timeout':'TIMEOUT','cancelled':'CANCELLED','empty':'EMPTY'}.get(mode,'AVAILABLE')
            candidates=()
            if status=='AVAILABLE':
                content=('continuity: deterministic '+query.upper() if d.kind=='skill' else 'continuity: local '+d.kind+' knowledge about '+query)
                candidate=ExternalCandidate('item:continuity','v1',content,digest(content),format_contract_datetime(now),
                    format_contract_datetime(now+timedelta(seconds=300)),0.7,('external:shared-source:continuity',))
                if self.candidate_hook:candidate=self.candidate_hook(candidate)
                candidates=(candidate,)
            result=ProviderResult(d.connector_id,digest(d.to_dict()),r.subject_id,r.choice.environment,r.capability_request_id,r.request_hash,status,candidates)
            receipt=ActionReceipt('receipt:'+r.idempotency_key[7:],r.capability_request_id,r.request_hash,d.adapter_id,
                r.subject_id,r.choice.environment,r.step_id,'SUCCEEDED',0,0,format_contract_datetime(now),digest(result.to_dict()))
            facts=[*self.facts(),{'receipt':receipt.to_dict(),'result':result.to_dict()}]
            atomic_write_json(self.path,{'version':'p16-fake-receipts-v1','facts':facts,'hash':digest(facts)})
            if mode=='lost_response':raise RuntimeError(SECRET_MARKER)
            return receipt
    def read_result(self,r):
        value=next(e['result'] for e in self.facts() if e['receipt']['capability_request_id']==r.capability_request_id)
        if self.result_hook:value=self.result_hook(json.loads(json.dumps(value)))
        return ProviderResult.from_dict(value)


class _Thinking:
    provider_id='p16-local-thinking-v1'
    def __init__(self,fixture):self.fixture=fixture;self.inputs=[]
    def think(self,perception,budget):
        self.inputs.append(perception)
        return ThinkingResult.create(provider_id=self.provider_id,result_summary='Local structured information need',
            rationale_summary='P16 bounded external candidate query',generated_new_thought=True,update_subject_state=False,
            request_more_memory=True,additional_memory_query=self.fixture.query,token_budget=budget,
            should_wait=False,suggest_future_user_contact=False)


class _Constraints(CoreConstraints):
    def confirmed(self,request):
        if request.step.capability.startswith('external.'):
            return self.confirmation_allowed and request.choice.environment=='TEST' and request.step.target in self.registered
        return super().confirmed(request)


class P16Fixture:
    def __init__(self,root,*,runtime=None,manager=None):
        self.root=_validate_fixture_root(Path(root));self.base=P09Fixture(self.root,runtime=runtime,manager=manager)
        self.runtime,self.manager=self.base.runtime,self.base.manager
        self.query='memory:continuity';self.feature=True;self.core_options={'context_budget':ContextBudget(token_limit=1024)}
        self.control=self.runtime.data_root/'fixture/p16-control.json'
        self.registry=JsonExternalProviderRepository(self.runtime.data_root,subject_id=self.runtime.descriptor.subject_id,environment='TEST')
        self.descriptors=[ProviderDescriptor('local.'+kind,'v1','external.'+kind+'.v1',kind,'credential:'+kind,
            self.runtime.descriptor.subject_id,'TEST','test:lookup',format_contract_datetime(self.runtime.clock.now()+timedelta(days=30)),
            'Local TEST '+kind+' query') for kind in KINDS]
        if not self.control.exists():
            atomic_write_json(self.control,{'subject_id':self.runtime.descriptor.subject_id,'environment':'TEST',
                'broker_allowed':True,'permission_allowed':True,'credential_refs':[d.credential_ref for d in self.descriptors],
                'credential_bindings':{d.credential_ref:d.connector_id for d in self.descriptors},
                'expires_at':format_contract_datetime(self.runtime.clock.now()+timedelta(days=30)),'mode':'success'})
            for d in self.descriptors:self.registry.register(d,expected_revision=self.registry.revision)
            self.registry._write('cache',self.registry._empty('cache'))
            atomic_write_json(self.runtime.data_root/'fixture/p16-profile.json',{'version':'p16-test-v1','subject_id':self.runtime.descriptor.subject_id,'environment':'TEST'})
        self.broker=FakeBroker(self.control,self.runtime.clock.now);self.permissions=FakePermissions(self.control)
        self.fake=FakeQueryProvider(self.runtime.data_root/'p16-fake/facts.json',self.control,self.runtime.clock.now)
        self.external=ExternalCapabilityService(self.registry,broker=self.broker,permissions=self.permissions,
            providers={d.key:self.fake for d,_ in self.registry.descriptors()})
        self.constraints=_Constraints();self.constraints.registered={d.key for d,_ in self.registry.descriptors()}
        self.reopen()
    @property
    def state(self):return self.runtime.subject_states.load(self.runtime.descriptor.subject_id)
    @property
    def external_calls(self):return self.fake.execute_calls
    def registry_bytes(self):return self.registry.registry_path.read_bytes()
    def control_change(self,**changes):
        value=read_json(self.control);value.update(changes);atomic_write_json(self.control,value)
    def revoke(self):self.control_change(permission_allowed=False)
    def mode(self,value):self.control_change(mode=value)
    def reopen(self):
        self.provider=_Thinking(self)
        def factory(**kwargs):
            self.core=build_continuity_core(**kwargs,environment='TEST',constraints=self.constraints,
                capabilities=(),claim_resolver=CoreClaims(),permission_policy=self.base.permission,
                external_capabilities=self.external if self.feature else None,**self.core_options)
            return self.core
        self.app=build_local_integration_app(self.runtime.data_root,clock=self.runtime.clock.now,thinking_provider=self.provider,
            continuity_core_factory=factory,contract_validator=SandboxContractValidator(),result_factory=SandboxFirstRoundResultFactory(),
            available_permissions=('subject_state:update','memory:request','test:lookup'))
        return self.app
    def disable_feature(self):
        self.feature=False
        # Legacy path uses the original P09 fixture, without installing P16 ports.
        self.app=self.base.app;self.core=self.base.core
    def request(self):return self.base.request()
    def submit(self,request=None):
        request=request or self.request();value=self.app.adapter.submit(request)
        self.last_request=request
        operation=self.app.ledger.load_operation(request['requestId'])
        if operation and operation.domain_progress:self.last_context=operation.domain_progress.perception.continuity_context
        return value
    def next_round(self):
        self.runtime.clock.advance(timedelta(seconds=1));return self.submit()

    def lifecycle(self,operation):
        """Explicit TEST confirmation through the existing P15/Evolution service."""
        from .p15_subject_fixture import TestLifecycleAuthority
        from continuity_engine.domain.subject_lifecycle import LifecycleCommand,LifecyclePolicy
        from continuity_engine.domain.action import PermissionGrant
        from continuity_engine.services.action_service import ActionService
        from continuity_engine.services.action_permissions import InMemoryPermissionProvider
        from continuity_engine.services.subject_lifecycle_service import SubjectLifecycleService
        authority=TestLifecycleAuthority();now=self.runtime.clock.now();state=self.state
        command=LifecycleCommand('p16-lifecycle-'+str(state.revision),state.subject_id,'TEST',state.revision,now,
            'Explicit isolated P16 lifecycle test',operation,'OWNER')
        token=authority.confirm(command,'p16-test-owner',now)
        grant=PermissionGrant('subject.lifecycle',state.subject_id,now,scopes=[state.subject_id])
        service=SubjectLifecycleService(self.core.subject_states,environment='TEST',authority=authority,
            action_gate=ActionService(InMemoryPermissionProvider([grant]),None),clock=self.runtime.clock.now,
            policy=LifecyclePolicy(archive_configured=True,delete_retention_seconds=0,allow_test_logical_delete=True))
        return service.submit(command,token)

    def replace_memory_connector(self):
        old=self.descriptors[0];new=replace(old,version='v2',capability_ref='external.memory.v2')
        self.external.register(new,expected_revision=self.registry.revision)
        self.registry.disable(old.key,expected_revision=self.registry.revision)
        self.external.providers[new.key]=self.fake;self.constraints.registered.add(new.key);self.reopen()
        return new


def golden_phase(root,phase):
    """A separate process opens persisted P01 state; no chat-history reconstruction."""
    from .sandbox import P01SandboxManager
    from continuity_engine.domain.errors import IntegrationExecutionError
    root=_validate_fixture_root(Path(root));manifest=root/'golden-manifest.json'
    if phase=='prepare':
        f=P16Fixture(root);request=f.request();before=f.state.to_dict()
        def fault(point):
            if point=='after_adapter_before_result':raise RuntimeError('P16_GOLDEN_INTERRUPTION')
        f.core.fault=fault
        try:f.submit(request)
        except IntegrationExecutionError as exc:
            if not isinstance(exc.__cause__,RuntimeError) or str(exc.__cause__)!='P16_GOLDEN_INTERRUPTION':raise
        else:raise AssertionError('expected injected interruption')
        assert f.external_calls==1 and len(f.fake.facts())==1
        atomic_write_json(manifest,{'sandbox_id':f.runtime.descriptor.sandbox_id,'request':request,'state':before})
        return {'phase':phase,'fact_count':1,'interruption':'after_adapter_before_result','new_calls':1}
    saved=read_json(manifest);manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    f=P16Fixture(root,manager=manager,runtime=manager.open_runtime(saved['sandbox_id']))
    if phase=='resume':
        f.submit(saved['request']);assert f.external_calls==0
        f.next_round();assert any(x.source_type=='external_candidate' for x in f.last_context.composition.snapshot.fragments)
        assert f.state.to_dict()==saved['state']
        saved['completed_request']=f.last_request;atomic_write_json(manifest,saved)
        return {'phase':phase,'restored_without_execute':True,'consumed_candidate':True,'new_calls':f.external_calls}
    if phase!='replace-revoke':raise ValueError('unknown golden phase')
    replacement=f.replace_memory_connector();f.next_round()
    assert f.core.last_action.requests[0].step.target==replacement.key
    f.next_round();assert any(x.source_type=='external_candidate' for x in f.last_context.composition.snapshot.fragments)
    completed=f.last_request;f.revoke();calls=f.external_calls
    f.submit(completed);assert f.external_calls==calls and f.external.cached()==()
    try:f.next_round()
    except IntegrationExecutionError:pass
    else:raise AssertionError('revocation must refuse new query')
    assert f.external_calls==calls and f.state.to_dict()==saved['state']
    return {'phase':phase,'replacement':replacement.key,'historical_replay':True,'revoked_new_execution':True,'new_calls':calls}


def run_golden(root):
    import subprocess,sys,time,os
    records=[]
    for phase in ('prepare','resume','replace-revoke'):
        command=[sys.executable,'-m','continuity_engine.testing.p16_provider_fixture','--phase',phase,'--root',str(root)]
        start=__import__('time').perf_counter()
        try:
            completed=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=60,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        except subprocess.TimeoutExpired as exc:
            def decoded(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
            print(json.dumps({'phase':phase,'command':command,'exit_code':None,'interruption':'TimeoutExpired',
                'stdout':decoded(exc.stdout),'stderr':decoded(exc.stderr),'seconds':round(time.perf_counter()-start,3)},ensure_ascii=False))
            raise
        record={'phase':phase,'command':command,'exit_code':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr,
                'seconds':round(time.perf_counter()-start,3)}
        records.append(record);print(json.dumps(record,ensure_ascii=False))
        if completed.returncode:raise AssertionError('P16 Golden child failed: '+phase)
    return records


if __name__=='__main__':
    import argparse,tempfile
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('prepare','resume','replace-revoke'));parser.add_argument('--root');parser.add_argument('--golden',action='store_true')
    options=parser.parse_args()
    if options.phase:
        if not options.root:parser.error('--phase requires --root')
        print(json.dumps(golden_phase(options.root,options.phase),ensure_ascii=False))
    elif options.golden:
        with tempfile.TemporaryDirectory(prefix='p16-golden-') as directory:run_golden(directory)
    else:parser.error('choose --golden or --phase')
