"""One controlled pre-connect cancellation, then replay the original request."""
import json,tempfile
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
from continuity_engine.domain.temporary_tools import ToolCommand
with tempfile.TemporaryDirectory(prefix='w43cancel-') as root:
    f=W04ToolFixture(root);rid,offer,_=f.discover();lease=f.lease(rid,offer)
    connection,replay=f.prepare_tool(ToolCommand('connect',lease),decision='probe:connect')
    close,result=f.close_tool(connection,lease,reason='CANCEL',decision='probe:cancel')
    after=replay(True)
    record=dict(cancel=result.status,replay=after.status,connections=len(f.tool_port.store.load()['connections']),
                effects=f.fake.effect_count,credits=f.fake.credits)
    print(json.dumps(record))
    assert record['connections']==0,'cancelled pending connection must not be opened by replay'
