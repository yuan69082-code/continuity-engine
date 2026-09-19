"""P18 closure review probes; separate from formal test identity counting."""
import contextlib
import datetime
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import runpy

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
source_hashes=runpy.run_path(str(OUT/'run.py'))['source_hashes']

class ControlEdgeProbe(unittest.TestCase):
    def test_old_control_does_not_reapply_after_many_owner_commands(self):
        with tempfile.TemporaryDirectory(prefix='p18-control-edge-') as directory:
            f=P18Fixture(Path(directory))
            def control(operation,identity):
                return f.host.control(operation,command_id=identity,expected_revision=None,handle='p18-test-owner')
            control('PAUSE','original-pause')
            for i in range(130):control('PAUSE' if i%2==0 else 'RESUME','later-'+str(i))
            before=f.store.path.read_bytes()
            self.assertEqual(f.host.query()['desired'],'RUNNING')
            control('PAUSE','original-pause')
            self.assertEqual(f.store.path.read_bytes(),before)
            self.assertEqual(f.host.query()['desired'],'RUNNING')

    def test_control_identity_is_not_stored_as_raw_material(self):
        with tempfile.TemporaryDirectory(prefix='p18-control-edge-') as directory:
            f=P18Fixture(Path(directory));material='synthetic-opaque-control-material-18'
            f.host.control('PAUSE',command_id=material,expected_revision=None,handle='p18-test-owner')
            self.assertNotIn(material,json.dumps(f.host.query()))
            for path in f.runtime.data_root.rglob('*.json'):
                self.assertNotIn(material,path.read_text(encoding='utf8'))

    def test_scaled_clock_preserves_legal_subject_lifecycle_control(self):
        with tempfile.TemporaryDirectory(prefix='p18-control-edge-') as directory:
            f=P18Fixture(Path(directory),test_clock_rate=1)
            with f.host.running():
                f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
                self.assertEqual(f.state.revision,2)
                f.lifecycle('SUSPEND')
                f.host.tick()
                self.assertEqual(f.host.query()['subject_lifecycle'],'SUSPENDED')
                self.assertEqual(f.provider.calls,1)

def main():
    label=sys.argv[1];path=OUT/(label+'.json');assert not path.exists()
    record=dict(command=[sys.executable,*sys.argv],startedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceBefore=source_hashes())
    start=time.perf_counter()
    with (OUT/(label+'.stdout.log')).open('x',encoding='utf8') as out,(OUT/(label+'.stderr.log')).open('x',encoding='utf8') as err:
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ControlEdgeProbe))
    record.update(run=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        failures=[(t.id(),v) for t,v in result.failures],errors=[(t.id(),v) for t,v in result.errors],skips=result.skipped,
        exitCode=0 if result.wasSuccessful() else 1,status='FINISHED',seconds=round(time.perf_counter()-start,3),
        finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),sourceAfter=source_hashes())
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:record[k] for k in ('run','passed','seconds','exitCode')}))
    return record['exitCode']

if __name__=='__main__':raise SystemExit(main())
