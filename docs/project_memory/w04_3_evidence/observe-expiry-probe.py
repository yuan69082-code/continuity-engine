import tempfile,json
from datetime import timedelta
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
with tempfile.TemporaryDirectory(prefix='wt-obs-') as root:
    f=W04ToolFixture(root);c,v,lease,offer=f.open_tool(seconds=1)
    command=f.tool_command(offer,'type',text='unused');f.runtime.clock.advance(timedelta(seconds=1))
    before=f.fake.store.load()['revision']
    try:
        observation=f.device.observe(command.observation.use)
    except Exception as exc:
        print(json.dumps(dict(refused=True,error=type(exc).__name__,effects=f.fake.effect_count,revision=before)))
    else:
        print(json.dumps(dict(refused=False,status=observation.status,effects=f.fake.effect_count,revision=before)))
        raise AssertionError('Expired temporary authorization must not allow a fresh observation')
