"""Capture the runnable P15 CLI outside its isolated temporary data root."""
from datetime import datetime,timezone
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent


def main():
    name='golden-cli'
    target=OUT/(name+'.json')
    hashes=runpy.run_path(str(OUT/'run.py'))['source_hashes']
    command=[sys.executable,'-m','continuity_engine.testing.p15_subject_fixture']
    record={'command':command,'startedAt':datetime.now(timezone.utc).isoformat(),
            'sourceBefore':hashes(),'status':'STARTED'}
    with target.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
    started=time.perf_counter()
    with (OUT/(name+'.stdout.log')).open('x',encoding='utf-8') as out, \
         (OUT/(name+'.stderr.log')).open('x',encoding='utf-8') as err:
        try:
            result=subprocess.run(command,cwd=ROOT,stdout=out,stderr=err)
            record.update(exitCode=result.returncode,status='FINISHED')
        except BaseException as exc:
            import traceback
            traceback.print_exc(file=err)
            record.update(exitCode=1,status='INTERRUPTED',interruption=type(exc).__name__,error=str(exc))
        finally:
            record.update(seconds=round(time.perf_counter()-started,3),
                finishedAt=datetime.now(timezone.utc).isoformat(),sourceAfter=hashes())
            target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if not k.startswith('source')},ensure_ascii=False))
    return record['exitCode']


if __name__=='__main__':raise SystemExit(main())
