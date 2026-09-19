"""Read-only Engine review; logs and probes belong to the planning workspace."""
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
PRIOR=OUT.parent/'p18-independent-review-20260912'
spec=importlib.util.spec_from_file_location('base',OUT.parent/'p13-independent-review-20260908/run_review.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);base.OUT=OUT
ENGINE=base.ENGINE

if __name__=='__main__':
    label,*args=sys.argv[1:]
    before=base.snapshot();base.save(label+'.before.json',before)
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(map(str,(OUT,PRIOR,ENGINE,ENGINE/'src',ENGINE/'tests'))),
             PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
    started=datetime.now(timezone.utc).isoformat();at=time.monotonic()
    with (OUT/(label+'.stdout.log')).open('xb') as out,(OUT/(label+'.stderr.log')).open('xb') as err:
        p=subprocess.run([sys.executable,*args],cwd=ENGINE,env=env,stdout=out,stderr=err)
    seconds=time.monotonic()-at;after=base.snapshot();base.save(label+'.after.json',after)
    result=dict(command=[sys.executable,*args],cwd=str(ENGINE),startedAt=started,finishedAt=datetime.now(timezone.utc).isoformat(),
        exitCode=p.returncode,elapsedSeconds=seconds,beforeCount=len(before),afterCount=len(after),
        changed=[k for k in sorted(before.keys()|after.keys()) if before.get(k)!=after.get(k)])
    base.save(label+'.result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print((OUT/(label+'.stderr.log')).read_text(encoding='utf-8')[-5000:])
    sys.exit(p.returncode)
