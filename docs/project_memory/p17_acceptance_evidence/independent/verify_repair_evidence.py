"""Independent P17 repair evidence verification, read-only Engine."""
import ast
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prior_verifier', OUT.parent / 'p15-independent-review-20260908/verify_evidence.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ENGINE, read, sha, drift, git = base.ENGINE, base.read, base.sha, base.drift, base.git
EVIDENCE = ENGINE / 'docs/project_memory/p17_repair_evidence'

if __name__ == '__main__':
    before, audit = read(EVIDENCE / 'before.json'), read(EVIDENCE / 'final.audit.json')
    full = read(EVIDENCE / 'full-final-01.json')
    previous_review = read(OUT / 'independent-edges-02.after.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in sorted((ENGINE / folder).rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('formal-after-02', 'independent-after-01', 'p17-final-01', 'compatibility-final-01', 'full-final-01'):
        r = read(EVIDENCE / (name + '.json'))
        stderr = (EVIDENCE / (name + '.stderr.log')).read_text(encoding='utf-8')
        runs[name] = dict(identityMatches=r['sourceBefore'] == r['sourceAfter'] == source,
            completed=r['status'] == 'FINISHED' and r['exitCode'] == 0 and
                not r['loaderErrors'] and not r['failures'] and not r['errors'],
            countConsistent=r['run'] == len(set(r['testIdentities'])) == r['passed'] + len(r['skips']),
            rawOutputsPresent=(EVIDENCE / (name + '.stdout.log')).is_file() and
                f"Ran {r['run']} tests" in stderr and '\nOK' in stderr,
            run=r['run'], passed=r['passed'], skips=r['skips'], seconds=r['seconds'])
    tracked = git('diff', '--name-only').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    delta = {p for p in source.keys() | before['sourceTest'].keys() if source.get(p) != before['sourceTest'].get(p)}
    allowed = {'src/continuity_engine/services/execution_service.py',
               'src/continuity_engine/testing/p17_execution_fixture.py', 'tests/test_p17_repair_edges.py'}
    archive_drift = [name for name,row in before['independentCopies'].items()
        if sha(EVIDENCE / 'independent' / name) != row['sha256'] or sha(Path(row['source'])) != row['sha256']]
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append(dict(path=path, error=str(error)))
    historical = {p:h for p,h in previous_review.items()
                  if p.startswith('docs/project_memory/p17_evidence/')}
    original_files = {p: previous_review[p] for p in audit['originalP17Unchanged']}
    previous_drift = {p for p,h in previous_review.items() if not (ENGINE / p).is_file() or sha(ENGINE / p) != h}
    checks = {
        'source253MatchesRepairAuditAndFull': len(source) == 253 and source == audit['sourceTest'] == full['sourceAfter'],
        'allFiveCitedRunsMatchAndAreClean': all(all(r[k] for k in ('identityMatches','completed','countConsistent','rawOutputsPresent')) for r in runs.values()),
        'original1348IdentitiesRetained': len(before['testIdentities']) == 1348 and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact12NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 12,
        'originalTestFilesUnchanged': not drift({p:h for p,h in before['sourceTest'].items() if p.startswith('tests/')}),
        'exactThreeSourceTestRepairPaths': delta == allowed == set(audit['sourceChangedSinceReview']) | set(audit['sourceAddedSinceReview']),
        'originalReviewSnapshotMatchesRepairBaseline': len(before['sourceTest']) == 252 and all(previous_review.get(p) == h for p,h in before['sourceTest'].items()),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'planning3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']) and base.tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31Unchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'otherExcludedReportUnchanged': len(before['otherPreserved']) == 1 and not drift(before['otherPreserved']),
        'allOriginalP17EvidenceUnchanged': bool(historical) and not drift(historical),
        'independent21OriginalsAndArchivedCopiesExact': len(before['independentCopies']) == 21 and not archive_drift,
        'prior113UnchangedFilesMatchIndependentSnapshot': len(original_files) == 113 and not drift(original_files),
        'only23DeclaredExistingEnginePathsChangedSinceReview': len(previous_drift) == 23 and previous_drift == set(audit['repairModifiedExisting']),
        'pending196Plus32ExclusionsExactlyMatch': len(audit['pending']) == 196 and (set(tracked) | set(untracked)) == set(audit['pending']) | set(before['excluded']),
        'prior136PendingPreserved': len(before['originalPending']) == 136 and set(before['originalPending']) <= set(audit['pending']),
        'recorded195PendingHashesMatch': len(audit['pendingHashes']) == 195 and not drift(audit['pendingHashes']),
        'python243SyntaxValid': sum(p.endswith('.py') for p in source) == 243 and not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse','HEAD') == git('rev-parse','origin/main') == before['head'] == '0c440b0476b07723abafe93777fe895b64fd8d0e',
        'stagingEmpty': not git('diff','--cached','--name-only'),
        'trackedDiffCheckClean': not git('diff','--check'),
        'versionAndPyprojectUnchanged': audit['version'] == '0.1.0' and sha(ENGINE / 'pyproject.toml') == before['pyproject'] == audit['pyprojectHash'],
    }
    result = dict(checks=checks, allIdentityChecksPass=all(checks.values()), notFormalAcceptance=True,
        citedRunsNotIndependent=runs, sourceTestCount=len(source), repairSourceDelta=sorted(delta),
        historicalEvidenceCount=len(historical), existingChangedSinceReview=sorted(previous_drift),
        trackedModifiedCount=len(tracked), untrackedCount=len(untracked), branch=git('branch','--show-current'),
        head=git('rev-parse','HEAD'), aheadBehindLocal=git('rev-list','--left-right','--count','HEAD...origin/main'),
        formalTreeHash=before['formalTreeHash'], syntaxErrors=syntax_errors, archiveDrift=archive_drift,
        gitWrites=False, remoteNetworkChecked=False)
    with (OUT / 'repair-identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
