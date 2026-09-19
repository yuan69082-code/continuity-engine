"""Read-only P18 evidence verification; no Engine imports or behavior tests.

Only identity-check.json beside this script is created, exclusively. --check-only
prints the same results without writing, to separate schema assumptions from
evidence discrepancies. Engine source, data, Git index, and evidence stay intact.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

OUT = Path(__file__).resolve().parent
ENGINE = Path(r'C:\Users\Administrator\Documents\continuity-engine')
EVIDENCE = ENGINE / 'docs/project_memory/p18_storage_final_evidence'
EXPECTED_HEAD = '5a3247a5d23ff17de2b4ba12bc327594b492e725'
ALLOWED_RUNTIME = {
    'src/continuity_engine/storage/json_repository.py',
    'src/continuity_engine/storage/json_runtime_repository.py',
}
NEW_TEST_FILES = {'tests/test_p18_storage_retry.py', 'tests/test_p18_storage_runtime.py'}
SELECTED = {
    'boundaries-final-04', 'originals-final-03', 'advancing-final-02',
    'prior-boundaries-final-01', 'native-denial-final-02', 'p18-final-01',
    'compatibility-final-01', 'full-final-01',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drift(mapping):
    return sorted(p for p, h in mapping.items()
                  if not (ENGINE / p).is_file() or sha(ENGINE / p) != h)


def source_inventory():
    return {p.relative_to(ENGINE).as_posix(): sha(p)
            for folder in ('src', 'tests') for p in sorted((ENGINE / folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def source_hash(mapping, *, compact=False):
    options = {'separators': (',', ':')} if compact else {}
    return 'sha256:' + hashlib.sha256(json.dumps(mapping, sort_keys=True, **options).encode()).hexdigest()


def tree_inventory_hash(root):
    # The audited formal inventory contains ASCII path/hash strings only. Compact
    # sorted-key JSON is therefore identical to its RFC 8785 canonical encoding.
    items = []
    for p in sorted(root.rglob('*'), key=lambda item: item.as_posix()):
        if p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Formal inventory contains a link; do not follow it')
        if p.is_file():
            relative = p.relative_to(root).as_posix()
            relative.encode('ascii')
            items.append({'relativePath': relative, 'fileHash': 'sha256:' + sha(p)})
    canonical = json.dumps(items, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    return 'sha256:' + hashlib.sha256(canonical).hexdigest()


def git(*args):
    process = subprocess.run([
        r'E:\Git\cmd\git.exe', '-c', f'safe.directory={ENGINE.as_posix()}',
        '-c', 'core.quotepath=false', '-c', 'core.safecrlf=false', '-C', str(ENGINE), *args,
    ], capture_output=True, text=True, encoding='utf-8',
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    if process.returncode:
        raise RuntimeError(f'Read-only git {args[0]} failed: {process.stderr}')
    return process.stdout


def git_paths(*args):
    return set(filter(None, git(*args, '-z').split('\0')))


def markdown_sections(path):
    result, section = {}, None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            section = line[3:]
            result[section] = []
        elif line.startswith('- ') and section is not None:
            result[section].append(line[2:])
    return result


def main():
    if sys.argv[1:] not in ([], ['--check-only']):
        raise ValueError('Only --check-only is supported')
    before = read(EVIDENCE / 'before.json')
    audit = read(EVIDENCE / 'final.audit-02.json')
    frozen = read(EVIDENCE / 'frozen-source-02.json')
    selected = read(EVIDENCE / 'selected-runs.json')
    changes = read(EVIDENCE / 'turn-changes-02.json')
    sections = markdown_sections(EVIDENCE / 'final.pending-files-02.md')
    index_path = Path(git('rev-parse', '--path-format=absolute', '--git-path', 'index').strip())
    index_before = sha(index_path)
    source = source_inventory()
    protected = before['protected']
    exclusions = {**protected['excludedP10'], **protected['otherPreserved']}
    group_drift = {name: drift(mapping) for name, mapping in protected.items()}
    original_test_files = {p: h for p, h in before['sourceTest'].items() if p.startswith('tests/')}
    changed_runtime = {p for p, h in before['sourceTest'].items()
                       if p.startswith('src/') and source.get(p) != h}
    source_added = set(source) - set(before['sourceTest'])
    source_removed = set(before['sourceTest']) - set(source)
    old_ids = set(before['testIdentities'])
    full = read(EVIDENCE / (selected['full'] + '.json'))
    full_ids = set(full['testIdentities'])
    new_ids = full_ids - old_ids
    static_added_ids, syntax_errors = set(), []
    for relative in source:
        if not relative.endswith('.py'):
            continue
        try:
            module = ast.parse((ENGINE / relative).read_text(encoding='utf-8-sig'), filename=relative)
        except (SyntaxError, UnicodeError) as error:
            syntax_errors.append({'file': relative, 'error': str(error)})
            continue
        if relative in NEW_TEST_FILES:
            for cls in module.body:
                if isinstance(cls, ast.ClassDef):
                    for method in cls.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith('test_'):
                            static_added_ids.add(f'{Path(relative).stem}.{cls.name}.{method.name}')
    runs = {}
    for label in selected['runs']:
        row = read(EVIDENCE / (label + '.json'))
        stderr = (EVIDENCE / (label + '.stderr.log')).read_text(encoding='utf-8')
        summary = {k: row[k] for k in ('run', 'passed', 'seconds', 'exitCode', 'status', 'skips')}
        summary.update(failures=len(row['failures']), errors=len(row['errors']))
        run_checks = {
            'sourceMatches': row['sourceBefore'] == row['sourceAfter'] == source,
            'finishedCleanly': row['status'] == 'FINISHED' and row['exitCode'] == 0
                              and not row['loaderErrors'] and not row['failures'] and not row['errors'],
            'countConsistent': row['run'] == len(row['testIdentities']) == len(set(row['testIdentities']))
                               == row['passed'] + len(row['skips']),
            'auditSummaryMatches': summary == audit['results'].get(label),
            'rawLogsPresent': (EVIDENCE / (label + '.stdout.log')).is_file()
                              and f"Ran {row['run']} tests" in stderr
                              and re.search(r'^OK(?: \(skipped=\d+\))?\s*$', stderr, re.MULTILINE) is not None,
        }
        runs[label] = {'checks': run_checks, **summary}
    formal = {p.relative_to(ENGINE).as_posix(): sha(p)
              for p in (ENGINE / '.continuity-data').rglob('*') if p.is_file()}
    formal_hash = tree_inventory_hash(ENGINE / '.continuity-data')
    tracked = git_paths('diff', '--name-only')
    untracked = git_paths('ls-files', '--others', '--exclude-standard')
    staged = git_paths('diff', '--cached', '--name-only')
    pending = tracked | untracked
    accepted_list = sections['完整P18成果']
    accepted = set(accepted_list)
    audit_self = (EVIDENCE / 'final.audit-02.json').relative_to(ENGINE).as_posix()
    current_changed = {p for p, h in before['existingPending'].items()
                       if not (ENGINE / p).is_file() or sha(ENGINE / p) != h}
    allowed_changes = set(read(EVIDENCE / 'documentation-files.json')) | ALLOWED_RUNTIME
    recorded_change_hash_drift = [p for p, row in changes['hashes'].items()
                                  if sha(ENGINE / p) != row['after']
                                  or row['before'] != before['existingPending'].get(p)]
    archive_drift = []
    for original, row in before['archives'].items():
        if sha(ENGINE / row['copy']) != row['sha256']:
            archive_drift.append(row['copy'])
        if original not in ALLOWED_RUNTIME and sha(ENGINE / original) != row['sha256']:
            archive_drift.append(original)
    latest_preimages_match = all(
        sha(EVIDENCE / 'source-before' / Path(p).name) == before['sourceTest'][p]
        for p in ALLOWED_RUNTIME)
    current_head = git('rev-parse', 'HEAD').strip()
    local_origin = git('rev-parse', 'origin/main').strip()
    branch = git('branch', '--show-current').strip()
    ahead_behind = git('rev-list', '--left-right', '--count', 'HEAD...origin/main').strip()
    diff_check = git('diff', '--check')
    checks = {
        'source269MatchesFreezeAuditAndFull': len(source) == 269 and source == frozen['source'] == audit['source'] == full['sourceAfter'],
        'sourceAggregateHashesMatch': source_hash(source) == frozen['sourceHash'] == audit['sourceHash']
                                      and source_hash(before['sourceTest'], compact=True) == before['sourceHash'],
        'eightSelectedRunsMatchAndAreClean': set(selected['runs']) == SELECTED == set(audit['results'])
                                            and len(selected['runs']) == 8
                                            and all(all(r['checks'].values()) for r in runs.values()),
        'original1480IdentitiesRetained': len(before['testIdentities']) == len(old_ids) == 1480
                                         and old_ids <= full_ids and frozen['originalIdentities'] == before['testIdentities'],
        'exact27NewIdentitiesAndStaticDefinitions': len(new_ids) == 27 and new_ids == set(frozen['addedIdentities']) == static_added_ids,
        'full1507IdentitiesMatchFreeze': len(full_ids) == 1507 and full['testIdentities'] == frozen['identities'],
        'originalTestFilesUnchanged': not drift(original_test_files),
        'onlyTwoExistingRuntimeFilesChanged': changed_runtime == ALLOWED_RUNTIME == set(frozen['changedRuntimeFiles']) == set(before['allowedRuntimeFiles']),
        'onlyTwoNewTestFilesAndNoSourceRemoval': source_added == NEW_TEST_FILES and not source_removed,
        'protectedNested63Plans3Formal7Exclusions32Unchanged':
            {k: len(v) for k, v in protected.items()} == audit['protectedCounts'] ==
            {'protected': 63, 'plans': 3, 'formalFiles': 7, 'excludedP10': 31, 'otherPreserved': 1}
            and not any(group_drift.values()) and len(exclusions) == 32
            and exclusions == audit['excluded'] and set(exclusions) == set(before['excluded']),
        'formalSevenFilesAndTreeUnchanged': len(formal) == 7 and formal == protected['formalFiles'] == audit['formalFiles']
                                          and formal_hash == before['formalTreeHash'] == audit['formalTreeHash'],
        'pyprojectAndVersionUnchanged': sha(ENGINE / 'pyproject.toml') == before['pyproject'] == audit['pyprojectHash']
                                      and tomllib.loads((ENGINE / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version'] == audit['version'] == '0.1.0',
        'pending643Plus32Equals675': len(accepted_list) == len(accepted) == audit['pendingCount'] == 643
                                    and len(pending) == 675 and accepted.isdisjoint(exclusions)
                                    and pending == accepted | set(exclusions),
        'pending642HashesMatchWithOnlyAuditSelfExcluded': len(audit['pendingHashes']) == 642
                                                        and set(audit['pendingHashes']) == accepted - {audit_self}
                                                        and not drift(audit['pendingHashes']),
        'original548PendingPreservedWithOnly16AllowedChanges': len(before['existingPending']) == audit['existingPending'] == 548
                                                               and set(before['existingPending']) <= accepted
                                                               and len(current_changed) == 16
                                                               and current_changed == set(changes['existingChanged']) == set(audit['existingChanged'])
                                                               and current_changed <= allowed_changes,
        'exact95NewPendingAndManifestListsAgree': accepted - set(before['existingPending']) == set(changes['new']) == set(sections['本轮新增文件'])
                                                and len(changes['new']) == audit['newCount'] == 95
                                                and set(sections['本轮修改既有文件']) == current_changed,
        'recordedChangeHashesMatch': not recorded_change_hash_drift,
        'archivesAndLatestPreimagesPreserved': len(before['archives']) == 10 and before['archives'] == audit['archives']
                                             and not archive_drift and latest_preimages_match,
        'sourcePythonSyntaxValid': not syntax_errors,
        'localBaselineAndBranchUnchanged': current_head == local_origin == before['head'] == audit['git']['head'] == EXPECTED_HEAD
                                          and branch == before['branch'] == audit['git']['branch'] == 'main'
                                          and ahead_behind == '0\t0',
        'indexEmptyAndUnchanged': not staged and sha(index_path) == index_before,
        'pendingGitSetsMatchAudit': tracked == set(audit['git']['trackedChanges']) and untracked == set(audit['git']['untracked']),
        'gitDiffCheckClean': not diff_check,
        'sourceStableDuringVerification': source_inventory() == source,
    }
    result = {
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'allIdentityChecksPass': all(checks.values()), 'behaviorTestsRun': False,
        'citedRunsAreRevalidatedEvidenceNotIndependentExecutions': runs,
        'counts': {'sourceTestFiles': len(source), 'sourcePythonFiles': sum(p.endswith('.py') for p in source),
                   'originalTestFiles': len(original_test_files), 'originalIdentities': len(old_ids), 'newIdentities': len(new_ids),
                   'currentIdentities': len(full_ids), 'protectedGroups': {k: len(v) for k, v in protected.items()},
                   'pending': len(accepted), 'excluded': len(exclusions), 'totalGitPending': len(pending),
                   'trackedModified': len(tracked), 'untracked': len(untracked), 'pendingHashes': len(audit['pendingHashes'])},
        'sourceHash': source_hash(source), 'formalTreeHash': formal_hash,
        'beforeSourceHash': source_hash(before['sourceTest'], compact=True),
        'preflightAssumptionCorrection': {
            'mode': '--check-only; no result file was created or overwritten',
            'initialFailedCheck': 'sourceAggregateHashesMatch',
            'classification': 'VERIFIER_SERIALIZATION_ASSUMPTION',
            'explanation': 'The first preflight used current freeze default JSON spacing for both epochs. The inherited before hash uses compact separators; the current freeze uses default spacing. Per-file hashes and all other 23 checks passed in that preflight.',
            'algorithmSources': ['docs/project_memory/p18_persistence_evidence/audit.py:43',
                                 'docs/project_memory/p18_storage_final_evidence/freeze.py:13'],
        },
        'head': current_head, 'localOrigin': local_origin, 'branch': branch, 'aheadBehindLocal': ahead_behind,
        'indexHashBefore': index_before, 'indexHashAfter': sha(index_path),
        'changedRuntimeFiles': sorted(changed_runtime),
        'discrepancies': {'failedChecks': [k for k, passed in checks.items() if not passed],
                          'protectedDrift': group_drift, 'pendingHashDrift': drift(audit['pendingHashes']),
                          'unexpectedGitPending': sorted(pending - accepted - set(exclusions)),
                          'missingGitPending': sorted((accepted | set(exclusions)) - pending),
                          'recordedChangeHashDrift': recorded_change_hash_drift, 'archiveDrift': archive_drift,
                          'syntaxErrors': syntax_errors},
        'limitations': ['No behavior tests or unittest discovery were executed.',
                        'Git origin/main is the existing local tracking reference; network and CI were not checked.',
                        'The audit excludes its own hash; its consistency was checked against independent files and current state.',
                        'Formal data was hashed only; no content was printed or changed.'],
        'gitWrites': False, 'engineWrites': False, 'remoteNetworkChecked': False,
    }
    if '--check-only' not in sys.argv:
        with (OUT / 'identity-check.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
