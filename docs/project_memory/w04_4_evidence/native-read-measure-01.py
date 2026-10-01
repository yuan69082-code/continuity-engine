"""One native attempt with small counters; unchanged original budgets."""
import json
from pathlib import Path
import tempfile
import time
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

with tempfile.TemporaryDirectory(prefix='w44m-') as root:
    f=W04EntryFixture(Path(root));f.submit('周六选择哪家店？')
    f.entries.adopt_matter(f.last_request['requestId']);f.start_native()
    ledger=f.app.ledger; counts={}; originals=[]
    def measure(obj,name,scope=None):
        original=getattr(obj,name); originals.append((obj,name,original))
        def wrapped(*args,**kwargs):
            key=name+(' scoped' if scope is not None and scope.get() is not None else ' unscoped')
            row=counts.setdefault(key,{'calls':0,'seconds':0.0});start=time.perf_counter()
            try:return original(*args,**kwargs)
            finally:row['calls']+=1;row['seconds']+=time.perf_counter()-start
        setattr(obj,name,wrapped)
    measure(ledger,'_load_operations',ledger._operation_read_scope)
    measure(ledger,'_load_capability_document',ledger._capability_read_scope)
    measure(f.repo,'load')
    native=f.native_work._continue
    def once(request):
        try:return native(request)
        finally:
            print(json.dumps({'stage':'one-native-opportunity','metrics':counts,
                'operation_bytes':ledger.operation_path.stat().st_size,
                'capability_bytes':ledger.capability_path.stat().st_size}))
            # The measurement takes one cognition attempt only; controller then
            # stops observing. This exception is confined to this TEST harness.
            raise KeyboardInterrupt('TEST_ONE_ATTEMPT_OBSERVED')
    f.native_work._continue=once
    try:f.continue_native()
    except KeyboardInterrupt:pass
    finally:
        for obj,name,method in originals:setattr(obj,name,method)
        print(json.dumps({'effects':{k:p.effect_count for k,p in f.ports.items()},
                          'model_calls':len(f.provider.inputs), 'host_attached':f.host.owner is not None}))
