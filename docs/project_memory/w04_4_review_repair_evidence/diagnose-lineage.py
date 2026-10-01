"""One bounded TEST diagnosis of new failures; no production state or result."""
import json, time
from test_w04_4_review_repairs import EntryReviewRepairTests

case=EntryReviewRepairTests('test_native_state_derivation_authorized_positive_control')
case.setUp()
try:
    f=case.f; case.state_provider()
    f.submit('记下关注：A_DERIVED_PRIVATE_627')
    f.start_native(); case.state_provider(native_derive=True)
    native=f.continue_native()
    from uuid import uuid5, NAMESPACE_URL
    thinkid=str(uuid5(NAMESPACE_URL,'p14-think|'+native[len('native:'):]))
    session=f.app.adapter.service._thinking._repository.load_think_session(f.state.subject_id,thinkid)
    print(json.dumps({'proposals':case.observations,'result':session.result.to_dict()},ensure_ascii=False))
    print(json.dumps({'native':native,'state_judgments':f.state.intentions.judgments,
        'provider_inputs':[{'external':len(p.external_facts),'fragments':[
            {'source':r.source_id,'stable':r.stable_source_id,'version':r.version,'content':r.content}
            for r in p.continuity_context.composition.snapshot.fragments
            if r.source_id in {'engine.subject-state','engine.current-input'}]} for p in f.provider.inputs],
        'events':[{'id':u.event.event_id,'metadata':u.event.metadata,'changes':[c.to_dict() for c in u.changes]}
                  for u in f.runtime.subject_states.get_update_history(f.state.subject_id)]}, ensure_ascii=False))
finally:
    case.temp.cleanup()
