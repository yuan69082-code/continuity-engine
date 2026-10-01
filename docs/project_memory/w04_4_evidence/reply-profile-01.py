"""One bounded third-turn measurement; timings are nested, not additive."""
from pathlib import Path
import tempfile, json, time
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

with tempfile.TemporaryDirectory(prefix='w44r-') as root:
    f=W04EntryFixture(Path(root)); f.submit('周六选河边店还是山坡店？')
    item=f.entries.adopt_matter(f.last_request['requestId']); follow=f.continue_native()
    delivery=f.entries.inspect(follow)['deliveries'][0]
    f.advance(); f.native_mode=False; f.reopen()
    records={}; originals=[]
    def measure(obj, name, label=None):
        original=getattr(obj,name); originals.append((obj,name,original))
        def wrapped(*args, **kw):
            row=records.setdefault(label or name, {'calls':0, 'seconds':0.0}); start=time.perf_counter()
            try:return original(*args, **kw)
            finally:row['calls']+=1;row['seconds']+=time.perf_counter()-start
        setattr(obj,name,wrapped)
    prepare=f.core.recall._prepare
    def measured(*args,**kw):
        for name in ('scoped_state','origins','binding','transfer','reference_allowed'):
            measure(f.entries,name)
        measure(f.repo,'load','environment.load')
        from continuity_engine.domain.cross_entry import EntryBinding
        measure(EntryBinding, 'from_dict')
        measure(f.access, '_available')
        measure(f.core.subject_states,'load','state.load')
        measure(f.core.subject_states,'get_update_history')
        measure(f.app.ledger,'_load_operations')
        measure(f.app.ledger,'_load_capability_document')
        measure(f.core.router,'route')
        measure(f.core.composer,'compose')
        measure(f.core.recall,'_authorize')
        measure(f.core.recall,'_preference_candidates')
        import cProfile, pstats, sys
        profile=cProfile.Profile()
        try:return profile.runcall(prepare,*args,**kw)
        finally:
            pstats.Stats(profile,stream=sys.stdout).strip_dirs().sort_stats('cumulative').print_stats(35)
            for obj,name,original in reversed(originals):setattr(obj,name,original)
            print(json.dumps({'stage':'reply-recall-only','nested_metrics':records}))
    f.core.recall._prepare=measured
    try:f.submit('选河边店，窗边那张桌。',entry='entry:B',item_id=item.item_id,reply_to=delivery['request_id'])
    except Exception as error:
        print(json.dumps({'type':type(error).__name__,'recall':{k:v for k,v in (f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.recall_progress[-1]).items()
            if k in ('status','stop_reason','elapsed_ms','retrieved_count')}}))
    finally:
        print(json.dumps({'model_calls':len(f.provider.inputs),'effect_counts':{k:p.effect_count for k,p in f.ports.items()}}))
