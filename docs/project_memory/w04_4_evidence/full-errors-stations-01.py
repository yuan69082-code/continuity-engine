"""Two predeclared original failing tests, once each; nested diagnostic times."""
import gc
import json
import time
import unittest
from pathlib import Path
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

original_submit = W04EntryFixture.submit

def submit(self, text, **kwargs):
    if kwargs.get('entry') != 'entry:B' or not kwargs.get('reply_to'):
        return original_submit(self, text, **kwargs)
    original_prepare = self.core.recall._prepare
    def prepare(perception, operation, save, **options):
        records = {}; restores = []; overhead = [0.0]; reads = {}; saved = []
        def measure(obj, name, label):
            method = getattr(obj, name)
            def timed(*args, **kw):
                start = time.perf_counter()
                try: return method(*args, **kw)
                finally:
                    end = time.perf_counter()
                    row = records.setdefault(label, {'calls': 0, 'ms': 0})
                    row['calls'] += 1; row['ms'] += (end-start)*1000
                    overhead[0] += time.perf_counter()-end
            setattr(obj, name, timed); restores.append((obj, name, method))
        for obj, name, label in (
            (self.core.router,'route','Router'), (self.core.composer,'compose','Composer'),
            (self.core.recall,'_authorize','recall.authorize'),
            (self.core.recall,'_preference_candidates','candidate.interpretation'),
            (self.repo,'load','Environment'),
            (self.app.ledger,'_load_capability_document','E5-A-read'),
            (self.app.ledger,'_load_operations','operations'),
            (self.execution,'results_for_context','results'),
            (self.entries,'origins','entry.origins'),
            (self.entries,'reference_allowed','entry.permission'),
            (self.core.subject_states,'get_update_history','state.history')):
            measure(obj,name,label)
        if getattr(self,'tool_fixture',None):
            tool=self.tool_fixture
            for obj,name,label in ((tool.tools,'candidates','tool.candidates'),
                (tool.tools,'conditions','tool.conditions'), (tool.tools,'require_device','tool.device-current'),
                (tool.tools,'query','tool.query'), (tool.tool_port.store,'load','tool.store')):
                measure(obj,name,label)
        read_bytes=Path.read_bytes
        def read(path):
            start=time.perf_counter()
            try:return read_bytes(path)
            finally:
                end=time.perf_counter()
                # File basenames only; no document content or private root path.
                row=reads.setdefault(path.name,{'calls':0,'ms':0})
                row['calls']+=1;row['ms']+=(end-start)*1000
                overhead[0]+=time.perf_counter()-end
        Path.read_bytes=read
        gc_start={}; gc_ms=[0.0]
        def gc_event(phase, info):
            if phase=='start':gc_start[info['generation']]=time.perf_counter()
            elif info['generation'] in gc_start:
                gc_ms[0]+=(time.perf_counter()-gc_start.pop(info['generation']))*1000
        gc.callbacks.append(gc_event)
        def capture(record):
            saved.append({k:record.get(k) for k in ('status','stop_reason','elapsed_ms','retrieved_count')})
            return save(record)
        start=time.perf_counter(); cpu=time.process_time()
        try:return original_prepare(perception,operation,capture,**options)
        finally:
            elapsed=(time.perf_counter()-start)*1000; cpu_ms=(time.process_time()-cpu)*1000
            gc.callbacks.remove(gc_event); Path.read_bytes=read_bytes
            for obj,name,method in reversed(restores):setattr(obj,name,method)
            print(json.dumps({'stage':'before-cleanup-reply-recall','request':operation.request_id,
                'wall_ms':elapsed,'cpu_ms':cpu_ms,'gc_ms':gc_ms[0],
                'accounting_overhead_ms':overhead[0]*1000,'nested_not_additive':records,
                'current_reads':reads,'saved_recall':saved}),flush=True)
    self.core.recall._prepare=prepare
    try:return original_submit(self,text,**kwargs)
    finally:self.core.recall._prepare=original_prepare

W04EntryFixture.submit=submit
names=[
 'test_w04_4_continuity.CrossEntryTests.test_simulated_ui_question_followup_reply_same_engine_and_matter',
 'test_w04_package.W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities']
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(0 if result.wasSuccessful() else 1)
