import tempfile,json
from dataclasses import replace
from continuity_engine.testing.w04_tool_fixture import W04ToolFixture
from continuity_engine.domain.action_planning import digest
with tempfile.TemporaryDirectory(prefix='w04-3-discovery-diagnosis-') as root:
    f=W04ToolFixture(root);rid,offer,_=f.discover()
    other=replace(offer,attachment=replace(offer.attachment,subject_id='other:subject'))
    text=json.dumps(other.to_dict())
    f.discovery.fake.candidate_hook=lambda c:replace(c,content=text,content_hash=digest(text))
    try: f.discovery.next_round()
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__,external_core_is_discovery_core=f.discovery.external.core is f.discovery.core,
            content_bytes=len(text.encode()),results=[dict(status=x.status.value,reason=x.reason,gate_reasons=x.gate_reasons)
            for x in f.discovery.core.last_action.results if x is not None],external_calls=f.discovery.external_calls)))
        raise
