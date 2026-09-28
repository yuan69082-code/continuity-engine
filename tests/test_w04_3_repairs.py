"""W04-3 repair proofs through the original P18 host/Scheduler and E5-A."""
import json
import tempfile
import unittest
import re
import traceback
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from continuity_engine.domain.action_capability import ReceiptQuery
from continuity_engine.domain.execution import ExecutionError
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError

from continuity_engine.domain.temporary_tools import ToolCommand
from continuity_engine.services.temporary_tool_service import TemporaryToolRuntimeWork
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture


class ToolRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='w43-r-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.host=P18Fixture(self.root)
        self.f=W04ToolFixture(self.root,runtime=self.host.runtime,manager=self.host.manager)
        self.contexts={}
        self.inputs={}
        self.waiting=set()
        self.fresh_new_actions=False
        self.continuation_contexts={}
        self.attach()

    def attach(self):
        f=self.f;h=self.host
        original=f.authorize_tool
        def authorize(lease,offer,**kw):
            if kw['purpose']!='cleanup' and offer.tool_id in self.waiting:return ('LOGIN',)
            return original(lease,offer,**kw)
        f.tools.authorize=authorize
        def factory(kind,parent,existing,reason):
            f.last_context=self.contexts[parent.capability_request_id]
            if existing is None and self.fresh_new_actions and parent.capability_request_id in self.continuation_contexts:
                f.last_context=self.continuation_contexts[parent.capability_request_id]
            elif existing is None and self.fresh_new_actions:
                # The original subject producer may prepare a NEW step using
                # current state. Never rewrite a sealed old choice or receipt.
                from continuity_engine.domain.perception import PerceptionContext
                identity='tool-context:'+uuid4().hex
                wake=h.work.awakening.wake_manual(h.work.cycle_id,detail='TEST current tool continuation context',session_id=identity)
                perception=h.work.native._perception.perceive(PerceptionContext.from_awakening(wake,current_time=h.clock.now()))
                f.last_context=f.core.prepare(perception,SimpleNamespace(subject_id=h.state.subject_id,request_id=identity)).continuity_context
                # One current Context for the new use/close continuation, just
                # like the existing Fixture's action producer. Each step still
                # revalidates it; no historical choice is rebound or rewritten.
                self.continuation_contexts[parent.capability_request_id]=f.last_context
            return f.action_factory(kind,parent,existing,reason)
        self.factory=factory
        h.host.work=TemporaryToolRuntimeWork(h.work,f.tools,factory)
        for name in ('dispatch','query'):
            original_work=getattr(h.host.work,name)
            def diagnosed(request,method=original_work):
                try:return method(request)
                except Exception as exc:
                    code=exc.args[0] if exc.args and isinstance(exc.args[0],str) and re.fullmatch('[A-Z_]+',exc.args[0]) else None
                    print(json.dumps(dict(diagnostic='work-boundary',type=type(exc).__name__,code=code,
                        frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(exc.__traceback__)])),flush=True)
                    raise
            setattr(h.host.work,name,diagnosed)
        h.scheduler._notification=h.host.work

    def prepare(self,name,*,opened=False,seconds=120):
        f=self.f
        # Actual P16 discovery input and original C1 Context, never a prepared receipt.
        self.host.advance(1)
        if opened:
            connection,_,lease,offer=f.open_tool(name=name,seconds=seconds)
        else:
            rid,offer,_=f.discover(name=name)
            lease=f.lease(rid,offer,seconds=seconds)
            connection,_=f.prepare_tool(ToolCommand('connect',lease),decision='repair:'+name)
        self.contexts[connection.capability_request_id]=f.last_context
        self.inputs[connection.capability_request_id]=f.last_request['requestId']
        return connection,lease,offer

    def reopen(self):
        self.host=P18Fixture(self.root,initialize=False)
        self.f=W04ToolFixture(self.root,runtime=self.host.runtime,manager=self.host.manager)
        self.contexts={k:self.f.app.ledger.load_operation(v).domain_progress.perception.continuity_context
                       for k,v in self.inputs.items()}
        self.attach()

    def closes(self,connection):
        return [r for r in self.f.tools.related(connection.capability_request_id)
                if self.f.tools.command(r).operation=='close']

    def ticks(self,count,seconds=5):
        def control():self.host.host.guard('temporary-tool');return True
        self.f.tools.control=control
        for _ in range(count):
            self.assertTrue(self.host.host.tick())
            if seconds:self.host.advance(seconds)

    def diagnostic(self,label):
        f=self.f;h=self.host
        value=dict(label=label,checkpoint=h.store.load(),
            tasks=[t.to_dict() for t in h.scheduler.list_tasks(subject_id=h.state.subject_id,environment='TEST')],
            connections=[f.tools.inspect(r.capability_request_id) for r in f.tools._requests() if r.capability_type=='tool.connect'],
            effects=f.fake.effect_count,credits=f.fake.credits,native_calls=h.provider.calls,
            revision=h.state.revision,discovery_calls=f.discovery.external_calls)
        try:
            adapters={b.capability:b.adapter for b in f.core.capabilities}
            value['attempts']=[dict(request=r.capability_request_id,capability=r.capability_type,
                results=[dict(status=a.result.status.value,reason=a.result.reason,gates=a.result.gate_reasons)
                    for a in f.core.coordination.action_attempts(r,receipt_verifier=adapters[r.capability_type])])
                for r in f.tools._requests() if r.capability_type.startswith(('tool.','device.'))]
        except Exception as exc:value['diagnostic_error_type']=type(exc).__name__
        print(json.dumps(value,default=str))

    def test_waiting_first_does_not_starve_second_or_native_work(self):
        a,_,_=self.prepare('a');b,_,_=self.prepare('b')
        self.waiting.add('tool:a')
        # A real Event without a Memory causes native maintenance; cognition is
        # still the original RuntimeCognition.needs, never replaced with ().
        self.f.base.event('repair:maintenance',content='TEST retained event for native maintenance')
        with self.host.host.running():
            try:
                self.ticks(16)
                self.diagnostic('R1-before-stop')
                self.assertEqual(self.f.tools.inspect(b.capability_request_id)['state'],'CLOSED')
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(1,1))
                tasks=self.host.scheduler.list_tasks(subject_id=self.host.state.subject_id,environment='TEST')
                self.assertTrue(any(t.task_id.startswith('maintenance:') and t.completed_at for t in tasks))
                self.host.advance(3600);self.ticks(3,seconds=60)
                self.assertGreater(self.host.provider.calls,0)
            finally:
                self.host.control('STOP');self.assertFalse(self.host.host.tick())

    def test_three_failed_cleanup_facts_can_resume_via_host(self):
        f=self.f;c,lease,_=self.prepare('cleanup',opened=True)
        f.tool_port.mode='terminal'
        for i in range(3):
            request,result=f.close_tool(c,lease,reason='RETRY_CLEANUP',decision='repair:failed:'+str(i))
            self.assertEqual(result.status,'FAILED')
        old=[r.capability_request_id for r in f.tools.related(c.capability_request_id)]
        f.tool_port.mode='success';self.host.advance(5)
        with self.host.host.running():
            try:
                self.ticks(2)
                self.diagnostic('R2-before-stop')
                self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertTrue(set(old)<=set(r.capability_request_id for r in f.tools.related(c.capability_request_id)))
                self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))
            finally:
                self.host.control('STOP');self.assertFalse(self.host.host.tick())

    def test_both_native_needs_and_two_tools_obtain_real_dispatch(self):
        self.host.advance(3600)
        a,_,_=self.prepare('first',seconds=300)
        b,_,_=self.prepare('second',opened=True,seconds=300)
        self.fresh_new_actions=True
        self.waiting.add('tool:first')
        self.f.base.event('repair:simultaneous-memory',content='TEST independently retained maintenance material')
        native=self.host.work.needs(self.host.clock.now())
        self.assertEqual({n.kind for n in native},{'cognition','maintenance'})
        with self.host.host.running():
            try:
                # Observe at the normal retry cadence. Advancing in 60-second
                # jumps can skip a valid 120-second Action authorization window.
                self.ticks(16)
                self.host.advance(60);self.ticks(2)
                self.diagnostic('R1-native-and-tools')
                self.assertEqual(self.f.tools.inspect(b.capability_request_id)['state'],'CLOSED')
                tasks=self.host.scheduler.list_tasks(subject_id=self.host.state.subject_id,environment='TEST')
                self.assertTrue(any(t.task_id.startswith('maintenance:') and t.completed_at for t in tasks))
                self.assertGreater(self.host.provider.calls,0)
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(1,1))
            finally:self.host.control('STOP');self.assertFalse(self.host.host.tick())

    def test_login_wait_reopen_pause_resume_and_original_identity(self):
        a,_,_=self.prepare('a');b,_,_=self.prepare('b');self.waiting.add('tool:a')
        with self.host.host.running():
            self.ticks(2)
            self.assertEqual(self.f.tools.inspect(b.capability_request_id)['state'],'CLOSED')
            self.host.control('PAUSE')
        original_tasks=self.host.scheduler.list_tasks(subject_id=self.host.state.subject_id,environment='TEST')
        self.reopen();self.waiting.clear()
        with self.host.host.running():
            try:
                self.ticks(2);self.assertEqual(self.f.fake.effect_count,1)
                self.host.control('RESUME');self.ticks(13)
                self.assertEqual(self.f.tools.inspect(a.capability_request_id)['state'],'CLOSED')
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(2,2))
                task=self.host.scheduler.get('temporary-tool:'+a.capability_request_id,
                    subject_id=self.host.state.subject_id,environment='TEST')
                old=next(t for t in original_tasks if t.task_id==task.task_id)
                self.assertEqual((task.last_attempt_id,task.attempt_count),(old.last_attempt_id,old.attempt_count))
                self.assertEqual(self.f.discovery.external_calls,0)
            finally:self.host.control('STOP');self.assertFalse(self.host.host.tick())
        self.reopen()
        with self.host.host.running():self.assertFalse(self.host.host.tick())
        with self.assertRaises(RuntimeBoundaryError):self.host.control('RESUME')

    def test_unknown_first_does_not_block_second_or_replay(self):
        a,_,_=self.prepare('unknown');b,_,_=self.prepare('ready')
        query=self.f.tool_port.query
        self.f.tool_port.query=lambda r:ReceiptQuery.UNKNOWN if r.capability_request_id==a.capability_request_id else query(r)
        with self.host.host.running():
            try:
                self.ticks(3)
                self.assertEqual(self.f.tools.inspect(b.capability_request_id)['state'],'CLOSED')
                self.assertEqual(self.f.tools.inspect(a.capability_request_id)['state'],'UNKNOWN')
                self.assertNotIn(a.capability_request_id,self.f.tool_port.store.load()['connections'])
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(1,1))
            finally:self.diagnostic('R1-UNKNOWN');self.host.control('STOP')

    def test_dependency_wait_and_pending_cleanup_do_not_block_ready(self):
        a,lease,_=self.prepare('dirty',opened=True)
        self.f.tool_port.mode='partial_cleanup';self.f.close_tool(a,lease)
        self.f.tool_port.mode='success'
        b,_,_=self.prepare('dependent');c,_,_=self.prepare('ready')
        self.f.tools.dependencies=lambda offer:() if offer.tool_id=='tool:dependent' else ('local:device',)
        original=self.f.tool_port.execute
        def execute(r,command,offer,guard):
            self.f.tool_port.mode='partial_cleanup' if command.operation=='close' and command.connection_request_id==a.capability_request_id else 'success'
            return original(r,command,offer,guard)
        self.f.tool_port.execute=execute
        with self.host.host.running():
            try:
                self.ticks(4)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertEqual(self.f.tools.inspect(a.capability_request_id)['state'],'PENDING_CLEANUP')
                self.assertIn('DEPENDENCY_MISSING',self.f.tools.inspect(b.capability_request_id)['missing'])
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(1,1))
            finally:self.diagnostic('R1-mixed-waits');self.host.control('STOP')

    def test_automatic_partial_cleanup_survives_three_failures_and_reopen(self):
        c,lease,_=self.prepare('partial',opened=True)
        self.f.tool_port.mode='partial_cleanup';self.f.close_tool(c,lease)
        with self.host.host.running():
            self.ticks(3)
            self.assertGreaterEqual(len(self.closes(c)),4)
        old={r.capability_request_id:self.f.tools.query(r).canonical_hash() for r in self.closes(c)}
        self.reopen()
        with self.host.host.running():
            try:
                self.ticks(1)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertEqual({r.capability_request_id:self.f.tools.query(r).canonical_hash()
                    for r in self.closes(c) if r.capability_request_id in old},old)
                calls=self.f.tool_port.calls;self.ticks(1)
                self.assertEqual(self.f.tool_port.calls,calls)
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(0,0))
            finally:self.host.control('STOP')

    def test_cleanup_backoff_is_receipt_bound_readonly_and_configurable(self):
        c,lease,_=self.prepare('backoff',opened=True)
        self.f.tool_port.mode='terminal';self.f.close_tool(c,lease)
        # One immediate continuation of an explicit failure, then bounded pacing.
        self.f.tools.cleanup_retry_seconds=12
        with self.host.host.running():
            try:
                self.ticks(1,seconds=0)
                self.assertEqual(len(self.closes(c)),2)
                calls=self.f.tool_port.calls
                for _ in range(3):
                    result=self.f.tools.advance(c.capability_request_id,self.factory)
                    self.assertEqual(result['cleanup_wait_reason'],'BACKOFF')
                self.assertEqual(self.f.tool_port.calls,calls)
                self.host.advance(11)
                self.assertEqual(self.f.tools.advance(c.capability_request_id,self.factory)['cleanup_wait_reason'],'BACKOFF')
                self.host.advance(1);self.f.tool_port.mode='success';self.ticks(1)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertEqual(len(self.closes(c)),3)
            finally:self.host.control('STOP')

    def test_cleanup_unknown_and_return_lost_use_original_fact(self):
        c,lease,_=self.prepare('unknown-close',opened=True)
        self.f.tool_port.mode='lost_response'
        close,run=self.f.prepare_tool(ToolCommand('close',lease,c.capability_request_id,'CANCEL'),decision='repair:lost-close')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.f.tool_port.mode='unknown';calls=self.f.tool_port.calls
        with self.host.host.running():
            try:
                self.ticks(2)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLEANUP_UNKNOWN')
                self.assertEqual((len(self.closes(c)),self.f.tool_port.calls),(1,calls))
                self.f.tool_port.mode='success';self.ticks(1)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertEqual((len(self.closes(c)),self.f.tool_port.calls),(1,calls))
            finally:self.host.control('STOP')

    def test_cleanup_revocation_pause_stop_and_other_connection_isolation(self):
        c,lease,_=self.prepare('dirty',opened=True)
        other,_,_=self.prepare('other',opened=True)
        self.f.last_context=self.contexts[c.capability_request_id]
        self.f.tool_port.mode='terminal';self.f.close_tool(c,lease)
        self.f.tool_port.mode='success';self.f.change(cleanup=False)
        other_before=self.f.tool_port.store.load()['connections'][other.capability_request_id]
        canary=self.root/'formal-canary'/'sentinel';canary.parent.mkdir(exist_ok=True);canary.write_bytes(b'TEST untouched')
        with self.host.host.running():
            try:
                self.ticks(2)
                self.assertEqual(len(self.closes(c)),1)
                self.assertEqual(self.f.tool_port.store.load()['connections'][other.capability_request_id],other_before)
                self.host.control('PAUSE');self.f.change(cleanup=True)
                calls=self.f.tool_port.calls;self.ticks(2)
                self.assertEqual(self.f.tool_port.calls,calls)
                self.host.control('STOP');self.assertFalse(self.host.host.tick())
                self.assertEqual(canary.read_bytes(),b'TEST untouched')
            finally:
                if self.host.store.load()['desired']!='STOPPED':self.host.control('STOP')
        self.reopen()
        with self.host.host.running():self.assertFalse(self.host.host.tick())
        self.assertEqual(len(self.closes(c)),1)

    def test_current_host_and_scope_denial_prevent_new_cleanup(self):
        c,lease,_=self.prepare('fenced',opened=True)
        self.f.tool_port.mode='terminal';self.f.close_tool(c,lease)
        self.f.tool_port.mode='success'
        self.f.repo.handoff_test('host:a','host:b',expected_revision=self.f.repo.load()['revision'])
        with self.host.host.running():
            try:
                self.ticks(2)
                self.assertEqual(len(self.closes(c)),1)
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(0,0))
            finally:self.host.control('STOP')

    def test_old_context_is_not_rebound_after_native_revision(self):
        from continuity_engine.domain.errors import CapabilityValidationError
        self.host.advance(3600)
        c,_,_=self.prepare('old-context')
        sealed=c.to_dict();revision=self.host.state.revision
        with self.host.host.running():
            try:
                self.ticks(1)
                self.assertGreater(self.host.state.revision,revision)
                self.f.last_context=self.contexts[c.capability_request_id]
                planner=self.f.restore_dispatch(c)
                calls=self.host.provider.calls;state=self.host.state.to_dict()
                with self.assertRaisesRegex(CapabilityValidationError,'CONTEXT_CHANGED_BEFORE_ACTION'):
                    self.f.tools.run(planner,c.choice,self.f.last_context.composition,retry=True)
                self.assertEqual(c.to_dict(),sealed)
                self.assertEqual(self.f.tools.execution.request(c.capability_request_id).to_dict(),sealed)
                self.assertEqual((self.f.fake.effect_count,self.f.fake.credits),(0,0))
                self.assertEqual(self.host.provider.calls,calls)
                self.assertEqual(self.host.state.to_dict(),state)
            finally:self.host.control('STOP')

    def test_backoff_survives_reopen_without_reset_or_read_side_effect(self):
        c,lease,_=self.prepare('durable-backoff',opened=True)
        self.f.tool_port.mode='terminal';self.f.close_tool(c,lease)
        with self.host.host.running():self.ticks(1,seconds=0)
        old={r.capability_request_id:self.f.tools.query(r).canonical_hash() for r in self.closes(c)}
        self.assertEqual(len(old),2)
        self.reopen()
        with self.host.host.running():
            try:
                before=self.f.tool_port.store.path.read_bytes();revision=self.host.state.revision
                self.ticks(1,seconds=0)
                for _ in range(3):self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'PENDING_CLEANUP')
                self.assertEqual(self.f.tool_port.store.path.read_bytes(),before)
                self.assertEqual(self.host.state.revision,revision)
                self.assertEqual(self.f.tool_port.calls,0)
                self.host.advance(5);self.ticks(1)
                self.assertEqual(self.f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
                self.assertEqual(self.f.tool_port.calls,1)
                self.assertEqual({r.capability_request_id:self.f.tools.query(r).canonical_hash()
                    for r in self.closes(c) if r.capability_request_id in old},old)
            finally:self.host.control('STOP')

    def test_invalid_cleanup_pacing_is_rejected_without_port_work(self):
        from continuity_engine.services.temporary_tool_service import TemporaryToolService
        s=self.f.tools;path=self.f.tool_port.store.path
        before=path.read_bytes() if path.exists() else None
        for invalid in (0,-1,True,float('nan'),float('inf'),'5'):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaisesRegex(ExecutionError,'TOOL_CLEANUP_RETRY_POLICY_INVALID'):
                    TemporaryToolService(external=s.external,access=s.access,port=s.port,authorize=s.authorize,
                        dependencies=s.dependencies,clock=s.clock,authorize_view=s.authorize_view,
                        authorize_action=s.authorize_action,cleanup_retry_seconds=invalid)
        self.assertEqual(path.read_bytes() if path.exists() else None,before)
        self.assertEqual(self.f.tool_port.calls,0)
