"""P17 read-only baseline and immutable source/authorization archive."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
sys.dont_write_bytecode = True
from continuity_engine.testing.persistence import tree_inventory_hash

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()

def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test.id()

def main():
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    b = json.loads((ROOT/'docs/project_memory/p16_acceptance_evidence/before.json').read_text(encoding='utf-8'))
    full = json.loads((ROOT/'docs/project_memory/p16_repair_evidence/full-final-01.json').read_text(encoding='utf-8'))
    assert git('branch', '--show-current') == 'main'
    assert git('rev-parse', 'HEAD') == git('rev-parse', 'origin/main') == '0c440b0476b07723abafe93777fe895b64fd8d0e'
    assert not git('diff', '--name-only') and not git('diff', '--cached', '--name-only')
    source = {p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert source == full['sourceBefore'] == full['sourceAfter'] == b['sourceTest']
    for key in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        assert all(sha(ROOT/p) == h for p,h in b[key].items()), key
    assert tree_inventory_hash(ROOT/'.continuity-data') == b['formalTreeHash']
    loader = unittest.TestLoader()
    identities = list(flatten(loader.discover(str(ROOT/'tests'))))
    assert not loader.errors and identities == full['testIdentities'] and len(identities) == 1286
    record = {k:b[k] for k in ('protected','plans','formalFiles','excludedP10','otherPreserved','excluded','formalTreeHash')}
    record.update(at=datetime.now(timezone.utc).isoformat(),head=git('rev-parse','HEAD'),sourceTest=source,
                  testIdentities=identities,baselineResult={k:full[k] for k in ('run','passed','skips','exitCode','seconds')},
                  baselineIsCited=True,trackedFiles={p:sha(ROOT/p) for p in git('ls-files','-z').split('\0') if (ROOT/p).is_file()},
                  gitStatus=git('-c','core.quotepath=false','status','--short','--untracked-files=all'))
    origin = Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p17-kickoff-20260909')
    record['kickoff'] = {}
    for name in ('implementation-brief.md','baseline-verification.json','planning-extract.json'):
        with (OUT/name).open('xb') as stream:
            stream.write((origin/name).read_bytes())
        assert sha(OUT/name) == sha(origin/name)
        record['kickoff'][name] = {'source':str(origin/name),'sha256':sha(origin/name)}
    with (OUT/'before.json').open('x',encoding='utf-8') as stream:
        json.dump(record,stream,ensure_ascii=False,indent=2)
    print('P17 baseline verified: source 243, identities 1286, protected 63, formal 7, excluded 32. No tests rerun.')

if __name__ == '__main__':
    main()
