"""Exclusive W02-C repair evidence runner; never overwrites earlier records."""
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
from audit import collect


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
    start = datetime.now(timezone.utc)
    started = HERE / f'{label}.started.json'
    out = HERE / f'{label}.stdout.log'
    err = HERE / f'{label}.stderr.log'
    result = HERE / f'{label}.json'
    for path in (started, out, err, result):
        if path.exists():
            raise SystemExit(f'evidence label already exists: {path.name}')
    with started.open('x', encoding='utf-8') as stream:
        json.dump({'label': label, 'command': command, 'started_at': start.isoformat(),
                   'source_fingerprint': before['sourceHash']}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
               PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))))
    clock = time.monotonic()
    with out.open('x') as stdout, err.open('x') as stderr:
        proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=False)
    end = datetime.now(timezone.utc)
    after = collect()
    data = {'label': label, 'command': command, 'cwd': str(ROOT),
            'started_at': start.isoformat(), 'ended_at': end.isoformat(),
            'elapsed_seconds': time.monotonic() - clock, 'exit_code': proc.returncode,
            'source_fingerprint_before': before['sourceHash'],
            'source_fingerprint_after': after['sourceHash'],
            'source_inventory_identical': before['source'] == after['source'],
            'formal_identical': before['formal_files'] == after['formal_files'],
            'protected_identical': before['protected'] == after['protected'],
            'excluded_identical': before['excluded'] == after['excluded'],
            'stdout_sha256': sha(out), 'stderr_sha256': sha(err)}
    with result.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(data, ensure_ascii=False))
    raise SystemExit(proc.returncode)


if __name__ == '__main__':
    main()
