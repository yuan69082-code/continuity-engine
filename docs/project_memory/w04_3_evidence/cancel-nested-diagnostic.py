import json,tempfile
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
from continuity_engine.domain.temporary_tools import ToolCommand
with tempfile.TemporaryDirectory(prefix='w43nested-') as root:
    f=W04ToolFixture(root);rid,offer,_=f.discover();lease=f.lease(rid,offer)
    c,run=f.prepare_tool(ToolCommand('connect',lease),decision='nested:connect');observed=[]
    def cancel():
        f.tool_port.before=None
        try:
            close,result=f.close_tool(c,lease,reason='CANCEL',decision='nested:close')
            observed.append(dict(kind='returned',status=result.status))
        except Exception as exc:
            observed.append(dict(kind='exception',type=type(exc).__name__,static_code=str(exc) if str(exc).isupper() else 'NON_STATIC_OMITTED'))
    f.tool_port.before=cancel;result=run()
    print(json.dumps(dict(interleaving=observed,run_status=result.status,view=f.tools.inspect(c.capability_request_id),
        connections=len(f.tool_port.store.load()['connections']),effects=f.fake.effect_count,credits=f.fake.credits)))
