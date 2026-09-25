"""Exclusive W02 integration evidence runner; records every attempt once."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'docs/project_memory/w02_c_evidence'))
from audit import collect  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: run.py LABEL UNITTEST_ARGS...')
    label = sys.argv[1]
    if not label.replace('-', '').replace('_', '').isalnum():
        raise SystemExit('invalid label')
    command = [sys.executable, '-m', 'unittest', *sys.argv[2:]]
    before = collect()
    started_at = datetime.now(timezone.utc)
    paths = {suffix: HERE / f'{label}.{suffix}' for suffix in
             ('started.json', 'stdout.log', 'stderr.log', 'json')}
    for path in paths.values():
        if path.exists():
            raise SystemExit(f'evidence label already exists: {path.name}')
    with paths['started.json'].open('x', encoding='utf-8') as stream:
        json.dump({'label': label, 'command': command, 'started_at': started_at.isoformat(),
                   'source_fingerprint': before['sourceHash']}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
               PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))))
    start = time.monotonic()
    with paths['stdout.log'].open('x') as stdout, paths['stderr.log'].open('x') as stderr:
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   stdout=stdout, stderr=stderr, check=False)
    after = collect()
    result = {
        'label': label, 'command': command, 'cwd': str(ROOT),
        'started_at': started_at.isoformat(), 'ended_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.monotonic() - start, 'exit_code': completed.returncode,
        'source_fingerprint_before': before['sourceHash'],
        'source_fingerprint_after': after['sourceHash'],
        'source_inventory_identical': before['source'] == after['source'],
        'formal_identical': before['formal_files'] == after['formal_files'],
        'protected_identical': before['protected'] == after['protected'],
        'excluded_identical': before['excluded'] == after['excluded'],
        'stdout_sha256': sha(paths['stdout.log']),
        'stderr_sha256': sha(paths['stderr.log']),
    }
    with paths['json'].open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
