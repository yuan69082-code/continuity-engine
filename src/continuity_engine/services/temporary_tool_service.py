"""Temporary tool lifecycle projected from P16 and the ONE E5-A ledger.

No task, request, receipt or credential store here. Attachment registration is
rebuildable metadata. Hosts inject current grants/control, never tool documents.
"""
from dataclasses import replace
from datetime import timedelta
from functools import wraps
import json
import math

from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest, ReceiptQuery
from continuity_engine.domain.action_planning import ActionSpecification, digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.device_operation import DeviceCommand
from continuity_engine.domain.environment_access import Attachment, DiscoveryState, EnvironmentAccessError
from continuity_engine.domain.execution import ExecutionError
from continuity_engine.domain.temporary_tools import ToolCommand, ToolOffer


def _verified_reads(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        repository=self.execution.core.coordination._repository
        # Reuse the existing exact-current-byte scope, NOT cached grants,
        # receipts, provider responses or across-request authorization.
        if repository._capability_read_scope.get() is not None:
            return method(self,*args,**kwargs)
        with repository._verified_capability_reads():
            return method(self,*args,**kwargs)
    return call


class TemporaryToolService:
    def __init__(self, *, external, access, port, authorize, dependencies, clock, authorize_view,
                 authorize_action, control=lambda: True, cleanup_retry_seconds=None):
        # Infrastructure pacing, not a lifetime attempt limit. Default to the
        # existing P18 retry interval; no usage reservation or clock is reset.
        from continuity_engine.domain.persistent_runtime import RuntimePolicy
        if cleanup_retry_seconds is None:
            cleanup_retry_seconds=RuntimePolicy().retry_seconds
        if (type(cleanup_retry_seconds) not in (int,float)
                or not math.isfinite(cleanup_retry_seconds) or cleanup_retry_seconds<=0):
            raise ExecutionError('TOOL_CLEANUP_RETRY_POLICY_INVALID')
        self.cleanup_retry_seconds=cleanup_retry_seconds
        self.external,self.access,self.port=external,access,port
        self.authorize,self.dependencies,self.clock=authorize,dependencies,clock
        self.authorize_view,self.control=authorize_view,control
        self.authorize_action=authorize_action
        self.subject_id,self.environment=access.repository.subject_id,access.repository.environment
        self.adapter_id,self.version,self.world=port.adapter_id,port.version,port.world
        self.execution=None

    @staticmethod
    def _port(code, function, *args, **kwargs):
        try: return function(*args,**kwargs)
        except Exception: raise ExecutionError(code) from None

    def _requests(self):
        # Read typed immutable originals with the repository's full validation.
        # No shadow list of operation identities is maintained.
        return self.execution.core.coordination._repository._load_capability_document(
            _projection=lambda requests, attempts: tuple(r for r in requests
                if isinstance(r,InternalActionRequest)
                and (r.subject_id,r.choice.environment)==(self.subject_id,self.environment)))

    def _material(self,value):
        self.execution.validate_input_material(value)

    @_verified_reads
    def candidates(self, discovery_request_id, *, current=True):
        request=self.execution.request(discovery_request_id)
        if request is None or not request.capability_type.startswith('external.'):
            raise ExecutionError('TOOL_DISCOVERY_ENTRY_MISSING')
        if (request.subject_id,request.choice.environment)!=(self.subject_id,self.environment):
            raise ExecutionError('TOOL_DISCOVERY_BOUNDARY')
        result=self.external._verified(request,consume=current)
        if result is None or result.status!='AVAILABLE': raise ExecutionError('TOOL_DISCOVERY_UNAVAILABLE')
        offers=[]
        for candidate in result.candidates:
            try: offer=ToolOffer.from_dict(json.loads(candidate.content))
            except Exception: raise ExecutionError('TOOL_OFFER_UNVERIFIED') from None
            self._material(offer.to_dict())
            if (offer.attachment.subject_id,offer.attachment.environment)!=(self.subject_id,self.environment):
                raise ExecutionError('TOOL_OFFER_BOUNDARY')
            offers.append((candidate,offer))
        return tuple(offers)

    def offer(self, lease, *, current=True):
        pairs=self.candidates(lease.discovery_request_id,current=current)
        pair=next(((c,o) for c,o in pairs if c.source_id==lease.source_id),None)
        if pair is None or digest(pair[1].to_dict())!=lease.offer_hash:
            raise ExecutionError('TOOL_OFFER_CHANGED')
        return pair[1]

    def step(self, command, *, step_id='step-0', dependencies=()):
        return ActionSpecification(step_id,command.capability,'asset:tool-port',command.hash,
                                   dependencies,command.to_dict())

    def command(self, request):
        command=ToolCommand.from_dict(request.step.input_payload)
        if (command.capability,command.hash,request.subject_id,request.choice.environment,request.adapter_id)!=(
                request.capability_type,request.step.argument_hash,self.subject_id,self.environment,self.adapter_id):
            raise ExecutionError('TOOL_REQUEST_BINDING')
        if self.execution.request(request.capability_request_id)!=request:
            raise ExecutionError('TOOL_LEDGER_BINDING')
        if command.connection_request_id is not None:
            parent=self.execution.request(command.connection_request_id)
            if parent is None: raise ExecutionError('TOOL_CONNECTION_MISSING')
            old=ToolCommand.from_dict(parent.step.input_payload)
            if old.operation!='connect' or old.lease!=command.lease or parent.subject_id!=request.subject_id or parent.choice.environment!=request.choice.environment:
                raise ExecutionError('TOOL_CONNECTION_BINDING')
        return command

    def conditions(self, command):
        """Read current missing conditions; never asks for all-step approval."""
        offer=self.offer(command.lease,current=False)
        if self._port('TOOL_CONTROL_UNAVAILABLE',self.control) is not True:
            return ('CONTROL_PAUSED_OR_STOPPED',)
        self.execution.core.subject_states.require_active(self.subject_id,self.environment)
        lease=command.lease
        if lease.purpose!=offer.purpose or lease.scope not in offer.attachment.read_scopes:
            return ('SCOPE_MISMATCH',)
        document=self.access.repository.load();item=offer.attachment
        if (item.host_id,item.generation)!=(document['active_host'],document['generation']):
            return ('BINDING_NOT_CURRENT',)
        if command.operation!='close' and self.clock()>=parse_capability_datetime(lease.expires_at):
            return ('EXPIRED',)
        if command.operation!='close':
            from continuity_engine.domain.external_capabilities import ExternalCapabilityError
            try: self.offer(lease,current=True)
            except ExternalCapabilityError as exc:
                if str(exc) not in {'EXTERNAL_RESULT_EXPIRED','EXTERNAL_CONNECTOR_REVOKED',
                    'EXTERNAL_CONNECTOR_EXPIRED','EXTERNAL_PERMISSION_DENIED','EXTERNAL_CREDENTIAL_REFERENCE_DENIED'}:
                    raise
                return ('SOURCE_NOT_CURRENT',)
            if (not item.enabled or not parse_capability_datetime(item.valid_from)<=self.clock()<parse_capability_datetime(item.expires_at)):
                return ('BINDING_NOT_CURRENT',)
        # Grant source is a trusted control port, not the discovery description.
        missing=self._port('TOOL_AUTHORIZATION_UNAVAILABLE',self.authorize,lease,offer,
            at=self.clock(),purpose='cleanup' if command.operation=='close' else 'use')
        allowed={'LOGIN','NEW_SCOPE','BUDGET','REVOKED','CREDENTIAL','PURCHASE_NOT_AUTHORIZED'}
        if not isinstance(missing,tuple) or any(x not in allowed for x in missing):
            raise ExecutionError('TOOL_AUTHORIZATION_INVALID')
        if missing: return missing
        if command.operation!='close':
            available=self._port('TOOL_DEPENDENCY_UNAVAILABLE',self.dependencies,offer)
            if not isinstance(available,tuple) or any(x not in offer.dependencies for x in available):
                raise ExecutionError('TOOL_DEPENDENCY_INVALID')
            if set(offer.dependencies)-set(available): return ('DEPENDENCY_MISSING',)
        if self._port('TOOL_ROUTE_UNAVAILABLE',self.port.available,offer) is not True:
            return ('CAPABILITY_UNAVAILABLE',)
        return ()

    def _verified_result(self, request):
        command=self.command(request)
        fact=self._port('TOOL_QUERY_UNAVAILABLE',self.port.query,request)
        if isinstance(fact,ActionReceipt):
            self._material(fact.to_dict());fact.validate_request(request)
            payload=self._port('TOOL_RESULT_UNAVAILABLE',self.port.read_result,request)
            self._material(payload)
            try:
                value=json.loads(payload['content'])
                expected_connection=command.connection_request_id or request.capability_request_id
                if (set(payload)!={'request_id','request_hash','world','asset','kind','content'}
                        or (payload['request_id'],payload['request_hash'],payload['asset'],payload['world'])!=(
                            request.capability_request_id,request.request_hash,request.step.target,self.world)
                        or digest(payload)!=fact.output_hash
                        or set(value)!={'operation','connection_id','status','remaining','authority'}
                        or (value['operation'],value['connection_id'],value['authority'])!=(
                            command.operation,expected_connection,'SIMULATED_CONNECTION_OBSERVATION')
                        or value['status'] not in {'CONNECTED','VERIFIED','CLOSED','PARTIAL','FAILED'}
                        or not isinstance(value['remaining'],list)
                        or any(x not in {'connection','temporary_files','credential_reference'} for x in value['remaining'])
                        or (value['status']=='CLOSED' and value['remaining'])
                        or (fact.status=='FAILED_TERMINAL')!=(value['status']=='FAILED')
                        or fact.effect_count!=0):
                    raise ValueError()
                statuses={'connect':{'CONNECTED','FAILED'},'verify':{'VERIFIED','FAILED'},'close':{'CLOSED','PARTIAL','FAILED'}}
                if value['status'] not in statuses[command.operation]: raise ValueError()
            except Exception: raise ExecutionError('TOOL_RESULT_BINDING') from None
            return fact,payload
        return (ReceiptQuery.NOT_EXECUTED if fact is ReceiptQuery.NOT_EXECUTED else ReceiptQuery.UNKNOWN),None

    def query(self, request):
        return self._verified_result(request)[0]

    def read_result(self,request):
        fact,payload=self._verified_result(request)
        if not isinstance(fact,ActionReceipt): raise ExecutionError('TOOL_RESULT_UNKNOWN')
        return payload

    def _value(self,request):
        fact,payload=self._verified_result(request)
        return json.loads(payload['content']) if isinstance(fact,ActionReceipt) else None

    def related(self, connection_id):
        rows=[]
        for r in self._requests():
            if r.capability_type.startswith('tool.'):
                c=self.command(r)
                if r.capability_request_id==connection_id or c.connection_request_id==connection_id: rows.append(r)
        return tuple(rows)

    def _closed_or_pending(self,connection_id):
        return any(self.command(r).operation=='close' for r in self.related(connection_id))

    def __call__(self,request,*,purpose):
        return self.require_device(request,purpose=purpose)

    @_verified_reads
    def observe(self,use):
        """A read of the temporary tool is a current use, not a history query."""
        matches=[]
        for r in self._requests():
            if r.capability_type=='tool.connect':
                c=self.command(r);o=self.offer(c.lease,current=False)
                if o.attachment.attachment_id==use.attachment_id: matches.append((r,c,o))
        if len(matches)!=1: raise EnvironmentAccessError('TOOL_CONNECTION_REQUIRED')
        r,c,o=matches[0]
        if (use.subject_id,use.environment,use.scope)!=(self.subject_id,self.environment,c.lease.scope):
            raise EnvironmentAccessError('W04_SCOPE_DENIED')
        if (self.conditions(c) or self._closed_or_pending(r.capability_request_id)
                or self._port('TOOL_CONNECTION_UNAVAILABLE',self.port.connected,r.capability_request_id,o) is not True):
            raise EnvironmentAccessError('W04_REVOKED')
        if not any(self.command(v).operation=='verify' and (value:=self._value(v)) is not None
                and value['status']=='VERIFIED' for v in self.related(r.capability_request_id)):
            raise EnvironmentAccessError('TOOL_VERIFICATION_REQUIRED')

    @_verified_reads
    def execute(self, request):
        command=self.command(request);fact=self.query(request)
        if isinstance(fact,ActionReceipt): return fact
        if fact is not ReceiptQuery.NOT_EXECUTED: raise ExecutionError('TOOL_RESULT_UNKNOWN')
        offer=self.offer(command.lease,current=command.operation!='close')
        def guard():
            self.execution.current(request,self.execution.route_for(request),'execute')
            missing=self.conditions(command)
            if missing: raise ExecutionError('TOOL_'+missing[0])
            connection=command.connection_request_id or request.capability_request_id
            if command.operation=='connect':
                if self._closed_or_pending(connection):
                    raise ExecutionError('TOOL_ENDING')
                for old in self._requests():
                    if old.capability_type=='tool.connect' and old.capability_request_id!=connection:
                        c=self.command(old)
                        if self.offer(c.lease,current=False).attachment.attachment_id==offer.attachment.attachment_id:
                            raise ExecutionError('TOOL_CONNECTION_ID_REUSE_FORBIDDEN')
            else:
                parent=self.execution.request(connection)
                original=self._value(parent)
                if command.operation=='close':
                    # A proven unexecuted or terminal failed connection can be
                    # cancelled. The native close still checks/removes actual
                    # resources under its original transaction and returns a
                    # verified receipt. UNKNOWN never means absent resources.
                    if self.query(parent) is ReceiptQuery.UNKNOWN:
                        raise ExecutionError('TOOL_CONNECTION_UNCONFIRMED')
                elif original is None or original['status']!='CONNECTED':
                    raise ExecutionError('TOOL_CONNECTION_UNCONFIRMED')
            if command.operation=='verify' and self._closed_or_pending(connection):
                raise ExecutionError('TOOL_ENDING')
            if command.operation=='close':
                for old in self.related(connection):
                    if self.command(old).operation!='close' or old==request: continue
                    old_fact=self.query(old)
                    if old_fact is ReceiptQuery.UNKNOWN: raise ExecutionError('TOOL_CLEANUP_UNKNOWN')
                    if isinstance(old_fact,ActionReceipt) and self._value(old)['status']=='CLOSED':
                        raise ExecutionError('TOOL_ALREADY_CLOSED')
        guard()
        fact=self._port('TOOL_RESPONSE_UNKNOWN',self.port.execute,request,command,offer,guard)
        verified=self.query(request)
        if not isinstance(verified,ActionReceipt) or verified!=fact: raise ExecutionError('TOOL_RESULT_UNKNOWN')
        return fact

    @_verified_reads
    def activate(self, verify_request_id):
        """Rebuild attachment admission from verified original facts, with CAS."""
        request=self.execution.request(verify_request_id);command=self.command(request)
        fact=self._value(request)
        if command.operation!='verify' or fact is None or fact['status']!='VERIFIED':
            raise ExecutionError('TOOL_VERIFICATION_REQUIRED')
        if self.conditions(command) or self._closed_or_pending(command.connection_request_id):
            raise ExecutionError('TOOL_NOT_CURRENT')
        offer=self.offer(command.lease)
        if self._port('TOOL_CONNECTION_UNAVAILABLE',self.port.connected,command.connection_request_id,offer) is not True:
            raise ExecutionError('TOOL_DISCONNECTED')
        attachment=replace(offer.attachment,state=DiscoveryState.CONNECTED)
        self.access.repository.register(attachment,expected_revision=self.access.repository.load()['revision'])
        return attachment

    @_verified_reads
    def require_device(self, request, *, purpose):
        """Optional W04-2 final gate; the same lease covers API and UI routes."""
        use=DeviceCommand.from_dict(request.step.input_payload).observation.use
        matches=[]
        for r in self._requests():
            if r.capability_type=='tool.connect':
                c=self.command(r);offer=self.offer(c.lease,current=False)
                if offer.attachment.attachment_id==use.attachment_id: matches.append((r,c,offer))
        if len(matches)!=1: raise EnvironmentAccessError('TOOL_CONNECTION_REQUIRED')
        parent,command,offer=matches[0];connection=parent.capability_request_id
        def reject():
            raise EnvironmentAccessError('W04_REVOKED')
        if self.conditions(command) or self._closed_or_pending(connection): reject()
        if self._port('TOOL_ACTION_AUTHORIZATION_UNAVAILABLE',self.authorize_action,request,command.lease,
                offer,at=self.clock(),purpose=purpose) is not True: reject()
        if self._port('TOOL_CONNECTION_UNAVAILABLE',self.port.connected,connection,offer) is not True: reject()
        verified=any(self.command(r).operation=='verify' and (value:=self._value(r)) is not None
                     and value['status']=='VERIFIED' for r in self.related(connection))
        if not verified: reject()
        if purpose=='execute':
            credits=0;used=False
            for old in self._requests():
                if not old.capability_type.startswith('device.'): continue
                prior=DeviceCommand.from_dict(old.step.input_payload)
                if prior.observation.use.attachment_id!=use.attachment_id: continue
                fact=self.execution.query(old)
                if old.capability_request_id!=request.capability_request_id and fact is ReceiptQuery.UNKNOWN:
                    raise ExecutionError('TOOL_EFFECT_UNKNOWN')
                if isinstance(fact,ActionReceipt):
                    credits+=fact.test_credits
                    used=used or (fact.status=='SUCCEEDED' and old.capability_request_id!=request.capability_request_id)
            if command.lease.mode=='SINGLE' and used: raise ExecutionError('TOOL_SINGLE_USE_FINISHED')
            if credits+self.execution.routes[request.capability_type].cost>command.lease.test_budget:
                raise ExecutionError('RESOURCE_EXHAUSTED')

    @_verified_reads
    def inspect(self, connection_id):
        """Read-only projection. No activate, execute, cleanup, model or revision."""
        def view_gate():
            if self._port('TOOL_VIEW_UNAVAILABLE',self.authorize_view,self.subject_id,self.environment) is not True:
                raise ExecutionError('TOOL_VIEW_DENIED')
        view_gate();request=self.execution.request(connection_id)
        if request is None: raise ExecutionError('TOOL_CONNECTION_MISSING')
        command=self.command(request)
        if command.operation!='connect': raise ExecutionError('TOOL_CONNECTION_REFERENCE_REQUIRED')
        rows=[];state='CANDIDATE';remaining=[]
        for r in self.related(connection_id):
            fact=self.query(r);value=self._value(r) if isinstance(fact,ActionReceipt) else None
            rows.append(dict(request_id=r.capability_request_id,operation=self.command(r).operation,
                result=value['status'] if value else fact.value,receipt_hash=fact.canonical_hash() if value else None))
            if value and value['status'] in {'CONNECTED','VERIFIED'}: state=value['status']
            if self.command(r).operation=='close':
                state='CLOSED' if value and value['status']=='CLOSED' else 'PENDING_CLEANUP' if value or fact is ReceiptQuery.NOT_EXECUTED else 'CLEANUP_UNKNOWN'
                remaining=value['remaining'] if value else ['UNCONFIRMED']
        if any(r['operation']=='close' and r['result']=='CLOSED' for r in rows):
            state='CLOSED';remaining=[]
        if not any(r['operation']=='close' for r in rows):
            missing=self.conditions(command)
            if missing:
                ending=set(missing).intersection({'EXPIRED','REVOKED','SOURCE_NOT_CURRENT','BINDING_NOT_CURRENT'})
                state='PENDING_CLEANUP' if state!='CANDIDATE' and ending else 'WAITING_CONDITIONS'
            elif state=='CANDIDATE' and any(r['result']=='UNKNOWN' for r in rows): state='UNKNOWN'
        else: missing=()
        result=dict(connection_id=connection_id,mode=command.lease.mode,purpose=command.lease.purpose,
            scope=command.lease.scope,expires_at=command.lease.expires_at,state=state,
            missing=list(missing),remaining=remaining,steps=rows,authority='E5_A_FACT_PROJECTION')
        result['uses']=[]
        for use in self.uses(connection_id):
            fact=self.execution.query(use)
            result['uses'].append(dict(request_id=use.capability_request_id,capability=use.capability_type,
                status=fact.status if isinstance(fact,ActionReceipt) else fact.value,
                receipt_hash=fact.canonical_hash() if isinstance(fact,ActionReceipt) else None,
                test_credits=fact.test_credits if isinstance(fact,ActionReceipt) else None))
        view_gate();return result

    @_verified_reads
    def run(self, planner, choice, context, *, retry=False):
        """Use the existing action planner, preserving sealed identities on resume."""
        self.execution.prepare(planner,choice,context)
        run=planner.run(choice,context,retry=retry)
        self.execution.retain_pending(run)
        # UNKNOWN/wait is retained by E5-A/Outbox, not presented to the P17
        # verified-fact collector as if it carried a receipt.
        self.execution.collect(replace(run,results=tuple(
            result if result is not None and result.receipt is not None else None for result in run.results)))
        return run

    def uses(self, connection_id):
        command=self.command(self.execution.request(connection_id));offer=self.offer(command.lease,current=False)
        return tuple(r for r in self._requests() if r.capability_type.startswith('device.') and
            DeviceCommand.from_dict(r.step.input_payload).observation.use.attachment_id==offer.attachment.attachment_id)

    @_verified_reads
    def alternative(self, original_id, replacement_id):
        """Only a proven unexecuted technical failure may change transport."""
        old=self.execution.request(original_id);new=self.execution.request(replacement_id)
        a=self.command(old);b=self.command(new)
        if a.operation!='connect' or b.operation!='connect': raise ExecutionError('TOOL_ALTERNATIVE_KIND')
        if self.query(old) is not ReceiptQuery.NOT_EXECUTED: raise ExecutionError('TOOL_ALTERNATIVE_UNKNOWN')
        reasons=self.conditions(a)
        if not reasons or not set(reasons)<={'CAPABILITY_UNAVAILABLE','DEPENDENCY_MISSING'}:
            raise ExecutionError('TOOL_ALTERNATIVE_DENIED')
        x=self.offer(a.lease);y=self.offer(b.lease)
        if ((a.lease.purpose,a.lease.scope,a.lease.grant_ref,a.lease.test_budget,
             x.attachment.software_id,x.attachment.device_id,x.attachment.account_id,x.attachment.session_id)
                !=(b.lease.purpose,b.lease.scope,b.lease.grant_ref,b.lease.test_budget,
                   y.attachment.software_id,y.attachment.device_id,y.attachment.account_id,y.attachment.session_id)
                or self.conditions(b)):
            raise ExecutionError('TOOL_ALTERNATIVE_SCOPE')
        return self.execution.alternative(original_id,'CHANGE_ROUTE',replacement_id)

    @_verified_reads
    def advance(self, connection_id, action_factory):
        """One bounded continuation of a granted task; no per-step model calls.

        factory returns an ORIGINAL P08 planner/choice/context (the trusted
        producer and current Action Gate still validate them). Its use intent
        is formed by the host's existing subject chain, never by a catalogue.
        Subsequent calls reconstruct progress from E5-A, not an extra journal.
        """
        parent=self.execution.request(connection_id);command=self.command(parent)
        if command.operation!='connect': raise ExecutionError('TOOL_CONNECTION_REFERENCE_REQUIRED')
        state=self.inspect(connection_id)
        if state['state'] in {'CLOSED','CLEANUP_UNKNOWN','UNKNOWN'}: return state
        def perform(kind, existing=None, reason='TASK'):
            planner,choice,context=action_factory(kind,parent,existing,reason)
            if existing is not None:
                if choice!=existing.choice: raise ExecutionError('TOOL_RESUME_IDENTITY_CHANGED')
            elif len(choice.steps)!=1:
                raise ExecutionError('TOOL_CONTINUATION_STEP')
            elif kind=='use':
                use=DeviceCommand.from_dict(choice.steps[0].input_payload).observation.use
                if use.attachment_id!=self.offer(command.lease).attachment.attachment_id:
                    raise ExecutionError('TOOL_CONTINUATION_BINDING')
            else:
                expected=ToolCommand(kind,command.lease,connection_id,reason)
                if ToolCommand.from_dict(choice.steps[0].input_payload)!=expected:
                    raise ExecutionError('TOOL_CONTINUATION_BINDING')
            return self.run(planner,choice,context,retry=True)
        closes=[r for r in self.related(connection_id) if self.command(r).operation=='close']
        missing=self.conditions(command)
        if 'CONTROL_PAUSED_OR_STOPPED' in missing: return state
        if closes or (state['state']=='PENDING_CLEANUP' and missing):
            if closes:
                last=closes[-1];fact=self.query(last)
                if fact is ReceiptQuery.UNKNOWN: return state
                if fact is ReceiptQuery.NOT_EXECUTED: perform('close',last)
                else:
                    # The last automatic attempt starts a new pacing interval,
                    # derived from its verified receipt even after reopening.
                    # The first continuation of an explicit failed close keeps
                    # its existing immediate eligibility. Every invocation can
                    # perform at most ONE cleanup, regardless of lifetime count.
                    if self.command(last).reason=='RETRY_CLEANUP':
                        due=parse_capability_datetime(fact.completed_at)+timedelta(seconds=self.cleanup_retry_seconds)
                        if self.clock()<due:
                            state['cleanup_wait_reason']='BACKOFF'
                            state['cleanup_next_check_at']=due.isoformat()
                            return state
                    missing_cleanup=self.conditions(ToolCommand('close',command.lease,connection_id,'RETRY_CLEANUP'))
                    if missing_cleanup:
                        state['cleanup_wait_reason']='CURRENT_CONDITIONS'
                        state['cleanup_missing']=list(missing_cleanup)
                        return state
                    perform('close',reason='RETRY_CLEANUP')
            else: perform('close',reason='EXPIRE' if 'EXPIRED' in missing else 'REVOKE')
            return self.inspect(connection_id)
        if missing: return state
        fact=self.query(parent)
        if fact is ReceiptQuery.NOT_EXECUTED or isinstance(fact,ActionReceipt):
            perform('connect',parent);fact=self.query(parent)
        if not isinstance(fact,ActionReceipt) or fact.status!='SUCCEEDED': return self.inspect(connection_id)
        verifications=[r for r in self.related(connection_id) if self.command(r).operation=='verify']
        if not verifications: perform('verify')
        elif self.query(verifications[-1]) is ReceiptQuery.NOT_EXECUTED: perform('verify',verifications[-1])
        verifications=[r for r in self.related(connection_id) if self.command(r).operation=='verify']
        if not verifications or not self._value(verifications[-1]) or self._value(verifications[-1])['status']!='VERIFIED':
            return self.inspect(connection_id)
        self.activate(verifications[-1].capability_request_id)
        uses=self.uses(connection_id)
        if not uses: perform('use')
        elif self.execution.query(uses[-1]) is ReceiptQuery.NOT_EXECUTED: perform('use',uses[-1])
        uses=self.uses(connection_id)
        fact=self.execution.query(uses[-1]) if uses else ReceiptQuery.UNKNOWN
        if not isinstance(fact,ActionReceipt):
            state=self.inspect(connection_id);state['task_status']='UNKNOWN';return state
        if command.lease.mode=='SINGLE' or fact.status=='FAILED_TERMINAL':
            perform('close',reason='COMPLETE' if fact.status=='SUCCEEDED' else 'CANCEL')
        state=self.inspect(connection_id);state['task_status']=fact.status
        return state


class TemporaryToolRuntimeWork:
    """Optional P18 work adapter, using its ORIGINAL Scheduler and controls.

    E5-A remains the execution authority. Scheduler receipts only describe the
    computation opportunity; no external UNKNOWN is reset to unexecuted.
    """
    def __init__(self, native, tools, action_factory):
        self.native,self.tools,self.action_factory=native,tools,action_factory
    @property
    def guard(self): return self.native.guard
    @guard.setter
    def guard(self,value): self.native.guard=value
    def __getattr__(self,name): return getattr(self.native,name)
    def needs(self,at):
        from continuity_engine.domain.persistent_runtime import RuntimeNeed
        pending=[]
        for r in self.tools._requests():
            if r.capability_type!='tool.connect': continue
            status=self.tools.inspect(r.capability_request_id)
            if status['state']=='CLOSED': continue
            uses=self.tools.uses(r.capability_request_id)
            if uses and status['state']=='VERIFIED' and status['mode']!='SINGLE':
                fact=self.tools.execution.query(uses[-1])
                if isinstance(fact,ActionReceipt): continue
            prefix='temporary-tool-cleanup:' if status['state'] in {'PENDING_CLEANUP','CLEANUP_UNKNOWN'} else 'temporary-tool:'
            pending.append(RuntimeNeed(prefix+r.capability_request_id,'maintenance',
                parse_capability_datetime(r.choice.created_at),15))
        native=self.native.needs(at)
        # Already admitted work (including UNKNOWN, cancellation and completion)
        # stays in the ONE Scheduler. Re-submitting its first item cannot earn it
        # another admission slot at the expense of unseen native/tool needs.
        admitted={t.task_id for t in self.scheduler.list_tasks(
            subject_id=self.subject_id,environment=self.environment)}
        unseen=[n for n in (*native,*pending) if n.identity not in admitted]
        # Oldest due first gives existing maintenance, cognition and tool work a
        # finite admission opportunity without a private cursor or shadow queue.
        # Original Scheduler still owns dispatch, aging, resources and recovery.
        return tuple(sorted(unseen,key=lambda n:(n.due_at,-n.priority,n.identity))[:2])
    def _continue(self,request,*,query):
        from continuity_engine.domain.scheduling import NotificationReceipt, NotificationStatus
        prefix=next((p for p in ('temporary-tool:','temporary-tool-cleanup:') if request.task_id.startswith(p)),None)
        if prefix is None:
            return self.native.query(request) if query else self.native.dispatch(request)
        connection=request.task_id[len(prefix):]
        if (request.subject_id,request.environment,request.cycle_id)!=(self.subject_id,self.environment,self.cycle_id):
            raise ExecutionError('TOOL_RUNTIME_BINDING')
        self.guard('before_tool_continuation')
        result=self.tools.advance(connection,self.action_factory)
        done=result['state']=='CLOSED' or (result['state']=='VERIFIED' and result['mode']!='SINGLE'
            and result.get('task_status')=='SUCCEEDED')
        return NotificationReceipt('tool-wake:'+digest([request.task_id,request.attempt_id,result])[7:],
            request.task_id,request.attempt_id,self.subject_id,self.environment,
            NotificationStatus.DELIVERED if done else NotificationStatus.UNKNOWN,self.clock(),
            'TOOL_CONTINUATION_COMPLETE' if done else 'TOOL_CONDITIONS_OR_FACTS_PENDING')
    def query(self,request): return self._continue(request,query=True)
    def dispatch(self,request): return self._continue(request,query=False)
