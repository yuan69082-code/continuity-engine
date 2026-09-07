"""Independent read-only check of the final second-repair evidence and scope."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(r'C:\Users\Administrator\Documents\continuity-engine')
E = ROOT / 'docs/project_memory/p12_second_repair_evidence'
INITIAL = ROOT / 'docs/project_memory/p12_evidence'
FIRST = ROOT / 'docs/project_memory/p12_repair_evidence'
GIT = Path(r'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
sys.dont_write_bytecode = True

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def drift(mapping):
    return [p for p, h in mapping.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]

def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id().removeprefix('tests.')

def git(*args):
    result = subprocess.run([str(GIT), '-c', f'safe.directory={ROOT}', '-c', 'core.quotepath=false',
                             '-C', str(ROOT), *args], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    return result.stdout

full = read(E / 'full-final.tests.json')
outer = read(E / 'full-final.json')
before = read(E / 'before.json')
initial = read(INITIAL / 'before.json')
first_full = read(FIRST / 'full-stable-02.tests.json')
audit = read(E / 'final-audit.json')
manifest = read(E / 'pending-files.json')
loader = unittest.TestLoader()
current_ids = list(ids(loader.discover(str(ROOT / 'tests'))))
assert not loader.errors, loader.errors
logged = {}
for line in (E / 'full-final.stderr.log').read_text(encoding='utf-8').splitlines():
    match = re.fullmatch(r'(\w+) \(([\w.]+)\) \.\.\. (ok|skipped .+)', line)
    if match:
        name = match[2] if match[2].endswith('.' + match[1]) else match[2] + '.' + match[1]
        name = name.removeprefix('tests.')
        assert name not in logged, name
        logged[name] = match[3]
assert len(current_ids) == len(set(current_ids)) == full['run'] == 1011
assert set(current_ids) == set(full['testIdentities']) == set(logged)
assert set(first_full['testIdentities']).issubset(current_ids)
assert set(initial['testIdentities']).issubset(current_ids)
assert full['passed'] == sum(value == 'ok' for value in logged.values()) == 1010
assert not full['failures'] and not full['errors'] and len(full['skips']) == 1
assert '1314' in str(full['skips'])
assert outer['exitCode'] == 0 and outer['interrupted'] is False
assert outer['sourceTest'] == full['sourceTest']

checks = {'finalSourceTest': full['sourceTest'], 'protected': initial['protected'],
          'p10Helpers': initial['p10Untracked'], 'reviewOriginals': before['reviewSources'],
          'preRepairTests': {p: h for p, h in before['sourceTest'].items() if p.startswith('tests/')}}
drifts = {name: drift(mapping) for name, mapping in checks.items()}
assert not any(drifts.values()), drifts
changed_source = sorted(drift(before['sourceTest']))
assert changed_source == ['src/continuity_engine/services/memory_service.py',
                          'src/continuity_engine/storage/json_memory_repository.py'], changed_source
new_source = sorted(set(full['sourceTest']) - set(before['sourceTest']))
assert new_source == ['tests/test_p12_memory_second_review.py'], new_source
python_paths = [p for p in full['sourceTest'] if Path(p).suffix == '.py']
for p in python_paths:
    ast.parse((ROOT / p).read_text(encoding='utf-8-sig'), filename=p)

stable_runs = {}
for label in ('p12-final', 'compatibility-final', 'neighbors-final', 'original-final'):
    run = read(E / (label + '.json'))
    assert run['exitCode'] == 0 and run['sourceTest'] == full['sourceTest'], label
    stable_runs[label] = run['exitCode']
assert not any(audit.get(key) for key in ('protectedDrift', 'formalDrift', 'reviewSourceDrift',
    'identityErrors', 'planDrift', 'unexpectedExistingDrift', 'newScopeErrors', 'astErrors',
    'brokenLinks', 'sensitiveMatches', 'newCacheFiles', 'stateErrors'))
assert audit['allStableSourceMatches'] and audit['allExpectedRunsCompleted']
assert not drift(audit['formalFiles'])
assert not drift(audit['ownedContentHashes'])
plans = read(INITIAL / 'planning-source.json')
assert all(sha(Path(plan['source'])) == plan['sha256'] for plan in plans.values())

status = git('status', '--porcelain=v1', '--untracked-files=all').splitlines()
paths = {line[3:].replace('\\', '/') for line in status}
staged = [line for line in status if line[0] not in (' ', '?')]
assert not staged, staged
assert paths - set(initial['p10Untracked']) == set(manifest['allP12Paths'])
assert not manifest['otherUnattributedFiles']
git('diff', '--check')
assert git('branch', '--show-current').strip() == 'main'
assert git('rev-parse', 'HEAD').strip() == before['head'] == '1b8020fbe687dafaaf83a629dbeee65d69a71d67'
assert git('rev-list', '--left-right', '--count', 'HEAD...origin/main').split() == ['0', '0']
category_counts = {name: len(values) for name, values in manifest['categories'].items()}
print(json.dumps({'independentEvidenceVerification': 'PASS', 'fullSuiteRerunThisReview': False,
    'currentTestCount': len(current_ids), 'prior992TestsPreserved': len(first_full['testIdentities']),
    'original894TestsPreserved': len(initial['testIdentities']),
    'sourceTestFilesVerified': len(full['sourceTest']), 'pythonFilesParsed': len(python_paths),
    'changedRuntimeFiles': changed_source,
    'newSourceTestFiles': new_source, 'hashCheckCounts': {name: len(mapping) for name, mapping in checks.items()},
    'drift': drifts, 'finalRunSourceMatches': stable_runs,
    'suppliedFullRun': {key: full[key] for key in ('run', 'passed', 'skips', 'seconds')},
    'suppliedFullLogSHA256': sha(E / 'full-final.stderr.log'),
    'formalDataFiles': len(audit['formalFiles']), 'formalTreeHash': audit['formalTreeHash'],
    'planningSourceFilesVerified': len(plans), 'auditedContentFilesUnchanged': len(audit['ownedContentHashes']),
    'worktree': {'trackedChanges': sum(not s.startswith('??') for s in status),
                 'untracked': sum(s.startswith('??') for s in status), 'staged': len(staged),
                 'p12Paths': len(manifest['allP12Paths']), 'categories': category_counts},
    'actualRemoteCheckedThisReview': False,
    'decision': 'F1/F2 review clear; conditional Git closeout may be dispatched, no formal acceptance'},
    ensure_ascii=False, indent=2))
