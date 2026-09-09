"""One durable P17 test invocation; original outputs survive Fixture cleanup."""
import contextlib
import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('src', 'tests') for p in sorted((ROOT / folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    label, *prefixes = sys.argv[1:]
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in label):
        raise ValueError('invalid evidence label')
    output = DIRECTORY / (label + '.json')
    record = {'command': [sys.executable, *sys.argv],
              'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceBefore': source_hashes(), 'status': 'STARTED'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    start = time.perf_counter()
    code = 1
    with (DIRECTORY / (label + '.stdout.log')).open('x', encoding='utf-8') as stdout, \
            (DIRECTORY / (label + '.stderr.log')).open('x', encoding='utf-8') as stderr:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                loader = unittest.TestLoader()
                if prefixes == ['--independent-probe']:
                    import importlib.util
                    spec=importlib.util.spec_from_file_location('test_independent_edges',DIRECTORY/'independent/test_independent_edges.py')
                    module=importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    discovered=list(flatten(loader.loadTestsFromModule(module)))
                    prefixes=[]
                else:
                    discovered = list(flatten(loader.discover(str(ROOT / 'tests'))))
                record['loaderErrors'] = loader.errors
                if loader.errors:
                    raise RuntimeError('\n'.join(loader.errors))
                tests = [t for t in discovered if not prefixes or t.id().startswith(tuple(prefixes))]
                if not tests:
                    raise ValueError('no matching test identities')
                record['testIdentities'] = [t.id() for t in tests]
                result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
                failed = {getattr(t, 'test_case', t).id() for t, _ in (*result.failures, *result.errors)}
                record.update(run=result.testsRun,
                              passed=result.testsRun - len(failed) - len(result.skipped),
                              failures=[(t.id(), s) for t, s in result.failures],
                              errors=[(t.id(), s) for t, s in result.errors],
                              skips=[(t.id(), s) for t, s in result.skipped])
                code = 0 if result.wasSuccessful() else 1
                record['status'] = 'FINISHED'
            except BaseException as exc:
                import traceback
                traceback.print_exc()
                record.update(status='INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'ERROR',
                              interruption=type(exc).__name__, error=str(exc))
            finally:
                record.update(exitCode=code, seconds=round(time.perf_counter() - start, 3),
                              finishedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              sourceAfter=source_hashes())
                output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k not in {
        'sourceBefore', 'sourceAfter', 'testIdentities', 'failures', 'errors', 'loaderErrors'}}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
