"""P18 acceptance archive audit; no behavior tests or Git writes.

Creates new manifests once. With --verify-existing it only verifies the saved audit.
"""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tomllib

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREVIOUS = OUT.parent / 'p18_exception_evidence'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    result = subprocess.run(
        ['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
        capture_output=True, encoding='utf8',
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'},
    )
    result.check_returncode()
    return result


def paths(*args):
    return git(*args).stdout.splitlines()


def create(name, content):
    with (OUT / name).open('x', encoding='utf8', newline='\n') as stream:
        stream.write(content if isinstance(content, str) else
                     json.dumps(content, ensure_ascii=False, indent=2) + '\n')


b = read(OUT / 'before.json')
docs = read(OUT / 'documentation-files.json')
frozen = read(PREVIOUS / 'frozen-source.json')
source = runpy.run_path(str(PREVIOUS / 'run.py'))['source_hashes']()
assert source == frozen['source'] == b['source']
assert len(frozen['identities']) == 1517
assert len(set(frozen['identities'])) == len(frozen['identities'])
assert all(sha(ROOT / p) == h for group in b['protected'].values() for p, h in group.items())
assert sha(ROOT / 'pyproject.toml') == b['pyprojectHash']
assert tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf8'))['project']['version'] == '0.1.0'
from continuity_engine.testing.persistence import tree_inventory_hash
formal_files = {p.relative_to(ROOT).as_posix(): sha(p)
                for p in (ROOT / '.continuity-data').rglob('*') if p.is_file()}
assert formal_files == b['protected']['formalFiles']
assert tree_inventory_hash(ROOT / '.continuity-data') == b['formalTreeHash']
assert sha(ROOT / '.git/index') == b['indexHash']
assert git('rev-parse', 'HEAD').stdout.strip() == b['head']
assert git('rev-parse', 'origin/main').stdout.strip() == b['localOrigin'] == b['head']
assert git('branch', '--show-current').stdout.strip() == 'main'
assert not paths('diff', '--cached', '--name-only')
assert all(sha(ROOT / p) == h for p, h in b['excluded'].items())

if sys.argv[1:] == ['--verify-existing']:
    audit = read(OUT / 'final.audit.json')
    assert all(sha(ROOT / p) == h for p, h in audit['pendingHashes'].items())
    actual = set(paths('diff', '--name-only') + paths('ls-files', '--others', '--exclude-standard'))
    assert actual == set(audit['pending']) | set(b['excluded'])
    assert audit['source'] == source
    assert all(sha(Path(row['original'])) == sha(ROOT / row['copy']) == row['sha256']
               for row in read(OUT / 'independent-archive.json')['files'])
    print(json.dumps({'verified': True, 'pending': len(audit['pending']),
                      'excluded': len(b['excluded']), 'tracked': len(paths('diff', '--name-only')),
                      'untracked': len(paths('ls-files', '--others', '--exclude-standard')),
                      'staged': [], 'sourceHash': b['sourceHash'], 'gitWrites': False}))
    raise SystemExit(0)
assert not sys.argv[1:]
assert not (OUT / 'final.audit.json').exists()

changed = {p for p, h in b['existingPending'].items() if sha(ROOT / p) != h}
assert changed == set(docs)
assert all(sha(ROOT / p) == h for p, h in b['existingPending'].items() if p not in docs)
separator = ('以下保留发生时的状态及结论；其中 IMPLEMENTED_NOT_ACCEPTED、EVIDENCE_CONFLICT=PRESENT、'
             'D-073 未创建等均为历史，不代表本次现行状态。\r\n\r\n').encode('utf8')
for rel in docs:
    body = (ROOT / rel).read_bytes()
    current, historical = body.split(separator, 1)
    assert b'P18_ACCEPTED_D073_20260919' in current
    assert 'P00—P18 = ACCEPTED'.encode() in current
    assert 'P19—P23 = NOT_STARTED'.encode() in current
    assert b'EVIDENCE_CONFLICT = NONE' in current and b'UNKNOWN' in current
    if rel.endswith('04_决策记录.md'):
        historical = historical.split('\r\n\r\n## D-073：'.encode('utf8'), 1)[0]
    assert hashlib.sha256(historical).hexdigest() == b['documentsBefore'][rel]
decisions = (ROOT / 'docs/project_memory/04_决策记录.md').read_text(encoding='utf8')
assert len(re.findall(r'^## D-073：', decisions, re.M)) == 1
assert not re.search(r'^#{1,5} D-074', decisions, re.M)
matrix = read(OUT / 'accepted-matrix.json')
assert set(matrix) == {f'P18-{i:02}' for i in range(1, 13)}
old_matrix = read(PREVIOUS / 'matrix-test-map.json')
assert all(v['status'] == 'ACCEPTED' and v['decision'] == 'D-073' and
           v['testIdentities'] == old_matrix[k]['testIdentities'] for k, v in matrix.items())
review_runs = {}
for label, count in [('original-six-01', 6), ('p18-01', 157), ('prior-35-01', 35), ('exception-edges-01', 4)]:
    result = read(OUT / 'independent' / (label + '.result.json'))
    before = read(OUT / 'independent' / (label + '.before.json'))
    after = read(OUT / 'independent' / (label + '.after.json'))
    assert before == after and all(before[p] == h for p, h in source.items())
    assert result['exitCode'] == 0 and not result['changed']
    stderr = (OUT / 'independent' / (label + '.stderr.log')).read_text(encoding='utf8')
    match = re.search(r'Ran (\d+) tests? in ([\d.]+)s', stderr)
    assert int(match[1]) == count and re.search(r'\nOK\s*$', stderr)
    review_runs[label] = {'run': count, 'passed': count, 'skip': 0, 'fail': 0, 'error': 0,
                          'unittestSeconds': float(match[2]), 'runnerSeconds': result['elapsedSeconds'],
                          'exitCode': 0, 'executedBy': 'independent reviewer; cited this archive turn'}
identity = read(OUT / 'independent/identity-check.json')
assert identity['allIdentityChecksPass'] and identity['sourceHash'] == b['sourceHash']
supplier_runs = {}
for label in read(PREVIOUS / 'selected-runs.json')['runs']:
    result = read(PREVIOUS / (label + '.json'))
    assert result['sourceBefore'] == source == result['sourceAfter'] and result['exitCode'] == 0
    supplier_runs[label] = {key: result[key] for key in ('run', 'passed', 'seconds', 'exitCode', 'status', 'skips')}
full = read(PREVIOUS / 'full-final-01.json')
assert set(full['testIdentities']) == set(frozen['identities'])
assert full['run'] == 1517 and full['passed'] == 1516 and len(full['skips']) == 1
assert full['skips'] == read(PREVIOUS / 'final.audit-resume-20260919.json')['results']['full-final-01']['skips']
archive = read(OUT / 'independent-archive.json')
assert len(archive['files']) == 26
assert all(sha(Path(row['original'])) == sha(ROOT / row['copy']) == row['sha256'] for row in archive['files'])

manifest_names = ['document-changes.json', 'final.pending-files.md', 'final.audit.json']
pending = sorted(set(paths('diff', '--name-only') + paths('ls-files', '--others', '--exclude-standard') +
                     [(OUT / n).relative_to(ROOT).as_posix() for n in manifest_names]) - set(b['excluded']))
new = sorted(set(pending) - set(b['existingPending']))
assert all(p.startswith(OUT.relative_to(ROOT).as_posix() + '/') for p in new)
for rel in pending:
    assert not set(Path(rel).parts) & {'__pycache__', '.continuity-data', '.assistant-data', 'dist', 'build', 'node_modules'}
    assert Path(rel).suffix.lower() not in {'.pyc', '.pyo', '.whl', '.zip', '.tmp', '.swp'}
create('document-changes.json', {
    'modifiedDocuments': {p: {'before': b['documentsBefore'][p], 'after': sha(ROOT / p)} for p in docs},
    'newArchiveFiles': new, 'existingP18Files': len(b['existingPending']),
    'previousEvidenceAndSourceUnchanged': True, 'historicalDocumentBodiesPreserved': True,
    'runtimeAndFormalTestChangesThisTurn': [],
})
text = '# P18 验收归档后精确待提交与排除清单\n\n'
text += f'P18 全部待提交成果 {len(pending)} 项；包含本轮前已有 716 项及本轮新增 {len(new)} 项。'
text += '本轮仅追加验收档案和独立证据，修改既有文档 21 份；源码/正式测试不变。此清单不构成 Git 操作授权。\n\n'
text += '## 本轮修改的既有文档（21）\n\n' + '\n'.join('- ' + p for p in docs) + '\n\n'
text += '## 本轮新增验收文件\n\n' + '\n'.join('- ' + p for p in new) + '\n\n'
text += '## 全部 P18 待提交文件\n\n' + '\n'.join('- ' + p for p in pending) + '\n\n'
text += '## 原样排除的 32 项（含 SHA-256）\n\n'
text += '\n'.join('- ' + p + ' — ' + h for p, h in b['excluded'].items()) + '\n\n'
text += '无其他无法归属的待提交项。缓存、正式数据及被忽略运行材料未加入本清单，未清理或暂存。\n'
create('final.pending-files.md', text)

links, broken = [], []
for path in [ROOT / p for p in docs] + list(OUT.rglob('*.md')):
    for dest in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf8')):
        if dest.startswith(('https:', 'http:', '#', 'app:')):
            continue
        target = dest.split('#')[0].strip('<>')
        if not target:
            continue
        links.append({'file': path.relative_to(ROOT).as_posix(), 'target': target})
        resolved = (path.parent / target).resolve()
        if not resolved.exists() and resolved != OUT / 'final.audit.json':
            broken.append(links[-1])
assert not broken, broken
parsed = []
for rel in source:
    if rel.endswith('.py'):
        ast.parse((ROOT / rel).read_text(encoding='utf-8-sig'))
        parsed.append(rel)
ast.parse(Path(__file__).read_text(encoding='utf8'))
signatures, whitespace = [], []
for rel in pending:
    path = ROOT / rel
    if not path.exists() or path.suffix not in {'.md', '.json', '.log', '.py'}:
        continue
    body = path.read_text(encoding='utf-8-sig')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}', body):
        signatures.append(rel)
    lines = [n for n, line in enumerate(body.splitlines(), 1) if line.endswith((' ', '\t'))]
    if lines:
        whitespace.append({'file': rel, 'lines': lines, 'newThisTurn': rel in new})
assert not signatures, signatures
assert not [x for x in whitespace if x['newThisTurn']], whitespace
diff = git('diff', '--check')
assert sha(ROOT / '.git/index') == b['indexHash']
status = {'branch': 'main', 'head': b['head'], 'localOrigin': b['localOrigin'],
          'aheadBehind': git('rev-list', '--left-right', '--count', 'HEAD...origin/main').stdout.strip(),
          'staged': [], 'tracked': paths('diff', '--name-only'),
          'untracked': sorted(set(paths('ls-files', '--others', '--exclude-standard')) |
                              {(OUT / 'final.audit.json').relative_to(ROOT).as_posix()}),
          'remoteQueried': False, 'indexHash': b['indexHash']}
create('final.audit.json', {
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'stage': 'P18', 'status': 'ACCEPTED', 'engineSide': 'ACCEPTED', 'decision': 'D-073',
    'P00-P18': 'ACCEPTED', 'P19-P23': 'NOT_STARTED', 'VioDependency': 'NONE',
    'planningConflict': 'NONE', 'evidenceConflict': 'NONE',
    'conflictMeaning': 'Present acceptance blockers closed; historical F1/H1/F2 UNKNOWN explicitly accepted by user, not solved.',
    'historicalCauses': {'F1': 'UNKNOWN', 'H1': 'UNKNOWN', 'F2': 'UNKNOWN'},
    'source': source, 'sourceHash': b['sourceHash'], 'formalTests': len(frozen['identities']),
    'behaviorTestsRunThisTurn': 0, 'independentRunsCited': review_runs, 'supplierRunsCited': supplier_runs,
    'independentIdentityChecksCited': len(identity['checks']),
    'archiveCount': 26, 'archiveHashesVerified': True, 'historicalEvidenceUnchanged': True,
    'historicalDocumentBodiesPreserved': True, 'protectedUnchanged': True,
    'protectedCounts': {k: len(v) for k, v in b['protected'].items()},
    'formalFiles': formal_files, 'formalTreeHash': b['formalTreeHash'],
    'pyprojectHash': b['pyprojectHash'], 'version': '0.1.0', 'excluded': b['excluded'],
    'modifiedDocuments': docs, 'newArchiveFiles': new, 'pending': pending, 'pendingCount': len(pending),
    'pendingHashes': {p: sha(ROOT / p) for p in pending if p != (OUT / 'final.audit.json').relative_to(ROOT).as_posix()},
    'selfHashPolicy': 'Audit path included, own hash excluded; verify-existing checks remaining paths and exact Git path set.',
    'sourcePythonAST': len(parsed), 'linkCount': len(links), 'brokenLinks': broken,
    'secretSignatureFindings': signatures, 'secretScanLimit': 'Specific key signatures only; not exhaustive.',
    'historicalWhitespace': whitespace, 'diffCheck': {'exitCode': diff.returncode, 'stdout': diff.stdout, 'stderr': diff.stderr},
    'git': status, 'gitWrites': False, 'CI': 'NOT_QUERIED_NO_PASS_CLAIM',
    'processesStartedThisTurn': 0, 'processesTerminatedThisTurn': 0,
    'auxiliaryReadWarning': 'Initial PowerShell rg literal wildcard paths returned OS error 123; corrected with rg -g. No Engine test failure or file change.',
})
print(json.dumps({'pending': len(pending), 'new': len(new), 'modifiedDocuments': len(docs),
                  'excluded': len(b['excluded']), 'sourcePythonAST': len(parsed), 'links': len(links),
                  'brokenLinks': broken, 'secretSignatures': signatures, 'historicalFormatFiles': len(whitespace),
                  'diffCheck': diff.returncode, 'tracked': len(status['tracked']),
                  'untracked': len(status['untracked']), 'stage': 'ACCEPTED'}, ensure_ascii=False))
