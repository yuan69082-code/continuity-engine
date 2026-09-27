"""Bounded TEST chain examples. No formal data, UI desktop, or real service."""
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import runpy
import tempfile
import time

from continuity_engine.domain.awakening import AwakeningResult
from continuity_engine.domain.perception import PerceptionContext
from continuity_engine.domain.integration_results import format_contract_datetime as fmt
from continuity_engine.testing.w04_device_fixture import W04DeviceFixture
from continuity_engine.testing.persistence import tree_inventory_hash

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
destination=HERE/'chain-examples.json'
if destination.exists():raise SystemExit('example already archived')
source_before=SNAP['fingerprint'](SNAP['source']());start=time.perf_counter()
examples=[]
for kind in ('body','ui','history'):
    with tempfile.TemporaryDirectory(prefix='w4e-') as directory:
        f=W04DeviceFixture(Path(directory));f.submit()
        identity=f.state.subject_id;revision=f.state.revision
        if kind=='body':
            f.submit_device(f.command('body.act',amount=2))
            request=f.core.last_action.requests[0]
            progress=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress
            wake=f.app.adapter.service._awakening.get_session(identity,progress.wake_session_id)
            context=PerceptionContext.from_awakening(AwakeningResult(context=progress.wake_context,session=wake),
                current_time=f.runtime.clock.now(),context_id='sample:sensor')
            perception=f.device.perceive_sensor(f.use(body=True,purpose='body.sense'),f.sensor(),context)
            extras={'sensor_fact':perception.external_facts[-1].to_dict()}
        elif kind=='ui':
            for i,(op,arguments) in enumerate((('click',{}),('type',{'text':'isolated simulated document'}),('save',{}))):
                request,run=f.prepare(f.command(op,**arguments),decision='sample:'+str(i))
                result=run();f.execution.collect(result)
                assert result.results[0].status.value=='SUCCEEDED'
            extras={'app_state':f.fake.store.load()['view']}
        else:
            now=f.runtime.clock.now()
            row=dict(source_id='source:sample',root_id='root:sample',version='v1',readable=True,
                software_id='software:a',device_id='device:a',session_id='session:a',object_id='object:continuity',
                occurred_at=fmt(now),expires_at=fmt(now+timedelta(hours=1)),content='continuity historical simulation note')
            f.fake.change(history=[row]);request,run=f.prepare(f.command('query',history=asdict(f.scope())),decision='sample:query')
            result=run();f.execution.collect(result)
            perception=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
            composed=f.device.history_context(request.capability_request_id,perception)
            extras={'context_hash':composed.snapshot.snapshot_hash,'references':[
                {'source':x.source_id,'stable_id':x.stable_source_id,'hash':x.content_hash,'roots':list(x.provenance_roots)}
                for x in composed.snapshot.fragments if x.source_type=='execution_result']}
        before=tree_inventory_hash(f.runtime.data_root)
        read=f.device.inspect(request.capability_request_id)
        assert tree_inventory_hash(f.runtime.data_root)==before
        assert f.state.subject_id==identity and f.state.revision==revision
        examples.append({'kind':kind,'subject_id':identity,'message_request_id':f.last_request['requestId'],
            'capability_request_id':request.capability_request_id,'request_hash':request.request_hash,
            'argument_hash':request.step.argument_hash,'observation_id':request.step.input_payload['observation']['observation_id'],
            'read_only_result':read,'effects':f.fake.effect_count,'credits':f.fake.credits,'revision':revision,
            'subject_unchanged':True,'read_only_zero_writes':True,'temporary_root_released':True,**extras})
data=dict(source_before=source_before,source_after=SNAP['fingerprint'](SNAP['source']()),
    seconds=round(time.perf_counter()-start,3),examples=examples,status='COMPLETED',exit_code=0)
destination.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':data['status'],'seconds':data['seconds'],'examples':len(examples),'source':data['source_after']}))
