"""One bounded instrumented package run; nested times, not acceptance timing."""
import json,time,unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from tests.test_w04_package import W04PackageTests
original=W04EntryFixture.submit
def submit(self,text,**kwargs):
    if text!='周六选河边店还是山坡店？':return original(self,text,**kwargs)
    records={};restores=[]
    def measure(obj,name,label):
        method=getattr(obj,name)
        def timed(*args,**kw):
            at=time.perf_counter()
            try:return method(*args,**kw)
            finally:
                row=records.setdefault(label,{'calls':0,'ms':0});row['calls']+=1;row['ms']+=(time.perf_counter()-at)*1000
        setattr(obj,name,timed);restores.append((obj,name,method))
    preparation=self.core.recall._prepare
    def prepare(*a,**k):
        tool=self.tool_fixture
        for obj,name,label in ((self.core.router,'route','Router'),(self.core.composer,'compose','Composer'),
            (self.repo,'load','Environment'),(self.app.ledger,'_load_capability_document','E5-A-read'),
            (self.app.ledger,'_load_operations','operations'),(self.execution,'results_for_context','results'),
            (tool.tools,'candidates','tool.candidates'),(tool.tools,'conditions','tool.conditions'),
            (tool.tools,'require_device','tool.device-current'),(tool.tools,'query','tool.query'),
            (tool.tool_port.store,'load','tool.native-store'),(tool.discovery.fake,'query_receipt','discovery.receipt'),
            (self.entries,'origins','entry.origins')):measure(obj,name,label)
        at=time.perf_counter()
        try:return preparation(*a,**k)
        finally:
            print(json.dumps({'stage':'package-recall','elapsed_ms':(time.perf_counter()-at)*1000,'nested':records}))
            for obj,name,method in reversed(restores):setattr(obj,name,method)
    self.core.recall._prepare=prepare
    return original(self,text,**kwargs)
W04EntryFixture.submit=submit
suite=unittest.defaultTestLoader.loadTestsFromTestCase(W04PackageTests)
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
