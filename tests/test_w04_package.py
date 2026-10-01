"""Four W04 responsibilities on one real isolated Engine and original ledgers."""
from dataclasses import replace, asdict
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.domain.awakening import AwakeningResult
from continuity_engine.domain.perception import PerceptionContext
from continuity_engine.domain.environment_access import EnvironmentAccessError


class W04PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix='w04-package-')
        self.root=Path(self.temp.name);self.f=W04EntryFixture(self.root)
    def tearDown(self):
        capture_failure(self,self.root);self.temp.cleanup()

    def test_simulator_rechecks_current_bytes_without_sharing_mutable_facts(self):
        from continuity_engine.testing.w04_tool_fixture import SimulatedConnections
        from continuity_engine.domain.execution import ExecutionError
        from continuity_engine.domain.action_planning import digest
        store=SimulatedConnections(self.f.runtime.data_root/'worlds'/'cache-test',self.f.state.subject_id)
        store.path.parent.mkdir(parents=True,exist_ok=True)
        store.save(store.empty())
        raw=store.path.read_bytes()
        first=store.load();first['connections']['phantom']={'active':True}
        self.assertNotIn('phantom',store.load()['connections'])
        bad=json.loads(raw);bad['document']['facts']=[{'receipt':{},'output':{}}]
        bad['hash']=digest(bad['document'])
        store.path.write_text(json.dumps(bad),encoding='utf8')
        with self.assertRaises(ExecutionError):store.load()
        store.path.write_bytes(raw)
        self.assertEqual(store.load(),json.loads(raw)['document'])

    def test_discovery_history_body_and_native_cross_entry_share_authorities(self):
        f=self.f
        tool=W04ToolFixture(self.root,runtime=f.runtime,manager=f.manager)
        f.bind_tools(tool)
        discovery,offer,_=tool.discover(name='package',route='UI')
        f.reopen()
        # A new authorized continuation obtains its own current Context. The
        # discovery request's older composition is not silently rebound.
        f.submit('核查选店旧记录，供接下来的选择参考。')
        tool.last_context=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception.continuity_context
        lease=tool.lease(discovery,offer,seconds=3600)
        from continuity_engine.domain.temporary_tools import ToolCommand
        connect,run=tool.prepare_tool(ToolCommand('connect',lease),decision='package:connect')
        self.assertEqual(run().status,'COMPLETED')
        verify,run=tool.prepare_tool(ToolCommand('verify',lease,connect.capability_request_id),decision='package:verify')
        self.assertEqual(run().status,'COMPLETED');tool.tools.activate(verify.capability_request_id)
        from continuity_engine.domain.integration_results import format_contract_datetime as fmt
        now=f.runtime.clock.now()
        tool.fake.change(history=[dict(source_id='restaurant:old',root_id='restaurant:root',version='v1',readable=True,
            software_id='software:a',device_id='device:a',session_id='session:a',object_id='object:continuity',
            occurred_at=fmt(now),expires_at=fmt(now+timedelta(hours=1)),content='河边店有窗边桌，山坡店有庭院。')])
        query,run=tool.prepare_step(tool.device.step(tool.tool_command(offer,'query')),decision='package:history')
        self.assertEqual(run().status,'COMPLETED')
        f.submit('周六选河边店还是山坡店？')
        original=f.last_request['requestId']; item=f.entries.adopt_matter(original)
        fragments=f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
        if not any(x.stable_source_id=='execution:'+query.capability_request_id for x in fragments):
            context=f.provider.inputs[-1].continuity_context
            print(json.dumps(dict(stage='before-cleanup-context-selection',target=query.capability_request_id,
                context=context.to_dict()),ensure_ascii=False))
        self.assertTrue(any(x.stable_source_id=='execution:'+query.capability_request_id for x in fragments))
        follow=f.continue_native(); delivery=f.entries.inspect(follow)['deliveries'][0]
        self.assertEqual(delivery['status'],'SENT')
        f.native_mode=False;f.reopen();f.advance()
        answer=f.submit('选河边店的窗边桌。',entry='entry:B',reply_to=delivery['request_id'],item_id=item.item_id)
        self.assertIn('河边店',answer.response.content)
        self.assertEqual(f.entries.inspect(follow)['deliveries'][0]['reply'],'ANSWER_RECORDED')
        # Same original core now runs body action, not a separate fixture result.
        command=f.base.command('body.act',amount=2)
        body,run=f.prepare_step(f.base.device.step(command),'package:body')
        result=run();f.execution.collect(result)
        self.assertEqual(result.status,'COMPLETED')
        op=f.app.ledger.load_operation(f.last_request['requestId']);p=op.domain_progress
        wake=f.app.adapter.service._awakening.get_session(f.state.subject_id,p.wake_session_id)
        context=PerceptionContext.from_awakening(AwakeningResult(context=p.wake_context,session=wake),current_time=f.runtime.clock.now(),context_id='package:sensor')
        perception=f.base.device.perceive_sensor(f.base.use(body=True,purpose='body.sense'),f.base.sensor(),context)
        self.assertEqual(json.loads(perception.external_facts[-1].content)['value'],2)
        identity=f.state.to_dict()
        old_use=f.base.use(body=True)
        old=next(row for row in f.repo.load()['attachments'] if row['attachment_id']=='body:attachment')
        from continuity_engine.domain.environment_access import Attachment
        newer=replace(Attachment.from_dict(old),attachment_id='body:replacement',device_id='body:new')
        f.repo.disable(old['attachment_id'],expected_revision=f.repo.load()['revision'])
        f.repo.register(newer,expected_revision=f.repo.load()['revision'])
        with self.assertRaises(EnvironmentAccessError):f.base.device.observe(old_use)
        with self.assertRaises(EnvironmentAccessError):f.base.device.observe(replace(old_use,generation=old_use.generation+1))
        self.assertEqual(f.state.to_dict(),identity)
        # Current query facts retain history; cleanup removes only the tool's
        # temporary connection. It never erases the original send/body facts.
        tool.last_context=op.domain_progress.perception.continuity_context
        close,result=tool.close_tool(connect,lease,decision='package:cleanup')
        self.assertEqual(result.status,'COMPLETED')
        self.assertEqual(tool.tools.inspect(connect.capability_request_id)['state'],'CLOSED')
        self.assertEqual(f.state.subject_id,tool.state.subject_id)
        self.assertEqual((f.ports['entry:A'].effect_count,f.ports['entry:B'].effect_count),(2,2))
        print(json.dumps(dict(subject=f.state.subject_id,input=original,discovery=discovery,connection=connect.capability_request_id,
            history=query.capability_request_id,matter=item.item_id,native=follow,delivery=delivery,
            reply=f.last_request['requestId'],body=body.capability_request_id,cleanup=close.capability_request_id,
            costs=dict(a=f.ports['entry:A'].credits,b=f.ports['entry:B'].credits,body=f.base.fake.credits))))


if __name__=='__main__':unittest.main()
