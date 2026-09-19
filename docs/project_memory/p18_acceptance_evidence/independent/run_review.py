"""Read-only Engine review: logs and snapshots are saved only in this directory."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior_runner', OUT.parent / 'p18-storage-final-review-20260914/run_review.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
base = prior.base
base.OUT = OUT
ENGINE = base.ENGINE

if __name__ == '__main__':
    label, *args = sys.argv[1:]
    before = base.snapshot()
    base.save(label + '.before.json', before)
    paths = (OUT, OUT.parent / 'p18-storage-final-review-20260914',
             OUT.parent / 'p18-persistence-review-20260913', OUT.parent / 'p18-repair-review-20260913',
             OUT.parent / 'p18-independent-review-20260912',
             ENGINE / 'docs/project_memory/p18_storage_repair_evidence/independent',
             ENGINE / 'docs/project_memory/p18_f1_h1_evidence/independent',
             ENGINE, ENGINE / 'src', ENGINE / 'tests')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, paths)),
               PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    started = datetime.now(timezone.utc).isoformat()
    at = time.monotonic()
    with (OUT / (label + '.stdout.log')).open('xb') as stdout, (OUT / (label + '.stderr.log')).open('xb') as stderr:
        result = subprocess.run([sys.executable, *args], cwd=ENGINE, env=env, stdout=stdout, stderr=stderr)
    seconds = time.monotonic() - at
    after = base.snapshot()
    base.save(label + '.after.json', after)
    report = dict(command=[sys.executable, *args], cwd=str(ENGINE), startedAt=started,
                  finishedAt=datetime.now(timezone.utc).isoformat(), exitCode=result.returncode,
                  elapsedSeconds=seconds, beforeCount=len(before), afterCount=len(after),
                  changed=[p for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)])
    base.save(label + '.result.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('\n'.join((OUT / (label + '.stderr.log')).read_text(encoding='utf-8').splitlines()[-5:]))
    sys.exit(result.returncode)
