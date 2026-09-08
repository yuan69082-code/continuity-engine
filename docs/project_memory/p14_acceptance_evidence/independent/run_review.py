"""Reuse the P13 read-only review harness; save P14 evidence outside Engine."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('previous_review', OUT.parent / 'p13-independent-review-20260908' / 'run_review.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
previous.OUT = OUT
ENGINE = previous.ENGINE

if __name__ == '__main__':
    label, *command = sys.argv[1:]
    before = previous.snapshot()
    previous.save(label + '.before.json', before)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(OUT), str(ENGINE / 'src'), str(ENGINE / 'tests'))),
               PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    started = time.monotonic()
    with (OUT / (label + '.stdout.log')).open('xb') as stdout, (OUT / (label + '.stderr.log')).open('xb') as stderr:
        result = subprocess.run([sys.executable, *command], cwd=ENGINE, env=env, stdout=stdout, stderr=stderr)
    after = previous.snapshot()
    report = dict(command=[sys.executable, *command], cwd=str(ENGINE), exitCode=result.returncode,
                  elapsedSeconds=time.monotonic() - started, beforeCount=len(before), afterCount=len(after),
                  changed=[p for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)])
    previous.save(label + '.after.json', after)
    previous.save(label + '.result.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print((OUT / (label + '.stderr.log')).read_text(encoding='utf8')[-6500:])
    sys.exit(result.returncode)
