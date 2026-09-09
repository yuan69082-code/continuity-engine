"""Verify P17 acceptance scope without running tests or mutating Git."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import re
import runpy
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
config = runpy.run_path(str(Path(__file__).with_name('archive.py')))
ROOT, OUT, DOC, REPAIR, REVIEW = (config[k] for k in ('ROOT', 'OUT', 'DOC', 'REPAIR', 'REVIEW'))
read, sha, git, source = (config[k] for k in ('read', 'sha', 'git', 'source'))
links = runpy.run_path(str(DOC / 'p14_evidence/audit.py'))['links']
tree_inventory_hash = config['tree_inventory_hash']


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'final'
    assert re.fullmatch(r'[a-z0-9-]+', label)
    target = OUT / (label + '.audit.json')
    listing = OUT / (label + '.pending-files.md')
    assert not target.exists() and not listing.exists(), 'never overwrite an audit'
    before = read(OUT / 'before.json'); repair = read(REPAIR / 'final.audit.json')
    current = source(); errors = []; checks = {}
    checks['source253Exact'] = current == before['sourceTest'] == repair['sourceTest']
    s = config['status']()
    checks['gitBaseline'] = (s['branch'] == 'main' and s['head'] == s['originMain'] == config['BASE']
                             and s['remote'] == config['REMOTE'] and s['aheadBehind'] == '0\t0' and not s['staged'])
    checks['exclusionsStillUntracked'] = set(before['excluded']) <= set(s['untracked'])
    protection = {}
    for key in ('protected', 'plans', 'formalFiles', 'excludedP10', 'otherPreserved'):
        changed = [p for p, h in before[key].items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
        protection[key] = dict(count=len(before[key]), changed=changed)
        checks[key] = not changed
    formal_hash = tree_inventory_hash(ROOT / '.continuity-data')
    checks['formalTree'] = formal_hash == before['formalTreeHash']
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    checks['versionPyproject'] = version == '0.1.0' and sha(ROOT / 'pyproject.toml') == before['pyproject']
    allowed_docs = {p.relative_to(ROOT).as_posix() for p in config['CURRENT_DOCS']}
    old_hashes = before['pendingHashes']
    prior_changed = [p for p, h in old_hashes.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    checks['existingChangesOnlyCurrentDocs'] = set(prior_changed) <= allowed_docs
    snap = read(OUT / 'independent/repair-p17-01.after.json')
    history_drift = [p for p, h in snap.items() if p not in allowed_docs and (not (ROOT / p).is_file() or sha(ROOT / p) != h)]
    checks['allOtherReviewedHistoryUnchanged'] = not history_drift
    copies = read(OUT / 'archive-map.json')
    copy_checks = {n: sha(Path(v['source'])) == sha(ROOT / v['destination']) == v['sha256'] for n, v in copies.items()}
    checks['independentCopiesExact'] = all(copy_checks.values())
    independent_identity = read(OUT / 'independent/repair-identity-check.json')
    checks['independent24ChecksPass'] = len(independent_identity['checks']) == 24 and all(independent_identity['checks'].values())
    cited_runs = {}
    for label_run in ('formal-after-02', 'independent-after-01', 'p17-final-01', 'compatibility-final-01', 'full-final-01'):
        r = read(REPAIR / (label_run + '.json'))
        checks[label_run] = r['sourceBefore'] == r['sourceAfter'] == current and r['exitCode'] == 0 and r['status'] == 'FINISHED'
        cited_runs[label_run] = {k: r[k] for k in ('run', 'passed', 'skips', 'failures', 'errors', 'seconds', 'exitCode', 'command')}
    full = read(REPAIR / 'full-final-01.json'); repair_before = read(REPAIR / 'before.json')
    old_ids = set(repair_before['testIdentities']); final_ids = set(full['testIdentities'])
    checks['original1348IdentitiesAndAssertions'] = (old_ids <= final_ids and len(old_ids) == 1348
        and all(current[p] == h for p, h in repair_before['sourceTest'].items() if p.startswith('tests/')))
    checks['exact12NewIdentities'] = len(final_ids - old_ids) == 12
    checks['fullCounts'] = len(final_ids) == full['run'] == 1360 and full['passed'] == 1359 and len(full['skips']) == 1 and not full['errors'] and not full['failures']
    checks['onlyExistingSkip'] = full['skips'] == repair['tests']['full-final-01']['skips']
    decisions = (DOC / '04_决策记录.md').read_text(encoding='utf-8')
    checks['D071Unique'] = len(re.findall(r'^## D-071[：:]', decisions, re.M)) == 1
    matrix = next(DOC.glob('80_P17_*.md')).read_text(encoding='utf-8')
    matrix_items = re.findall(r'^\| P17-(\d{2}) \|[^\n]*\| ACCEPTED \|', matrix, re.M)
    checks['matrixTwelveAccepted'] = matrix_items == [f'{i:02}' for i in range(1, 13)]
    state_errors = []
    for p in config['CURRENT_DOCS']:
        content = p.read_text(encoding='utf-8')
        block = content.split('<!-- P17_ACCEPTED_START -->', 1)[1].split('<!-- P17_ACCEPTED_END -->', 1)[0]
        if not all(x in block for x in ('D-071', 'P00—P17 ACCEPTED', 'P17-01—P17-12 ACCEPTED',
                'P18—P23 NOT_STARTED', 'PLANNING_CONFLICT=NONE', 'EVIDENCE_CONFLICT=NONE', 'NOT_READY')):
            state_errors.append(str(p))
    checks['currentStatesConsistent'] = not state_errors
    pending = sorted((set(s['tracked'] + s['untracked']) - set(before['excluded'])) |
                     {target.relative_to(ROOT).as_posix(), listing.relative_to(ROOT).as_posix()})
    additions = sorted(set(pending) - set(before['reviewedPending']))
    checks['all196ReviewedFilesIncluded'] = set(before['reviewedPending']) <= set(pending)
    checks['newFilesOnlyAcceptance'] = all(p.startswith('docs/project_memory/p17_acceptance_evidence/') or p == config['ENTRY'].relative_to(ROOT).as_posix() for p in additions)
    forbidden = [p for p in pending if any(x in Path(p).parts for x in
                  ('.git', '.continuity-data', '.assistant-data', '__pycache__', 'build', 'dist', 'node_modules'))
                 or p.endswith(('.pyc', '.whl', '.zip', '.tmp'))]
    checks['noForbiddenArtifacts'] = not forbidden
    sections = [('# P17 正式验收完整提交清单', []),
                ('应提交：' + str(len(pending)) + ' 项（普通提交前精确路径）', pending),
                ('本次归档修改的原 P17 档案：' + str(len(prior_changed)) + ' 项', prior_changed),
                ('本次必要验收新增：' + str(len(additions)) + ' 项', additions),
                ('排除并原样保留：32 项（31 个 P10 脚本、1 份旧 P14 报告）', before['excluded'])]
    lines = []
    for title, paths in sections:
        lines += [title if title.startswith('# ') else '## ' + title, '', *('- `' + p + '`' for p in paths), '']
    lines += ['其他无关待提交文件：无。原始失败日志、明确标注的合成秘密反例和必要审计材料属于 P17 证据；不清理历史。', '',
              '本清单不是已完成提交的声明；最终 SHA、父提交及实际远端结果在提交后报告。', '']
    listing.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    sensitive = []; broken = []; link_count = 0; syntax = []; python_source = 0
    whitespace = []; synthetic = []
    secret = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    marker_source = (ROOT / 'src/continuity_engine/testing/p16_provider_fixture.py').read_text(encoding='utf-8')
    marker_match = re.search(r'SECRET_MARKER\s*=\s*[\'\"]([^\'\"]+)', marker_source)
    for name in current:
        if name.endswith('.py'):
            try:
                ast.parse((ROOT / name).read_text(encoding='utf-8-sig'), filename=name); python_source += 1
            except SyntaxError as exc:
                syntax.append(dict(path=name, line=exc.lineno))
    for name in pending:
        p = ROOT / name
        if not p.is_file() or p.suffix not in ('.py', '.md', '.json', '.log', '.txt'):
            continue
        content = p.read_text(encoding='utf-8-sig')
        if secret.search(content):
            sensitive.append(name)
        if marker_match and marker_match.group(1) in content:
            synthetic.append(name)
        if p.suffix == '.md':
            expected = {target.resolve(), listing.resolve(), (OUT / 'final.audit.json').resolve(), (OUT / 'final.pending-files.md').resolve()}
            count, bad = links(p, content, expected)
            link_count += count; broken += [(name, v) for v in bad]
        if p.suffix == '.py' and name not in current:
            try:
                ast.parse(content, filename=name)
            except SyntaxError as exc:
                syntax.append(dict(path=name, line=exc.lineno))
        if name in s['untracked']:
            whitespace += [dict(path=name, line=i, kind='trailing whitespace') for i, line in enumerate(content.splitlines(), 1) if line.endswith((' ', '\t'))]
            if content.endswith('\n\n') and content.strip():
                whitespace.append(dict(path=name, line=len(content.splitlines()), kind='new blank line at EOF'))
    old_format = read(DOC / 'p17_evidence/final.audit.json')
    known_warnings = old_format['newRawEvidenceWhitespace']
    unexpected_whitespace = [v for v in whitespace if v not in known_warnings]
    checks['pythonSyntax'] = not syntax
    checks['localLinks'] = not broken
    checks['sensitivePatternScan'] = not sensitive
    checks['newFormattingClean'] = not unexpected_whitespace
    d = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, encoding='utf-8')
    checks['trackedDiffCheck'] = d.returncode == 0
    errors += [name for name, ok in checks.items() if not ok]
    report = dict(at=datetime.now(timezone.utc).isoformat(), stage='P17', status='ACCEPTED', decision='D-071',
        planningConflict='NONE', evidenceConflict='NONE', conflictMeaning='known independently reviewed blockers closed; not proof of absence of every defect',
        testsExecutedThisCloseout=False, gitWritesByThisScript=False, checks=checks, errors=errors,
        sourceTest=current, sourceCount=len(current), sourceInventoryHash=repair['sourceInventoryHash'],
        parsedPythonFiles=python_source, protection=protection, formalTreeHash=formal_hash, version=version,
        independentCopyChecks=copy_checks, independentIdentityChecks=independent_identity['checks'],
        independentRuns={label_run: read(OUT / ('independent/' + label_run + '.result.json')) for label_run in ('repair-p17-01', 'repair-independent-01')},
        citedConstructionRunsNotNewExecutions=cited_runs, originalIdentityCount=len(old_ids), newIdentities=sorted(final_ids - old_ids),
        currentStateErrors=state_errors, matrixItems=matrix_items, reviewed196=before['reviewedPending'],
        acceptanceModifiedExisting=prior_changed, acceptanceAdded=additions, historicalDrift=history_drift,
        pending=pending, pendingFileCount=len(pending), excluded=before['excluded'], unrelatedPending=[],
        forbiddenArtifacts=forbidden, syntaxErrors=syntax, linkCount=link_count, brokenLinks=broken,
        sensitiveMatches=sensitive, syntheticTestMarkerLocations=synthetic,
        syntheticMarkerScope='explicit TEST counterexamples only; never credentials or permission to leak at runtime',
        preservedPriorEightWarnings=old_format['historicalEightWarnings'], preservedP17RawWarnings=known_warnings,
        allPendingUntrackedWhitespace=whitespace, unexpectedWhitespace=unexpected_whitespace,
        diffCheck=dict(exitCode=d.returncode, stdout=d.stdout, stderr=d.stderr),
        git=s, ci=dict(trackedWorkflows=git('ls-files', '.github/workflows').splitlines(),
                       remoteRunConfirmed=False, passClaimed=False),
        pendingHashes={p: sha(ROOT / p) for p in pending if p != target.relative_to(ROOT).as_posix()})
    report['git']['statusBeforeAuditFile'] = git('status', '--short', '--untracked-files=all')
    config['save'](target, report)
    print(json.dumps({k: report[k] for k in ('errors', 'pendingFileCount', 'sourceCount', 'parsedPythonFiles', 'linkCount', 'brokenLinks', 'sensitiveMatches', 'unexpectedWhitespace')}, ensure_ascii=False))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
