import json
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import timedelta

from continuity_engine.domain.action_capability import ReceiptQuery
from continuity_engine.domain.execution import ExecutionError
from continuity_engine.domain.temporary_tools import ToolCommand
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture


class TemporaryToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='w04-3-test-')
        self.addCleanup(self.temp.cleanup)
        self.f=W04ToolFixture(self.temp.name)

    def test_discovery_is_real_p16_and_not_current_availability(self):
        f=self.f;rid,offer,result=f.discover()
        self.assertEqual(result.status,'completed')
        self.assertEqual(f.discovery.external_calls,1)
        self.assertEqual(f.tools.candidates(rid)[0][1],offer)
        self.assertNotIn(offer.attachment.to_dict(),f.repo.load()['attachments'])
        self.assertEqual(f.tool_port.store.load()['connections'],{})

    def test_authorized_connect_verify_use_cleanup_and_readonly(self):
        f=self.f;connection,verify,lease,offer=f.open_tool()
        command=f.tool_command(offer,'type',text='TEST useful output')
        req,run=f.prepare_step(f.device.step(command),'use:one');result=run()
        self.assertEqual(result.status,'COMPLETED')
        self.assertEqual(f.fake.store.load()['view']['draft'],'TEST useful output')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
        revision=f.state.revision;calls=f.tool_port.calls
        before=f.tool_port.store.path.read_bytes()
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'VERIFIED')
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'VERIFIED')
        self.assertEqual((before,calls,revision),(f.tool_port.store.path.read_bytes(),f.tool_port.calls,f.state.revision))
        f.close_tool(connection,lease)
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'CLOSED')
        self.assertFalse(f.tool_port.store.load()['connections'][connection.capability_request_id]['temporary_files'])

    def test_missing_login_resumes_same_connection_without_discovery_or_cost_repeat(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        f.change(login=False)
        req,run=f.prepare_tool(ToolCommand('connect',lease),decision='wait:login')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(f.tools.inspect(req.capability_request_id)['missing'],['LOGIN'])
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)
        f.change(login=True)
        self.assertEqual(run(True).status,'COMPLETED')
        self.assertEqual(run(True).status,'COMPLETED')
        self.assertEqual((len(f.tool_port.store.load()['connections']),f.discovery.external_calls),(1,1))

    def test_partial_cleanup_is_pending_then_linked_cleanup_preserves_facts(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        f.tool_port.mode='partial_cleanup';first,result=f.close_tool(c,lease)
        self.assertEqual(result.status,'COMPLETED') # cleanup operation happened; NOT clean completion
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'PENDING_CLEANUP')
        f.tool_port.mode='success';f.close_tool(c,lease,reason='RETRY_CLEANUP',decision='close:two')
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLOSED')
        self.assertEqual(f.tools._value(first)['status'],'PARTIAL')

    def test_unknown_connection_never_replays_or_creates_effect(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        req,run=f.prepare_tool(ToolCommand('connect',lease),decision='unknown:connect')
        f.tool_port.mode='unknown'
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(run(True).status,'WAITING_CAPABILITY')
        self.assertEqual(f.tool_port.calls,0)

    def test_return_lost_recovers_original_receipt_without_second_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        req,run=f.prepare_tool(ToolCommand('connect',lease),decision='lost:connect')
        f.tool_port.mode='lost_response';self.assertEqual(run().status,'WAITING_CAPABILITY')
        f.tool_port.mode='success';self.assertEqual(run(True).status,'COMPLETED')
        self.assertEqual(f.tool_port.calls,1);self.assertEqual(len(f.tool_port.store.load()['connections']),1)

    def test_single_use_cannot_run_second_business_action(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='first')),'single:one')
        self.assertEqual(run().status,'COMPLETED')
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='second')),'single:two')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))

    def test_expiry_denies_use_but_cleanup_is_separately_authorized(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='TIMED',seconds=10)
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='no')),'expire:use')
        f.runtime.clock.advance(timedelta(seconds=10))
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,0)
        f.close_tool(c,lease,reason='EXPIRE')
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLOSED')

    def test_revocation_cannot_switch_route_and_view_permission_is_current(self):
        f=self.f;c,v,lease,offer=f.open_tool(route='UI')
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='denied')),'revoke:use')
        f.change(revoked=True)
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,0)
        f.change(view=False)
        with self.assertRaisesRegex(ExecutionError,'TOOL_VIEW_DENIED'):f.tools.inspect(c.capability_request_id)

    def test_history_query_reuses_original_receipt_router_composer(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        req,run=f.prepare_step(f.device.step(f.tool_command(offer)),'history:use')
        self.assertEqual(run().status,'COMPLETED')
        perception=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
        result=f.device.history_context(req.capability_request_id,perception)
        self.assertTrue(any(x.stable_source_id=='execution:'+req.capability_request_id for x in result.snapshot.fragments))
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_advance_autonomously_finishes_single_task_without_model_steps(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        request,_=f.prepare_tool(ToolCommand('connect',lease),decision='autonomous:one')
        before=len(f.provider.inputs);revision=f.state.revision
        value=f.tools.advance(request.capability_request_id,f.action_factory)
        self.assertEqual((value['state'],f.fake.effect_count,f.fake.credits),('CLOSED',1,1))
        f.tools.advance(request.capability_request_id,f.action_factory)
        self.assertEqual((len(f.provider.inputs),f.state.revision),(before,revision))
        self.assertEqual(len(f.tool_port.store.load()['connections']),1)

    def test_granted_persistent_connection_survives_task_until_explicit_cancel(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer,mode='PERSISTENT')
        request,_=f.prepare_tool(ToolCommand('connect',lease),decision='persistent:one')
        value=f.tools.advance(request.capability_request_id,f.action_factory)
        self.assertEqual((value['state'],value['task_status']),('VERIFIED','SUCCEEDED'))
        second,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='second task')),'persistent:second')
        self.assertEqual(run().status,'COMPLETED')
        f.close_tool(request,lease,reason='CANCEL')
        self.assertEqual(f.tools.inspect(request.capability_request_id)['state'],'CLOSED')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(2,2))

    def test_cancel_reserved_before_delivery_fences_future_use(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='PERSISTENT')
        use,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='must not run')),'cancel:use')
        close,close_run=f.prepare_tool(ToolCommand('close',lease,c.capability_request_id,'CANCEL'),decision='cancel:close')
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,0)
        self.assertEqual(close_run().status,'COMPLETED')

    def test_cancel_before_connection_reopen_and_replay_never_opens_it(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        connection,run=f.prepare_tool(ToolCommand('connect',lease),decision='cancel:pending')
        close,result=f.close_tool(connection,lease,reason='CANCEL',decision='cancel:absent')
        self.assertEqual(result.status,'COMPLETED')
        self.assertNotEqual(run(True).status,'COMPLETED')
        f.reopen()
        planner=f.restore_dispatch(connection)
        result=f.tools.run(planner,connection.choice,f.last_context.composition,retry=True)
        self.assertNotEqual(result.status,'COMPLETED')
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'CLOSED')
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)
        self.assertEqual((f.fake.effect_count,f.fake.credits,f.state.revision),(0,0,1))

    def test_cancel_during_connect_before_native_commit_is_fenced(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        connection,run=f.prepare_tool(ToolCommand('connect',lease),decision='cancel:race')
        cleanup=[];busy=[]
        def cancel():
            f.tool_port.before=None
            close,close_run=f.prepare_tool(ToolCommand('close',lease,connection.capability_request_id,'CANCEL'),
                decision='cancel:race-close')
            cleanup.append(close_run)
            try:close_run()
            except ExecutionError as exc:
                if str(exc)!='EXECUTION_BUSY':raise
                busy.append(str(exc))
        f.tool_port.before=cancel
        self.assertNotEqual(run().status,'COMPLETED')
        self.assertEqual(busy,['EXECUTION_BUSY'])
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'PENDING_CLEANUP')
        self.assertEqual(cleanup[0](True).status,'COMPLETED')
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'CLOSED')

    def test_terminal_failed_connection_can_finish_cleanup_without_fake_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        connection,run=f.prepare_tool(ToolCommand('connect',lease),decision='cancel:failed')
        f.tool_port.mode='terminal';self.assertEqual(run().status,'FAILED')
        f.tool_port.mode='success'
        close,result=f.close_tool(connection,lease,reason='CANCEL',decision='cancel:failed-close')
        self.assertEqual(result.status,'COMPLETED')
        self.assertEqual(f.tools.inspect(connection.capability_request_id)['state'],'CLOSED')
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_conditions_identify_new_scope_budget_dependency_without_creating_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        command=ToolCommand('connect',lease)
        f.change(scope=False);self.assertEqual(f.tools.conditions(command),('NEW_SCOPE',))
        f.change(scope=True,budget=0);self.assertEqual(f.tools.conditions(command),('BUDGET',))
        f.change(budget=10);f.dependencies_available=()
        self.assertEqual(f.tools.conditions(command),('DEPENDENCY_MISSING',))
        f.dependencies_available=('local:device',);f.tool_port.online=False
        self.assertEqual(f.tools.conditions(command),('CAPABILITY_UNAVAILABLE',))
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)

    def test_missing_discovery_and_untrusted_material_are_not_callable(self):
        f=self.f
        with self.assertRaisesRegex(ExecutionError,'TOOL_DISCOVERY_ENTRY_MISSING'):f.tools.candidates('action-cap:missing')
        f.discovery.query='skill:unstructured catalogue';f.discovery.submit()
        r=f.discovery.core.last_action.requests[0]
        with self.assertRaisesRegex(ExecutionError,'TOOL_OFFER_UNVERIFIED'):f.tools.candidates(r.capability_request_id)
        self.assertEqual(f.tool_port.calls,0)

    def test_candidate_identity_scope_and_hash_are_checked(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        with self.assertRaisesRegex(ExecutionError,'TOOL_OFFER_CHANGED'):
            f.tools.offer(replace(lease,offer_hash='sha256:'+'0'*64))
        other=replace(offer,attachment=replace(offer.attachment,subject_id='other:subject'))
        text=json.dumps(other.to_dict(),separators=(',',':'))
        from continuity_engine.domain.action_planning import digest
        f.discovery.fake.candidate_hook=lambda c:replace(c,content=text,content_hash=digest(text))
        f.discovery.next_round();r=f.discovery.core.last_action.requests[0]
        with self.assertRaisesRegex(ExecutionError,'TOOL_OFFER_BOUNDARY'):f.tools.candidates(r.capability_request_id)

    def test_current_discovery_revocation_prevents_use_but_preserves_historical_fact(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='denied')),'source:withdraw')
        f.discovery.revoke()
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(f.tools.offer(lease,current=False),offer)
        self.assertEqual(f.fake.effect_count,0)

    def test_failed_verification_does_not_register_usable_tool(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        c,run=f.prepare_tool(ToolCommand('connect',lease),decision='verify:connect');run()
        v,run=f.prepare_tool(ToolCommand('verify',lease,c.capability_request_id),decision='verify:fail')
        f.tool_port.mode='terminal';self.assertEqual(run().status,'FAILED')
        with self.assertRaisesRegex(ExecutionError,'TOOL_VERIFICATION_REQUIRED'):f.tools.activate(v.capability_request_id)
        self.assertNotIn('temporary:one',[a['attachment_id'] for a in f.repo.load()['attachments']])

    def test_cleanup_unknown_does_not_claim_closed_or_start_another_cleanup(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        close,run=f.prepare_tool(ToolCommand('close',lease,c.capability_request_id,'CANCEL'),decision='cleanup:unknown')
        f.tool_port.mode='unknown';self.assertEqual(run().status,'WAITING_CAPABILITY')
        calls=f.tool_port.calls
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLEANUP_UNKNOWN')
        self.assertEqual(f.tools.advance(c.capability_request_id,f.action_factory)['state'],'CLEANUP_UNKNOWN')
        self.assertEqual(f.tool_port.calls,calls)

    def test_view_rechecks_permission_at_return(self):
        f=self.f;c,*_=f.open_tool()
        answers=iter((True,False));f.tools.authorize_view=lambda *args:next(answers)
        with self.assertRaisesRegex(ExecutionError,'TOOL_VIEW_DENIED'):f.tools.inspect(c.capability_request_id)

    def test_budget_is_actual_unique_business_receipts_not_number_of_queries(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='TIMED',budget=1)
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='one')),'budget:one')
        self.assertEqual(run().status,'COMPLETED');self.assertEqual(run(True).status,'COMPLETED')
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='two')),'budget:two')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))

    def test_final_revocation_between_setup_and_native_call_is_zero_effect(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='blocked')),'race:use')
        f.fake.before_action=lambda:f.change(revoked=True)
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_connection_identity_is_not_reused_for_renewal(self):
        f=self.f;c,v,lease,offer=f.open_tool();f.close_tool(c,lease)
        renewed=replace(lease,expires_at=lease.expires_at,grant_ref='grant:test:2')
        f.change(grant='grant:test:2')
        r,run=f.prepare_tool(ToolCommand('connect',renewed),decision='renew:old-attachment')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(len(f.tool_port.store.load()['connections']),1)

    def test_credential_secret_rejected_before_ledger_write_and_traceback_safe(self):
        import traceback
        from continuity_engine.testing.p16_provider_fixture import SECRET_MARKER
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        ledger=f.core.coordination._repository.capability_path
        before=ledger.read_bytes()
        secret_lease=replace(lease,grant_ref=SECRET_MARKER)
        with self.assertRaises(ExecutionError):
            f.prepare_tool(ToolCommand('connect',secret_lease),decision='secret:refused')
        self.assertEqual(ledger.read_bytes(),before)
        self.assertNotIn(SECRET_MARKER,ledger.read_text(encoding='utf8'))
        # Port exception diagnostic is not copied into the error chain.
        def explode(*a,**kw):raise RuntimeError(SECRET_MARKER)
        f.tools.authorize=explode
        try:f.tools.conditions(ToolCommand('connect',lease))
        except ExecutionError:
            self.assertNotIn(SECRET_MARKER,traceback.format_exc())
        else:self.fail('port exception must refuse')
        self.assertEqual(f.tool_port.calls,0)

    def test_cross_process_lost_connection_recovery_and_replay(self):
        import subprocess,sys,os,pathlib
        with tempfile.TemporaryDirectory(prefix='w04-3-process-') as root:
            records=[]
            for phase in ('prepare','resume','replay'):
                command=[sys.executable,'-m','continuity_engine.testing.w04_tool_fixture','--root',root,'--phase',phase]
                result=subprocess.run(command,capture_output=True,text=True,encoding='utf8',timeout=120,
                    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                print(json.dumps(dict(phase=phase,command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)))
                self.assertEqual(result.returncode,0,result.stderr);records.append(json.loads(result.stdout))
            self.assertEqual((records[-1]['effects'],records[-1]['credits'],records[-1]['new_models']),(1,1,0))

    def test_same_tool_grant_does_not_authorize_send_or_purchase(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='PERSISTENT')
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'send',target='control:send')),'scope:send')
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,0)
        f.tools.authorize=lambda *a,**kw:('PURCHASE_NOT_AUTHORIZED',)
        self.assertEqual(f.tools.conditions(ToolCommand('connect',lease)),('PURCHASE_NOT_AUTHORIZED',))

    def test_cleanup_failure_then_reopen_preserves_pending_not_false_clean(self):
        f=self.f;c,v,lease,offer=f.open_tool();f.tool_port.mode='terminal'
        req,result=f.close_tool(c,lease,reason='CANCEL')
        self.assertEqual(result.status,'FAILED')
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'PENDING_CLEANUP')
        before=f.tool_port.store.path.read_bytes();f.reopen()
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'PENDING_CLEANUP')
        self.assertEqual(before,f.tool_port.store.path.read_bytes())
        f.tool_port.mode='success';value=f.tools.advance(c.capability_request_id,f.action_factory)
        self.assertEqual(value['state'],'CLOSED')

    def test_offline_recovery_does_not_reconnect_or_reset_generation(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='TIMED')
        req,run=f.prepare_step(f.device.step(f.tool_command(offer,'type',text='after reconnect')),'offline:use')
        before=f.repo.load();f.tool_port.online=False
        self.assertEqual(run().status,'WAITING_CAPABILITY');self.assertEqual(f.fake.effect_count,0)
        f.tool_port.online=True
        self.assertEqual(run(True).status,'COMPLETED')
        self.assertEqual(f.repo.load(),before);self.assertEqual(len(f.tool_port.store.load()['connections']),1)

    def test_expired_discovery_is_not_replaced_by_same_name_new_offer(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer,seconds=600)
        f.runtime.clock.advance(timedelta(seconds=300))
        self.assertEqual(f.tools.conditions(ToolCommand('connect',lease)),('SOURCE_NOT_CURRENT',))
        self.assertEqual(f.tools.offer(lease,current=False),offer)
        self.assertEqual(f.tool_port.calls,0)

    def test_connection_fact_corruption_refuses_read_and_has_no_effect(self):
        f=self.f;c,*_=f.open_tool()
        path=f.tool_port.store.path;path.write_text('{}',encoding='utf8')
        with self.assertRaisesRegex(ExecutionError,'TOOL_QUERY_UNAVAILABLE'):f.tools.inspect(c.capability_request_id)
        self.assertEqual(f.fake.effect_count,0)

    def test_other_environment_offer_is_rejected_before_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        # Forging a lease never changes the authoritative P16 observation.
        from continuity_engine.domain.action_planning import digest
        other=replace(offer,attachment=replace(offer.attachment,environment='RESEARCH'))
        with self.assertRaisesRegex(ExecutionError,'TOOL_OFFER_CHANGED'):
            f.tools.offer(replace(lease,offer_hash=digest(other.to_dict())))
        self.assertEqual(f.tool_port.calls,0)

    def test_p18_wait_resume_pause_stop_use_original_task_and_control(self):
        from continuity_engine.testing.p18_runtime_fixture import P18Fixture
        from continuity_engine.services.temporary_tool_service import TemporaryToolRuntimeWork
        from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
        with tempfile.TemporaryDirectory(prefix='wt-host-') as root:
            host=P18Fixture(root)
            f=W04ToolFixture(root,runtime=host.runtime,manager=host.manager)
            rid,offer,_=f.discover();lease=f.lease(rid,offer)
            request,_=f.prepare_tool(ToolCommand('connect',lease),decision='runtime:connect')
            f.change(login=False)
            # Explicit focused fixture: native cognition remains covered by P18
            # compatibility; this need is resumed by its same Scheduler/host.
            host.work.needs=lambda at:()
            work=TemporaryToolRuntimeWork(host.work,f.tools,f.action_factory)
            host.host.work=work;host.scheduler._notification=work
            def control():host.host.guard('tool-current');return True
            f.tools.control=control
            with host.host.running():
                self.assertTrue(host.host.tick())
                self.assertEqual(len(f.tool_port.store.load()['connections']),0)
                host.control('PAUSE');f.change(login=True)
                self.assertTrue(host.host.tick());self.assertEqual(f.fake.effect_count,0)
                host.control('RESUME');host.advance(5)
                self.assertTrue(host.host.tick())
                self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
                self.assertEqual(f.tools.inspect(request.capability_request_id)['state'],'CLOSED')
                host.control('STOP');self.assertFalse(host.host.tick())
                with self.assertRaises(RuntimeBoundaryError):host.control('RESUME')
            self.assertEqual(f.discovery.external_calls,1)

    def test_cleanup_preserves_other_connection_and_subject_files(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='PERSISTENT')
        other={'active':True,'offer_hash':'other','temporary_files':{'untouched':'TEST'},'credential_reference':True}
        with f.tool_port.store.transaction() as d:
            d['connections']['other:isolated']=other;f.tool_port.store.save(d)
        state=f.state.to_dict();f.close_tool(c,lease)
        self.assertEqual(f.tool_port.store.load()['connections']['other:isolated'],other)
        self.assertEqual(f.state.to_dict(),state)

    def test_lost_cleanup_response_recovers_without_duplicate_removal(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        req,run=f.prepare_tool(ToolCommand('close',lease,c.capability_request_id,'CANCEL'),decision='close:lost')
        f.tool_port.mode='lost_response';self.assertEqual(run().status,'WAITING_CAPABILITY')
        count=f.tool_port.calls;f.tool_port.mode='success';f.reopen()
        self.assertEqual(run(True).status,'COMPLETED');self.assertEqual(f.tool_port.calls,count)
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLOSED')

    def test_explicit_renewal_uses_new_valid_grant_and_new_connection_identity(self):
        f=self.f;c,v,lease,offer=f.open_tool();f.close_tool(c,lease)
        rid,second,_=f.discover(name='two');renewed=replace(f.lease(rid,second),grant_ref='grant:test:2')
        f.change(grant='grant:test:2')
        request,_=f.prepare_tool(ToolCommand('connect',renewed),decision='renew:new')
        state=f.tools.advance(request.capability_request_id,f.action_factory)
        self.assertEqual(state['state'],'CLOSED')
        self.assertEqual(len(f.tool_port.store.load()['connections']),2)
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'CLOSED')

    def test_technical_api_unavailable_may_select_ui_but_denial_and_unknown_do_not(self):
        f=self.f;rid,one,_=f.discover(route='API');lease=f.lease(rid,one)
        old,run=f.prepare_tool(ToolCommand('connect',lease),decision='route:api')
        f.tool_port.routes={'UI'};self.assertEqual(run().status,'WAITING_CAPABILITY')
        rid,two,_=f.discover(route='UI',name='two');newlease=f.lease(rid,two)
        new,run=f.prepare_tool(ToolCommand('connect',newlease),decision='route:ui')
        planner,choice,context=f.last_planning;f.execution.prepare(planner,choice,context)
        f.change(revoked=True)
        with self.assertRaisesRegex(ExecutionError,'TOOL_ALTERNATIVE_DENIED'):f.tools.alternative(old.capability_request_id,new.capability_request_id)
        f.change(revoked=False);f.tool_port.mode='unknown'
        with self.assertRaisesRegex(ExecutionError,'TOOL_ALTERNATIVE_UNKNOWN'):f.tools.alternative(old.capability_request_id,new.capability_request_id)
        f.tool_port.mode='success'
        self.assertEqual(f.tools.alternative(old.capability_request_id,new.capability_request_id),'CHANGE_ROUTE')
        self.assertEqual(run().status,'COMPLETED');self.assertEqual(len(f.tool_port.store.load()['connections']),1)

    def test_migration_fences_old_discovery_before_any_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        f.repo.handoff_test('host:a','host:b',expected_revision=f.repo.load()['revision'])
        req,run=f.prepare_tool(ToolCommand('connect',lease),decision='old-host:connect')
        self.assertEqual(run().status,'WAITING_CAPABILITY')
        self.assertEqual(f.tools.conditions(ToolCommand('connect',lease)),('BINDING_NOT_CURRENT',))
        self.assertEqual(len(f.tool_port.store.load()['connections']),0)

    def test_fresh_observation_checks_lease_before_and_after_read(self):
        f=self.f;c,v,lease,offer=f.open_tool(seconds=1)
        command=f.tool_command(offer,'type',text='unused')
        f.runtime.clock.advance(timedelta(seconds=1))
        with self.assertRaisesRegex(Exception,'W04_REVOKED'):f.device.observe(command.observation.use)
        self.assertEqual(f.fake.effect_count,0)

    def test_permission_loss_during_observation_refuses_return(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        command=f.tool_command(offer,'type',text='unused');native=f.fake.observe
        def change(use):
            result=native(use);f.change(revoked=True);return result
        f.fake.observe=change
        with self.assertRaisesRegex(Exception,'W04_REVOKED'):f.device.observe(command.observation.use)
        self.assertEqual(f.fake.effect_count,0)

    def test_pause_during_wait_does_not_create_cleanup_intent(self):
        f=self.f;c,v,lease,offer=f.open_tool(mode='PERSISTENT')
        f.change(paused=True);before=len(f.tools.related(c.capability_request_id))
        self.assertEqual(f.tools.advance(c.capability_request_id,f.action_factory)['state'],'WAITING_CONDITIONS')
        self.assertEqual(len(f.tools.related(c.capability_request_id)),before)
        self.assertEqual(f.fake.effect_count,0)

    def test_timed_task_completes_then_expiry_cleanup_uses_original_connection(self):
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer,mode='TIMED',seconds=10)
        c,_=f.prepare_tool(ToolCommand('connect',lease),decision='timed:complete')
        first=f.tools.advance(c.capability_request_id,f.action_factory)
        self.assertEqual((first['state'],first['task_status']),('VERIFIED','SUCCEEDED'))
        f.runtime.clock.advance(timedelta(seconds=10))
        last=f.tools.advance(c.capability_request_id,f.action_factory)
        self.assertEqual(last['state'],'CLOSED');self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))

    def test_registration_alone_does_not_replace_connection_verification(self):
        from continuity_engine.domain.environment_access import DiscoveryState
        f=self.f;rid,offer,_=f.discover();lease=f.lease(rid,offer)
        req,run=f.prepare_tool(ToolCommand('connect',lease),decision='registered:only');run()
        f.repo.register(replace(offer.attachment,state=DiscoveryState.CONNECTED),expected_revision=f.repo.load()['revision'])
        with self.assertRaisesRegex(Exception,'TOOL_VERIFICATION_REQUIRED'):f.tool_command(offer)
        self.assertEqual(f.fake.effect_count,0)

    def test_cleanup_after_host_handoff_is_blocked_not_falsely_clean(self):
        f=self.f;c,v,lease,offer=f.open_tool()
        f.repo.handoff_test('host:a','host:b',expected_revision=f.repo.load()['revision'])
        req,result=f.close_tool(c,lease,reason='CANCEL')
        self.assertEqual(result.status,'WAITING_CAPABILITY')
        self.assertEqual(f.tools.inspect(c.capability_request_id)['state'],'PENDING_CLEANUP')
        self.assertTrue(f.tool_port.store.load()['connections'][c.capability_request_id]['active'])

if __name__=='__main__':unittest.main()
