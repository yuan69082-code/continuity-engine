"""Invoke unchanged reviewer diagnostic functions, retaining separate output."""
import contextlib
import datetime
import json
from pathlib import Path
import runpy
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
runner = runpy.run_path(str(OUT / 'run.py'))
label = sys.argv[1]
assert label and all(c.isalnum() or c in '-_' for c in label)
path = OUT / (label + '.json')
assert not path.exists()
record = {'command': [sys.executable, *sys.argv], 'status': 'STARTED',
          'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sourceBefore': runner['source_hashes']()}
path.write_text(json.dumps(record, indent=2), encoding='utf8')
start = time.perf_counter()
code = 1
with (OUT / (label + '.stdout.log')).open('x', encoding='utf8') as stdout, \
        (OUT / (label + '.stderr.log')).open('x', encoding='utf8') as stderr:
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            probe = runpy.run_path(str(OUT / 'independent/probe_boundaries.py'))
            record['pure'] = probe['pure_probes']()
            record['native'] = [probe['native_fixture_probe'](allowed) for allowed in (True, False)]
            record['status'] = 'FINISHED_DIAGNOSTIC_NOT_TEST_SUITE'
            code = 0
        except BaseException as exc:
            traceback.print_exc()
            record.update(status='ERROR', exceptionType=type(exc).__name__)
        finally:
            record.update(sourceAfter=runner['source_hashes'](), exitCode=code,
                          seconds=round(time.perf_counter()-start, 3),
                          finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps({k: v for k, v in record.items() if k not in {'sourceBefore', 'sourceAfter', 'native'}}, ensure_ascii=False))
print(json.dumps([{k: v for k, v in row.items() if k not in {'host', 'action_results'}} for row in record.get('native', [])], ensure_ascii=False))
raise SystemExit(code)
