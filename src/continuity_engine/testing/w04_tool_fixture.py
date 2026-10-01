"""W04-3 local discovery + real P08/P16/P17/W04-2 chains, no real accounts."""
from dataclasses import asdict, replace
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest, ReceiptQuery
from continuity_engine.domain.action_planning import ActionChoice, digest
from continuity_engine.domain.environment_access import DiscoveryState
from continuity_engine.domain.execution import BlastRadius, ExecutionError, WorldCapability
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.external_capabilities import ExternalCandidate
from continuity_engine.domain.integration_results import format_contract_datetime as stamp
from continuity_engine.domain.temporary_tools import ToolOffer, ToolLease, ToolCommand
from continuity_engine.services.action_planning_service import ActionPlanningService
from continuity_engine.services.continuity_core_service import _CurrentConstraints
from continuity_engine.services.continuity_core_runtime import build_continuity_core
from continuity_engine.services.execution_service import ExecutionService
from continuity_engine.services.temporary_tool_service import TemporaryToolService
from continuity_engine.services.external_capability_service import ExternalCapabilityService
from continuity_engine.storage.json_execution_outbox import JsonExecutionOutbox
from continuity_engine.interfaces.local_integration_app import build_local_integration_app
from .w04_device_fixture import W04DeviceFixture
from .p16_provider_fixture import P16Fixture
from .p08_action_fixture import TestChoiceProducer, _validate_fixture_root
from .p09_core_fixture import CoreClaims
from .p17_execution_fixture import _Thinking
from .interaction import SandboxContractValidator, SandboxFirstRoundResultFactory
from .persistence import atomic_write_json, read_json


class SimulatedConnections(JsonExecutionOutbox):
    """External simulator state, not Engine's authority; facts verified by E5-A."""
    def __init__(self,root,subject):
        root=_validate_fixture_root(Path(root))
        super().__init__(root,subject_id=subject,environment='TEST')
        self.path=root/'connections.json'
        self._verified_document=None
    def empty(self):
        return dict(revision=0,subject_id=self.subject_id,environment='TEST',connections={},facts=[])
    def load(self):
        self._safe()
        if not self.path.exists(): return self.empty()
        try:
            current=self.path.read_bytes()
            if self._verified_document is not None and self._verified_document[0]==current:
                return deepcopy(self._verified_document[1])
            e=json.loads(current.decode('utf8'));d=e['document']
            if set(e)!={'document','hash'} or e['hash']!=digest(d) or set(d)!=set(self.empty()): raise ValueError()
            if (d['subject_id'],d['environment'])!=(self.subject_id,'TEST'): raise ValueError()
            ids=[]
            for row in d['facts']:
                receipt=ActionReceipt.from_dict(row['receipt']);ids.append(receipt.capability_request_id)
                if receipt.output_hash!=digest(row['output']): raise ValueError()
            if len(ids)!=len(set(ids)): raise ValueError()
            self._verified_document=(current,deepcopy(d))
            return d
        except Exception: raise ExecutionError('FAKE_CONNECTION_CORRUPT') from None


class SimulatedToolPort:
    adapter_id='w04-tool-adapter';version='v1';world='TEST';environment='TEST'
    def __init__(self,root,subject,clock):
        self.store=SimulatedConnections(root,subject);self.subject_id=subject;self.clock=clock
        self.mode='success';self.online=True;self.before=None;self.calls=0;self.receipt_hook=None
        self.routes={'API','UI'}
    def available(self,offer): return self.online and offer.route in self.routes and offer.version==self.version
    def connected(self,connection,offer):
        d=self.store.load()['connections'].get(connection)
        return bool(self.online and d and d['active'] and d['offer_hash']==digest(offer.to_dict()))
    def query(self,r):
        if (r.subject_id,r.choice.environment,r.adapter_id)!=(self.subject_id,'TEST',self.adapter_id):
            raise ExecutionError('FAKE_TOOL_BINDING')
        if self.mode=='unknown': return ReceiptQuery.UNKNOWN
        for row in self.store.load()['facts']:
            fact=ActionReceipt.from_dict(row['receipt'])
            if fact.capability_request_id==r.capability_request_id:
                fact.validate_request(r)
                return self.receipt_hook(fact) if self.receipt_hook else fact
        return ReceiptQuery.NOT_EXECUTED
    def execute(self,r,c,offer,guard):
        self.calls+=1
        if self.before: self.before()
        with self.store.transaction() as d:
            fact=self.query(r)
            if isinstance(fact,ActionReceipt): return fact
            if fact is not ReceiptQuery.NOT_EXECUTED: raise ExecutionError('FAKE_TOOL_UNKNOWN')
            guard()
            connection=c.connection_request_id or r.capability_request_id
            if self.mode=='before_failure': raise OSError('SYNTHETIC_TOOL_IO')
            remaining=[];status='FAILED'
            if self.mode!='terminal':
                if c.operation=='connect':
                    if connection in d['connections']: raise ExecutionError('FAKE_TOOL_CONNECTION_DUPLICATE')
                    d['connections'][connection]=dict(active=True,offer_hash=digest(offer.to_dict()),
                        temporary_files={'description':'TEST downloaded reference','session':'TEST ephemeral state'},credential_reference=True)
                    status='CONNECTED'
                elif c.operation=='verify':
                    status='VERIFIED' if self.connected(connection,offer) else 'FAILED'
                else:
                    entry=d['connections'].get(connection)
                    if entry is None:
                        status='CLOSED'
                    elif self.mode=='partial_cleanup':
                        entry['active']=False
                        entry['temporary_files'].pop('description',None)
                        remaining=['temporary_files','credential_reference'];status='PARTIAL'
                    else:
                        entry['active']=False
                        entry['temporary_files'].clear();entry['credential_reference']=False;status='CLOSED'
            content=dict(operation=c.operation,connection_id=connection,status=status,remaining=remaining,
                authority='SIMULATED_CONNECTION_OBSERVATION')
            payload=dict(request_id=r.capability_request_id,request_hash=r.request_hash,world='TEST',
                asset=r.step.target,kind='temporary_connection',content=json.dumps(content,sort_keys=True))
            fact=ActionReceipt('receipt:'+r.idempotency_key[7:],r.capability_request_id,r.request_hash,self.adapter_id,
                self.subject_id,'TEST',r.step_id,'FAILED_TERMINAL' if status=='FAILED' else 'SUCCEEDED',0,0,
                stamp(self.clock()),digest(payload))
            d['facts'].append(dict(receipt=fact.to_dict(),output=payload));self.store.save(d)
            if self.mode=='lost_response': raise OSError('SYNTHETIC_TOOL_RESPONSE_LOST')
            return fact
    def read_result(self,r):
        return next(row['output'] for row in self.store.load()['facts'] if row['receipt']['capability_request_id']==r.capability_request_id)


class W04ToolFixture(W04DeviceFixture):
    def __init__(self,root,*,runtime=None,manager=None):
        self._tool_ready=False
        super().__init__(root,runtime=runtime,manager=manager,include_body=False)
        self.discovery=P16Fixture(root,runtime=self.runtime,manager=self.manager)
        self.tool_port=SimulatedToolPort(self.runtime.data_root/'worlds'/'tools',self.state.subject_id,self.runtime.clock.now)
        self.control_path=self.runtime.data_root/'fixture/tool-grants.json'
        if not self.control_path.exists():
            atomic_write_json(self.control_path,dict(login=True,scope=True,revoked=False,cleanup=True,
                budget=10,grant='grant:test:1',paused=False,view=True))
        self.dependencies_available=('local:device',)
        external=ExternalCapabilityService(self.discovery.registry,broker=self.discovery.broker,
            permissions=self.discovery.permissions,providers=self.discovery.external.providers)
        self.tools=TemporaryToolService(external=external,access=self.access,port=self.tool_port,
            authorize=self.authorize_tool,dependencies=lambda offer:self.dependencies_available,clock=self.runtime.clock.now,
            authorize_view=lambda *a:read_json(self.control_path)['view'],control=lambda:not read_json(self.control_path)['paused'],
            authorize_action=lambda request,lease,offer,**kw: request.capability_type in {
                'device.type','device.query','device.locate','device.scroll'} and request.step.target==offer.attachment.software_id)
        self.device.connection_guard=self.tools
        self.routes=(*self.routes,*(WorldCapability('tool.'+op,'v1',self.state.subject_id,'TEST','TEST',
            'asset:tool-port',self.tool_port.adapter_id,'credential:p17:test',cost=0,max_output_bytes=8192,max_attempts=3)
            for op in ('connect','verify','close')))
        self.execution=ExecutionService(self.outbox,routes=self.routes,
            adapters={self.fake.adapter_id:self.device,self.tool_port.adapter_id:self.tools},boundary=self.boundary,broker=self.broker,
            limits=BlastRadius(requests=64,credits=32,messages=32,storage_bytes=1000000))
        self.tools.execution=self.execution
        old_capacity=self.boundary.capacity
        self.boundary.capacity=lambda route,request,limits: True if route.capability_ref.startswith('tool.') else old_capacity(route,request,limits)
        self._tool_ready=True;self.reopen()

    def authorize_tool(self,lease,offer,*,at,purpose):
        c=read_json(self.control_path)
        if purpose=='cleanup': return () if c['cleanup'] else ('REVOKED',)
        if c['revoked']: return ('REVOKED',)
        if not c['login']: return ('LOGIN',)
        if not c['scope'] or lease.grant_ref!=c['grant']: return ('NEW_SCOPE',)
        if lease.test_budget>c['budget']: return ('BUDGET',)
        if lease.credential_ref!='credential:temporary:test': return ('CREDENTIAL',)
        return ()

    def change(self,**kw):
        d=read_json(self.control_path);d.update(kw);atomic_write_json(self.control_path,d)

    def reopen(self):
        if not getattr(self,'_tool_ready',False): return super().reopen()
        self.provider=_Thinking(self)
        def factory(**kw):
            self.core=build_continuity_core(**kw,environment='TEST',constraints=self.constraints,
                capabilities=tuple(b for b in self.base.core.capabilities if b.capability=='silence'),claim_resolver=CoreClaims(),
                permission_policy=self.base.permission,execution=self.execution,external_capabilities=self.tools.external,
                context_budget=ContextBudget(token_limit=2048))
            return self.core
        self.app=build_local_integration_app(self.runtime.data_root,clock=self.runtime.clock.now,thinking_provider=self.provider,
            continuity_core_factory=factory,contract_validator=SandboxContractValidator(),result_factory=SandboxFirstRoundResultFactory(),
            available_permissions=('subject_state:update','memory:request','test:lookup','test:execute','action:silence'))
        return self.app

    def discover(self,*,route='API',name='one',message=None):
        item=replace(self.attachment(),attachment_id='temporary:'+name,state=DiscoveryState.DISCOVERED)
        offer=ToolOffer('tool:'+name,'v1','history.lookup',route,('local:device',),item)
        text=json.dumps(offer.to_dict(),separators=(',',':'))
        self.discovery.query='skill:find history lookup tool'
        self.discovery.fake.candidate_hook=lambda c:replace(c,content=text,content_hash=digest(text),source_id='offer:'+name)
        result=self.discovery.submit(message)
        request=next(r for r in self.discovery.core.last_action.requests if r.capability_type.startswith('external.'))
        self.last_request=self.discovery.last_request;self.last_context=self.discovery.last_context
        return request.capability_request_id,offer,result

    def lease(self,discovery,offer,*,mode='SINGLE',seconds=120,budget=5):
        return ToolLease(discovery,'offer:'+offer.tool_id.split(':')[1],digest(offer.to_dict()),offer.purpose,'device:read',
            'credential:temporary:test',mode,stamp(self.runtime.clock.now()+timedelta(seconds=seconds)),budget,'grant:test:1')

    def prepare_tool(self,command,*,decision):
        step=self.tools.step(command);return self.prepare_step(step,decision)

    def prepare_step(self,step,decision):
        snapshot=self.last_context.composition.snapshot;now=self.runtime.clock.now()
        choice=ActionChoice(decision,'p08-test-thinking-v1',self.state.subject_id,'TEST',snapshot.snapshot_hash,snapshot.source_revision,
            tuple(f.fragment_id for f in snapshot.fragments),'ACTION_INTENT',(step,),stamp(now),stamp(now+timedelta(minutes=2)))
        producer=TestChoiceProducer();producer.register(choice)
        planner=ActionPlanningService(coordination=self.core.coordination,action_gate=self.core.action_gate,producer=producer,
            constraints=_CurrentConstraints(self.core,self.last_context),capabilities=self.core.capabilities,
            clock=self.runtime.clock.now,subject_id=self.state.subject_id,environment='TEST')
        binding=planner.capabilities[step.capability]
        request=InternalActionRequest(choice,step.step_id,None,binding.adapter.adapter_id,binding.canonical_hash())
        binding.adapter.validate_request_material(request)
        self.constraints.confirmed_ids.add(request.idempotency_key)
        self.core.coordination.ensure_action_request(request)
        self.last_planning=(planner,choice,self.last_context.composition)
        return request,lambda retry=False:self.tools.run(planner,choice,self.last_context.composition,retry=retry)

    def action_factory(self,kind,parent,existing,reason):
        if existing is not None:
            planner=self.restore_dispatch(existing)
            return planner,existing.choice,self.last_context.composition
        lease=self.tools.command(parent).lease
        offer=self.tools.offer(lease,current=kind!='close')
        count=len(self.tools.related(parent.capability_request_id))
        decision='continue:'+kind+':'+parent.capability_request_id[-16:]+':'+str(count)
        if kind=='use':
            self.prepare_step(self.device.step(self.tool_command(offer,'type',text='TEST discovered tool task')),decision)
        else:
            self.prepare_tool(ToolCommand(kind,lease,parent.capability_request_id,reason),decision=decision)
        return self.last_planning

    def open_tool(self,*,mode='SINGLE',name='one',route='API',seconds=120,budget=5):
        discovery,offer,_=self.discover(name=name,route=route)
        lease=self.lease(discovery,offer,mode=mode,seconds=seconds,budget=budget)
        connect,run=self.prepare_tool(ToolCommand('connect',lease),decision='connect:'+name);run()
        verify,run=self.prepare_tool(ToolCommand('verify',lease,connect.capability_request_id),decision='verify:'+name);run()
        self.tools.activate(verify.capability_request_id)
        return connect,verify,lease,offer

    def tool_command(self,offer,operation='query',**kw):
        from continuity_engine.domain.environment_access import AttachmentUse
        from continuity_engine.domain.device_operation import DeviceCommand
        item=offer.attachment.to_dict()
        use=AttachmentUse(**{k:item[k] for k in ('attachment_id','subject_id','environment','generation','host_id',
            'channel_id','software_id','device_id','account_id','session_id')},purpose='device.act',scope='device:read')
        return DeviceCommand('w04-device-v1',operation,kw.get('target','control:edit'),kw.get('text'),kw.get('amount'),
            asdict(self.scope()) if operation=='query' else None,self.device.observe(use))

    def close_tool(self,connection,lease,*,reason='COMPLETE',decision='close:one'):
        request,run=self.prepare_tool(ToolCommand('close',lease,connection.capability_request_id,reason),decision=decision)
        return request,run()


def recovery_phase(root,phase):
    from .sandbox import P01SandboxManager
    root=_validate_fixture_root(Path(root));manifest=root/'tool-recovery.json'
    if phase=='prepare':
        f=W04ToolFixture(root);rid,offer,_=f.discover();lease=f.lease(rid,offer)
        request,run=f.prepare_tool(ToolCommand('connect',lease),decision='process:connect')
        f.tool_port.mode='lost_response';result=run()
        assert result.status=='WAITING_CAPABILITY' and len(f.tool_port.store.load()['connections'])==1
        atomic_write_json(manifest,dict(sandbox_id=f.runtime.descriptor.sandbox_id,request=f.last_request,
            connection=request.capability_request_id,revision=f.state.revision))
        return dict(phase=phase,status='UNKNOWN',connections=1)
    saved=read_json(manifest)
    manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    f=W04ToolFixture(root,manager=manager,runtime=manager.open_runtime(saved['sandbox_id']))
    f.last_request=saved['request']
    f.last_context=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception.continuity_context
    result=f.tools.advance(saved['connection'],f.action_factory)
    assert result['state']=='CLOSED' and f.fake.effect_count==1 and f.fake.credits==1
    assert f.state.revision==saved['revision'] and f.discovery.external_calls==0 and not f.provider.inputs
    facts=f.tool_port.store.load()['facts']
    assert sum(json.loads(row['output']['content'])['operation']=='connect' for row in facts)==1
    return dict(phase=phase,status=result['state'],effects=f.fake.effect_count,credits=f.fake.credits,
        new_discovery=f.discovery.external_calls,new_models=len(f.provider.inputs),revision=f.state.revision)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    parser.add_argument('--phase',choices=('prepare','resume','replay'),required=True)
    args=parser.parse_args();print(json.dumps(recovery_phase(args.root,args.phase)))
