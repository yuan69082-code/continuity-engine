"""One instrumented original process scenario; keep assertions and timeouts."""
from pathlib import Path
import contextlib,json,runpy,sys,time,unittest
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_p18_runtime_process as original
source=runpy.run_path(str(OUT/'run.py'))['source_hashes']
CHILD=r'''
import sys,json,re,traceback,hashlib
from pathlib import Path
from continuity_engine.services.runtime_cognition import RuntimeCognition
from continuity_engine.runtime import main
old=RuntimeCognition._continue
def checked(self,request):
    try:return old(self,request)
    except Exception as exc:
        code=str(exc)
        print(json.dumps(dict(stage='native-exception',exceptionType=type(exc).__name__,
            code=code if re.fullmatch('[A-Z][A-Z_0-9]+',code) else None,
            messageHash=hashlib.sha256(code.encode()).hexdigest(),
            frames=[dict(file=Path(t.filename).name,line=t.lineno,function=t.name) for t in traceback.extract_tb(exc.__traceback__)])),file=sys.stderr,flush=True)
        raise
RuntimeCognition._continue=checked
raise SystemExit(main(['start','--root',sys.argv[1]]))
'''

def main():
    label=sys.argv[1];target=OUT/(label+'.json');assert not target.exists()
    record=dict(command=[sys.executable,*sys.argv],startedAt=datetime.now(timezone.utc).isoformat(),sourceBefore=source())
    started=time.monotonic()
    case=original.RuntimeProcessTests('test_idle_and_subject_silence_do_not_end_process')
    start=case.start
    case.start=lambda custom=None:start(custom or [sys.executable,'-c',CHILD,str(case.root)])
    with (OUT/(label+'.stdout.log')).open('x',encoding='utf8') as stdout,(OUT/(label+'.stderr.log')).open('x',encoding='utf8') as stderr:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
    record.update(status='FINISHED',run=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        failures=[(t.id(),s) for t,s in result.failures],errors=[(t.id(),s) for t,s in result.errors],skips=result.skipped,
        seconds=round(time.monotonic()-started,3),exitCode=0 if result.wasSuccessful() else 1,
        sourceAfter=source(),testIdentities=[case.id()],instrumentation='subprocess diagnostic wrapper only; original assertions and timeout unchanged')
    with target.open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:record[k] for k in ('status','run','passed','seconds','exitCode')}))
    return record['exitCode']

if __name__=='__main__':raise SystemExit(main())
