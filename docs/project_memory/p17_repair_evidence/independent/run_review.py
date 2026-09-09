"""Read-only Engine test review, unique immutable logs in the planning workspace."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review_base', OUT.parent / 'p13-independent-review-20260908/run_review.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT
ENGINE = base.ENGINE

if __name__ == '__main__':
    label, *command = sys.argv[1:]
    before = base.snapshot()
    base.save(label + '.before.json', before)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(OUT), str(ENGINE), str(ENGINE / 'src'), str(ENGINE / 'tests'))),
               PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    start = time.monotonic()
    with (OUT / (label + '.stdout.log')).open('xb') as stdout, (OUT / (label + '.stderr.log')).open('xb') as stderr:
        result = subprocess.run([sys.executable, *command], cwd=ENGINE, env=env, stdout=stdout, stderr=stderr)
    elapsed = time.monotonic() - start
    after = base.snapshot()
    base.save(label + '.after.json', after)
    report = dict(command=[sys.executable, *command], cwd=str(ENGINE), exitCode=result.returncode,
                  elapsedSeconds=elapsed, beforeCount=len(before), afterCount=len(after),
                  changed=[p for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)])
    base.save(label + '.result.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print((OUT / (label + '.stderr.log')).read_text(encoding='utf-8')[-4500:], flush=True)
    sys.exit(result.returncode)
