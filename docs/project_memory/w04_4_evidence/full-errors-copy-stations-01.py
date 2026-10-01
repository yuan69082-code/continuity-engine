"""One package run to split Environment copy/path work; not a green-seeking rerun."""
import json, time, unittest
from pathlib import Path
import continuity_engine.storage.json_environment_repository as env
import continuity_engine.storage.json_integration_repository as journal
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

here=Path(__file__).resolve().parent
source=(here/'full-errors-stations-01.py').read_text(encoding='utf8')
namespace={}
exec(compile(source[:source.index('W04EntryFixture.submit=submit')], 'full-errors-stations-01.py', 'exec'),namespace)
original_submit=W04EntryFixture.submit
def submit(self,text,**kwargs):
    if kwargs.get('entry')!='entry:B' or not kwargs.get('reply_to'):
        return original_submit(self,text,**kwargs)
    active=[0]; records={}; restore=[]
    def wrap(obj,name,label,condition=lambda:True):
        original=getattr(obj,name)
        def invoke(*a,**k):
            if not condition():return original(*a,**k)
            start=time.perf_counter()
            try:return original(*a,**k)
            finally:
                row=records.setdefault(label,{'calls':0,'ms':0})
                row['calls']+=1;row['ms']+=(time.perf_counter()-start)*1000
        setattr(obj,name,invoke);restore.append((obj,name,original))
    load=env.JsonEnvironmentRepository.load
    def loaded(*a,**k):
        active[0]+=1
        try:return load(*a,**k)
        finally:active[0]-=1
    env.JsonEnvironmentRepository.load=loaded
    wrap(env,'deepcopy','environment.copy')
    wrap(env.json,'loads','json.parse',lambda:active[0]>0)
    wrap(Path,'lstat','environment.lstat',lambda:active[0]>0)
    wrap(Path,'exists','environment.exists',lambda:active[0]>0)
    wrap(journal,'deepcopy','journal.copy')
    try:return namespace['submit'](self,text,**kwargs)
    finally:
        for obj,name,original in reversed(restore):setattr(obj,name,original)
        env.JsonEnvironmentRepository.load=load
        print(json.dumps({'stage':'reply-environment-and-journal-components','nested':records}),flush=True)
W04EntryFixture.submit=submit
name='test_w04_package.W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities'
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(name))
raise SystemExit(0 if result.wasSuccessful() else 1)
