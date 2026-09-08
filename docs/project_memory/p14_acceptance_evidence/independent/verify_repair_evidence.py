"""Independent read-only identity verification for the R1/R2 repair."""
import ast
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('old_verifier', OUT / 'verify_evidence.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
ENGINE, sha, git, drift = old.ENGINE, old.sha, old.git, old.drift
EVIDENCE = ENGINE / 'docs/project_memory/p14_repair_evidence'


def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding='utf-8'))


if __name__ == '__main__':
    before, full, audit = read('before.json'), read('full-final.json'), read('final.audit.json')
    original_before = old.read('before.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in (ENGINE / folder).rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    changed_source = sorted(p for p in set(source) | set(before['sourceTest'])
                            if source.get(p) != before['sourceTest'].get(p))
    expected_changes = sorted(['src/continuity_engine/domain/dynamic_mind.py',
                              'src/continuity_engine/services/dynamic_mind_service.py',
                              'tests/test_p14_review_repair.py'])
    excluded = set(before['excludedP10'])
    tracked = git('diff', '--name-only').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    pending = sorted((set(tracked) | set(untracked)) - excluded)
    initial_snapshot = json.loads((OUT / 'original-p14-01.before.json').read_text(encoding='utf-8'))
    old_evidence = {p: h for p, h in initial_snapshot.items() if p.startswith('docs/project_memory/p14_evidence/')}
    runs = {}
    for name in ('confirmed-final.json', 'targeted-final.json', 'p14-final.json', 'compatibility-final.json', 'full-final.json'):
        result = read(name)
        runs[name] = {'currentIdentity': result['sourceBefore'] == result['sourceAfter'] == source,
                      'finishedClean': result['status'] == 'FINISHED' and result['exitCode'] == 0
                          and not result['loaderErrors'] and not result['errors'] and not result['failures'],
                      'countsValid': result['run'] == result['passed'] + len(result['skips']) == len(set(result['testIdentities'])),
                      'run': result['run'], 'passed': result['passed'], 'skips': result['skips'], 'seconds': result['seconds']}
    syntax_errors = []
    for name in source:
        if name.endswith('.py'):
            try:
                ast.parse((ENGINE / name).read_text(encoding='utf-8-sig'), filename=name)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append({'file': name, 'error': str(error)})
    review_drift = [p for p, h in before['reviewSources'].items() if not Path(p).is_file() or sha(Path(p)) != h]
    checks = {
        'current221SourceFilesMatchFullAndAudit': len(source) == 221 and source == full['sourceBefore'] == full['sourceAfter'] == audit['sourceTest'],
        'allFiveFinalRunsUseCurrentCodeAndFinishedCleanly': all(r['currentIdentity'] and r['finishedClean'] and r['countsValid'] for r in runs.values()),
        'full1137Count': full['run'] == 1137 and full['passed'] == 1136,
        'onlyThreeAuthorizedSourceChanges': changed_source == expected_changes,
        'original1124IdentitiesRetained': len(before['testIdentities']) == 1124 and set(before['testIdentities']) <= set(full['testIdentities']),
        'only13NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 13,
        'oldTestFilesByteUnchanged': not drift({p: h for p, h in before['sourceTest'].items() if p.startswith('tests/')}),
        'protected63ByteUnchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'formal7ByteUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']),
        'formalTreeUnchanged': old.previous.tree_inventory_hash(ENGINE / '.continuity-data') == original_before['formalTreeHash'],
        'planning3ByteUnchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'excluded31ByteUnchanged': len(excluded) == 31 and not drift(before['excludedP10']),
        'originalP14EvidenceUnchanged': bool(old_evidence) and not drift(old_evidence),
        'original28ReviewFilesUnchanged': len(before['reviewSources']) == 28 and not review_drift,
        'onlyKnownWindows1314Skip': full['skips'] == [['test_p08_fixture_paths.P08FixturePathTests.test_symlink_component_rejected_without_writes', 'OS does not grant symlink creation: 1314']],
        'pending192SetMatches': len(pending) == 192 and pending == sorted(audit['pending']),
        'pending191ContentHashesMatch': len(audit['pendingHashes']) == 191 and not drift(audit['pendingHashes']),
        'python211SyntaxValid': sum(p.endswith('.py') for p in source) == 211 and not syntax_errors,
        'headAndLocalTrackingRefUnchanged': git('rev-parse', 'HEAD') == git('rev-parse', 'origin/main') == before['head'],
        'stagingEmpty': not git('diff', '--cached', '--name-only'),
    }
    report = {'checks': checks, 'allChecksPass': all(checks.values()), 'notAcceptance': True,
              'sourceChanges': changed_source, 'sourceTestCount': len(source), 'citedRunsNotIndependent': runs,
              'reviewOriginalChanges': review_drift, 'originalP14EvidenceCount': len(old_evidence),
              'pendingCount': len(pending), 'trackedModifiedCount': len(tracked), 'untrackedCount': len(untracked),
              'excludedCount': len(excluded), 'head': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
              'aheadBehindLocal': git('rev-list', '--left-right', '--count', 'HEAD...origin/main'),
              'gitWrites': False, 'remoteNetworkChecked': False, 'syntaxErrors': syntax_errors,
              'formalTreeHash': original_before['formalTreeHash']}
    with (OUT / 'repair-identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
