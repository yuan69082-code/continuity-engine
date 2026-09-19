"""Independent read-only evidence checks; writes only a planning-side result."""
import ast
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior_verifier', OUT.parent / 'p18-storage-final-review-20260914/verify_evidence.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
ENGINE = prior.ENGINE
EV = ENGINE / 'docs/project_memory/p18_exception_evidence'
read, sha, drift, git = prior.read, prior.sha, prior.drift, prior.git
AUDIT_NAME = 'final.audit-resume-20260919.json'
SELECTED = {'independent-final-01': 6, 'formal-after-01': 10, 'storage-compatibility-final-01': 41,
            'p18-final-01': 157, 'compatibility-final-01': 605, 'full-final-01': 1517}


def main():
    before, audit, frozen, selected = [read(EV / name) for name in
        ('before.json', AUDIT_NAME, 'frozen-source.json', 'selected-runs.json')]
    changes = read(EV / 'turn-changes-resume-20260919.json')
    resume = read(EV / 'resume-verification-20260919.json')
    source = prior.source_inventory()
    old_snapshot = read(OUT.parent / 'p18-storage-final-review-20260914/p18-original-01.before.json')
    prior_source = {p: h for p, h in old_snapshot.items() if p.startswith(('src/', 'tests/'))}
    full = read(EV / 'full-final-01.json')
    old_ids, full_ids = set(before['testIdentities']), set(full['testIdentities'])
    old_tests = {p: h for p, h in before['sourceTest'].items() if p.startswith('tests/')}
    changed_runtime = {p for p, h in before['sourceTest'].items() if p.startswith('src/') and source.get(p) != h}
    new_path = 'tests/test_p18_storage_exceptions.py'
    syntax_errors, static_ids = [], set()
    for path in source:
        if not path.endswith('.py'):
            continue
        try:
            module = ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
        except (SyntaxError, UnicodeError) as error:
            syntax_errors.append({'path': path, 'error': str(error)})
            continue
        if path == new_path:
            for cls in module.body:
                if isinstance(cls, ast.ClassDef):
                    for method in cls.body:
                        if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                            static_ids.add(f'{Path(path).stem}.{cls.name}.{method.name}')
    runs = {}
    for label, expected in SELECTED.items():
        row = read(EV / (label + '.json'))
        stderr = (EV / (label + '.stderr.log')).read_text(encoding='utf-8')
        summary = {k: row[k] for k in ('run', 'passed', 'seconds', 'exitCode', 'status', 'skips')}
        summary.update(failures=len(row['failures']), errors=len(row['errors']))
        checks = {
            'sourceMatches': row['sourceBefore'] == row['sourceAfter'] == source,
            'finishedCleanly': row['status'] == 'FINISHED' and row['exitCode'] == 0 and not any(row[k] for k in ('loaderErrors', 'failures', 'errors')),
            'countMatches': row['run'] == expected == len(row['testIdentities']) == len(set(row['testIdentities'])) == row['passed'] + len(row['skips']),
            'auditMatches': summary == audit['results'][label],
            'rawLogsPresent': (EV / (label + '.stdout.log')).is_file() and f'Ran {expected} tests' in stderr and bool(re.search(r'^OK(?: \(skipped=\d+\))?\s*$', stderr, re.M)),
            'resumeRawHashesMatch': all(sha(EV / (label + suffix)) == value for suffix, value in resume['results'][label]['rawEvidenceHashes'].items()),
        }
        runs[label] = dict(checks=checks, **summary)
    protected = before['protected']
    exclusions = {**protected['excludedP10'], **protected['otherPreserved']}
    protection_drift = {name: drift(items) for name, items in protected.items()}
    sections = prior.markdown_sections(EV / 'final.pending-files-resume-20260919.md')
    accepted = set(sections['完整P18成果'])
    tracked = prior.git_paths('diff', '--name-only')
    untracked = prior.git_paths('ls-files', '--others', '--exclude-standard')
    pending = tracked | untracked
    audit_self = (EV / AUDIT_NAME).relative_to(ENGINE).as_posix()
    archive_drift = []
    for original, row in before['archives'].items():
        if sha(ENGINE / row['copy']) != row['sha256']:
            archive_drift.append(row['copy'])
        if original not in prior.ALLOWED_RUNTIME and sha(ENGINE / original) != row['sha256']:
            archive_drift.append(original)
    changed_existing = {p for p, h in before['existingPending'].items() if sha(ENGINE / p) != h}
    index_path = Path(git('rev-parse', '--path-format=absolute', '--git-path', 'index').strip())
    index_hash = sha(index_path)
    head, origin = git('rev-parse', 'HEAD').strip(), git('rev-parse', 'origin/main').strip()
    checks = {
        'source270MatchesFreezeAuditAndFull': len(source) == 270 and source == frozen['source'] == audit['source'] == full['sourceAfter'],
        'sourceHashesMatch': prior.source_hash(source) == frozen['sourceHash'] == audit['sourceHash'] == resume['sourceHash'] and prior.source_hash(before['sourceTest']) == before['sourceHash'],
        'preimageMatchesPriorIndependentSnapshot': before['sourceTest'] == prior_source and all(sha(EV / 'source-before' / Path(p).name) == before['sourceTest'][p] for p in prior.ALLOWED_RUNTIME),
        'exactTwoRuntimeFilesAndOneNewTestFile': changed_runtime == prior.ALLOWED_RUNTIME == set(frozen['changedRuntimeFiles']) and set(source) - set(before['sourceTest']) == {new_path} and not (set(before['sourceTest']) - set(source)),
        'allOriginalTestFilesUnchanged': not drift(old_tests),
        'original1507PlusTenIdentitiesRetained': len(old_ids) == 1507 and old_ids <= full_ids and len(full_ids) == 1517 and full_ids - old_ids == static_ids == set(frozen['addedIdentities']) and len(static_ids) == 10,
        'sixSelectedRunsCleanMatchingAndComplete': set(selected['runs']) == set(SELECTED) == set(audit['results']) and all(all(row['checks'].values()) for row in runs.values()),
        'onlyExisting1314Skip': full['passed'] == 1516 and full['skips'] == [['test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes', 'OS does not grant symlink creation: 1314']],
        'protected63Plans3Formal7Exclusions32Unchanged': {k: len(v) for k, v in protected.items()} == {'protected': 63, 'plans': 3, 'formalFiles': 7, 'excludedP10': 31, 'otherPreserved': 1} and not any(protection_drift.values()),
        'formalTreeAndVersionUnchanged': prior.tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'] == audit['formalTreeHash'] and sha(ENGINE / 'pyproject.toml') == before['pyproject'] == audit['pyprojectHash'] and audit['version'] == '0.1.0',
        'pending716Plus32Equals748': len(accepted) == len(sections['完整P18成果']) == audit['pendingCount'] == 716 and accepted.isdisjoint(exclusions) and len(pending) == 748 and pending == accepted | set(exclusions),
        'pending715HashesMatch': len(audit['pendingHashes']) == 715 and set(audit['pendingHashes']) == accepted - {audit_self} and not drift(audit['pendingHashes']),
        'existing643RetainedWithScoped16Changes': len(before['existingPending']) == 643 and set(before['existingPending']) <= accepted and len(changed_existing) == 16 and changed_existing == set(changes['existingChanged']) == set(audit['existingChanged']) and changed_existing <= set(read(EV / 'documentation-files.json')) | prior.ALLOWED_RUNTIME,
        'exact73NewPending': accepted - set(before['existingPending']) == set(changes['new']) == set(sections['本轮新增文件']) and len(changes['new']) == audit['newCount'] == 73,
        'recordedChangeHashesMatch': all(sha(ENGINE / p) == row['after'] and row['before'] == before['existingPending'].get(p) for p, row in changes['hashes'].items()),
        'originalAndCopiedArchives23Unchanged': len(before['archives']) == 23 and before['archives'] == audit['archives'] and not archive_drift,
        'localHeadAndOriginUnchanged': head == origin == before['head'] == audit['git']['head'] == prior.EXPECTED_HEAD and git('branch', '--show-current').strip() == 'main' and git('rev-list', '--left-right', '--count', 'HEAD...origin/main').strip() == '0\t0',
        'gitIndexEmptyAndUnchanged': not prior.git_paths('diff', '--cached', '--name-only') and index_hash == before['gitIndexHash'] == sha(index_path),
        'pendingGitSetsMatch': tracked == set(audit['git']['trackedChanges']) and untracked == set(audit['git']['untracked']),
        'trackedDiffCheckClean': not git('diff', '--check'),
        'sourcePythonSyntaxAndIdentityStable': not syntax_errors and prior.source_inventory() == source,
    }
    report = dict(checkedAt=datetime.now(timezone.utc).isoformat(), checks=checks,
                  allIdentityChecksPass=all(checks.values()), citedRunsNotIndependentExecutions=runs,
                  counts=dict(source=len(source), originalTests=len(old_ids), newTests=len(static_ids), originalTestFiles=len(old_tests),
                              sourcePython=sum(p.endswith('.py') for p in source), pending=len(accepted), excluded=len(exclusions),
                              tracked=len(tracked), untracked=len(untracked)),
                  sourceHash=prior.source_hash(source), changedRuntimeFiles=sorted(changed_runtime),
                  discrepancies=dict(failedChecks=[k for k, v in checks.items() if not v], archiveDrift=archive_drift, protectionDrift=protection_drift,
                                     syntaxErrors=syntax_errors, pendingHashDrift=drift(audit['pendingHashes'])),
                  gitWrites=False, engineWrites=False, remoteNetworkChecked=False, behaviorTestsRun=False)
    if '--check-only' not in sys.argv:
        with (OUT / 'identity-check.json').open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: report[k] for k in ('allIdentityChecksPass', 'counts', 'sourceHash', 'discrepancies')}, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
