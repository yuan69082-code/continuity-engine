"""One predetermined isolated two-cycle investigation; no automatic retries."""
from pathlib import Path
import contextlib,hashlib,json,re,runpy,sys,tempfile,time,traceback
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from tests.test_p18_runtime_process import runtime_diagnostic
source=runpy.run_path(str(OUT/'run.py'))['source_hashes']

def main():
    label=sys.argv[1];target=OUT/(label+'.json');assert not target.exists()
    r=dict(kind='bounded diagnostic, not a full regression',command=[sys.executable,*sys.argv],at=datetime.now(timezone.utc).isoformat(),sourceBefore=source(),events=[])
    started=time.monotonic()
    with (OUT/(label+'.stdout.log')).open('x',encoding='utf8') as stdout,(OUT/(label+'.stderr.log')).open('x',encoding='utf8') as stderr:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            try:
                with tempfile.TemporaryDirectory(prefix='dr18-') as temp:
                    f=P18Fixture(Path(temp),mode='silence');original=f.work._continue
                    def continuation(request):
                        try:return original(request)
                        except Exception as exc:
                            code=str(exc)
                            r['events'].append(dict(stage='native-exception',exceptionType=type(exc).__name__,
                                code=code if re.fullmatch('[A-Z][A-Z_0-9]+',code) else None,
                                messageHash=hashlib.sha256(code.encode()).hexdigest(),
                                frames=[dict(file=Path(t.filename).name,line=t.lineno,function=t.name) for t in traceback.extract_tb(exc.__traceback__)]))
                            raise
                    f.work._continue=continuation
                    def snap(stage):
                        sessions=[dict(think_id=s.think_id,status=s.status.value,completed=s.completed_successfully,
                            state_written=s.state_written_back,update_id=s.state_update_id,
                            error_code=s.error if s.error and re.fullmatch('[A-Z][A-Z_0-9]+',s.error) else None)
                            for s in f.work.thinking.get_sessions(f.state.subject_id)]
                        r['events'].append(dict(stage=stage,subjectRevision=f.state.revision,sessions=sessions,snapshot=runtime_diagnostic(f)))
                    with f.host.running():
                        f.advance(3600);f.host.tick();f.advance(60);f.host.tick();snap('first-cognition')
                        f.control('PAUSE');f.advance(3600);f.host.tick();snap('paused')
                        f.control('RESUME');f.host.tick();snap('resumed-maintenance')
                        f.advance(60);f.host.tick();snap('second-cognition')
                        r['advanced']=f.state.revision==3
                        f.control('STOP');r['stopped']=f.host.tick() is False
                    r['hostReleased']=not f.store.host_alive()
                r['outcome']='ADVANCED' if r['advanced'] else 'NOT_ADVANCED'
            except Exception:
                traceback.print_exc();r['outcome']='DIAGNOSTIC_ERROR'
            finally:
                r.update(sourceAfter=source(),seconds=round(time.monotonic()-started,3))
                with target.open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(outcome=r['outcome'],seconds=r['seconds'],events=len(r['events']))))

if __name__=='__main__':main()
