"""Unique-label evidence runner. Runs exactly the requested set, never retries."""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'tests')]
os.chdir(ROOT)
os.environ.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONPATH=str(ROOT/'src'))


def source():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests') for p in sorted((ROOT/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def identities(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from identities(test)
        else:
            yield test.id()


class CountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successful_identities = []

    def addSuccess(self, test):
        self.successful_identities.append(test.id())
        super().addSuccess(test)


if __name__ == '__main__':
    label = sys.argv[1]
    if not label.replace('-', '').isalnum():
        raise ValueError('unsafe evidence label')
    target = HERE/(label+'.json')
    assert not target.exists(), 'labels are immutable'
    data = dict(status='STARTED', command=[sys.executable, '-B', *sys.argv], pid=os.getpid(),
                startedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), sourceBefore=source())
    def save():
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    save()
    start = time.monotonic()
    code = 2
    with (HERE/(label+'.stdout.log')).open('w',encoding='utf-8') as out, (HERE/(label+'.stderr.log')).open('w',encoding='utf-8') as err:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                loader = unittest.TestLoader()
                suite = loader.loadTestsFromNames(sys.argv[2:]) if len(sys.argv)>2 else loader.discover('tests')
                data['testIdentities'] = list(identities(suite))
                data['loaderErrors'] = loader.errors
                save()
                result = unittest.TextTestRunner(stream=err, verbosity=2, resultclass=CountedResult).run(suite)
                code = 0 if result.wasSuccessful() and not loader.errors else 1
                data.update(status='FINISHED', run=result.testsRun, passed=len(result.successful_identities), successfulIdentities=result.successful_identities,
                    failures=[(t.id(),e) for t,e in result.failures], errors=[(t.id(),e) for t,e in result.errors],
                    skips=[(t.id(),e) for t,e in result.skipped])
            except BaseException:
                data['status']='INTERRUPTED_OR_RUNNER_ERROR'
                traceback.print_exc(file=err)
    data.update(exitCode=code, seconds=round(time.monotonic()-start,3), sourceAfter=source(),
                finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save()
    print(json.dumps({k:v for k,v in data.items() if k in ('status','run','passed','exitCode','seconds')},ensure_ascii=False))
    sys.exit(code)
