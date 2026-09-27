"""Immutable labelled subprocess evidence; no Engine or test semantics changes."""
import datetime, json, os, pathlib, runpy, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def main():
    label=sys.argv[1];args=sys.argv[2:]
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in label):raise ValueError('label')
    paths=[HERE/(label+'.'+s) for s in ('json','stdout.log','stderr.log')]
    if any(p.exists() for p in paths):raise ValueError('existing label')
    cmd=[sys.executable,*args];before=SNAP['source']();start=time.perf_counter()
    record=dict(label=label,command=cmd,cwd=str(ROOT),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='STARTED',source_before=before,hash_before=SNAP['fingerprint'](before))
    paths[0].write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join((str(ROOT),str(ROOT/'src'),str(ROOT/'tests')))}
    with paths[1].open('x',encoding='utf8') as out,paths[2].open('x',encoding='utf8') as err:
        try:
            done=subprocess.run(cmd,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=7200)
            record.update(status='COMPLETED',exit_code=done.returncode)
        except BaseException as exc:
            record.update(status='INTERRUPTED',error_type=type(exc).__name__,exit_code=None)
        finally:
            after=SNAP['source']();record.update(duration_seconds=round(time.perf_counter()-start,3),source_after=after,hash_after=SNAP['fingerprint'](after))
            paths[0].write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in record.items() if not k.startswith('source_')}))
    return record['exit_code'] if record['exit_code'] is not None else 2
if __name__=='__main__':sys.exit(main())
