"""Bounded isolated example through normal discovery/action/receipt paths."""
import json,tempfile
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
from continuity_engine.domain.temporary_tools import ToolCommand

with tempfile.TemporaryDirectory(prefix='w43example-') as root:
    f=W04ToolFixture(root);discovery,offer,_=f.discover()
    lease=f.lease(discovery,offer)
    connection,_=f.prepare_tool(ToolCommand('connect',lease),decision='example:connect')
    f.change(login=False)
    waiting=f.tools.advance(connection.capability_request_id,f.action_factory)
    assert waiting['state']=='WAITING_CONDITIONS' and waiting['missing']==['LOGIN']
    f.change(login=True)
    result=f.tools.advance(connection.capability_request_id,f.action_factory)
    replay=f.tools.advance(connection.capability_request_id,f.action_factory)
    assert result['state']==replay['state']=='CLOSED'
    assert (f.fake.effect_count,f.fake.credits)==(1,1)
    print(json.dumps(dict(subject=f.state.subject_id,environment='TEST',
        information_request=f.last_request['requestId'],discovery_request=discovery,
        candidate_source=lease.source_id,candidate_hash=lease.offer_hash,offer=offer.to_dict(),
        connection_request=connection.capability_request_id,waiting=waiting,result=result,replay=replay,
        effects=f.fake.effect_count,test_credits=f.fake.credits,discovery_calls=f.discovery.external_calls,
        final_revision=f.state.revision),ensure_ascii=False))

with tempfile.TemporaryDirectory(prefix='w43history-') as root:
    f=W04ToolFixture(root);c,v,lease,offer=f.open_tool()
    request,run=f.prepare_step(f.device.step(f.tool_command(offer)),'example:history')
    assert run().status=='COMPLETED'
    perception=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
    context=f.device.history_context(request.capability_request_id,perception)
    selected=[dict(fragment_id=x.fragment_id,source=x.stable_source_id) for x in context.snapshot.fragments]
    assert any(x['source']=='execution:'+request.capability_request_id for x in selected)
    print(json.dumps(dict(kind='N21',subject=f.state.subject_id,connection_request=c.capability_request_id,
        query_request=request.capability_request_id,context_hash=context.snapshot.snapshot_hash,
        sources=selected,effects=f.fake.effect_count,test_credits=f.fake.credits),ensure_ascii=False))
