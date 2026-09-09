"""Read-only P17 identity/protection checks; no claims of a new full regression."""
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
EVIDENCE = ENGINE / 'docs/project_memory/p17_evidence'

if __name__ == '__main__':
    before, audit = read(EVIDENCE / 'before.json'), read(EVIDENCE / 'final.audit.json')
    full = read(EVIDENCE / 'full-final-02.json')
    compatibility = read(EVIDENCE / 'compatibility-final-01.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in sorted((ENGINE / folder).rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('p17-final-03', 'compatibility-final-01', 'full-final-02'):
        r = read(EVIDENCE / (name + '.json'))
        stderr = (EVIDENCE / (name + '.stderr.log')).read_text(encoding='utf-8')
        runs[name] = dict(identityMatchesCurrent=r['sourceBefore'] == r['sourceAfter'] == source,
            identityUnchangedDuringRun=r['sourceBefore'] == r['sourceAfter'],
            completed=r['status'] == 'FINISHED' and r['exitCode'] == 0 and
                not r['loaderErrors'] and not r['failures'] and not r['errors'],
            countConsistent=r['run'] == len(set(r['testIdentities'])) == r['passed'] + len(r['skips']),
            rawOutputsPresent=(EVIDENCE / (name + '.stdout.log')).is_file() and
                f"Ran {r['run']} tests" in stderr and '\nOK' in stderr,
            run=r['run'], passed=r['passed'], skips=r['skips'], seconds=r['seconds'])
    delta = {p for p in source.keys() | before['sourceTest'].keys() if source.get(p) != before['sourceTest'].get(p)}
    modified = {p for p in source.keys() & before['sourceTest'].keys() if source[p] != before['sourceTest'][p]}
    compatibility_delta = {p for p in source.keys() | compatibility['sourceAfter'].keys()
                           if source.get(p) != compatibility['sourceAfter'].get(p)}
    tracked = git('diff', '--name-only').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    archive_drift = [name for name, row in before['kickoff'].items()
                     if sha(EVIDENCE / name) != row['sha256'] or sha(Path(row['source'])) != row['sha256']]
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append(dict(path=path, error=str(error)))
    checks = {
        'source252MatchesAuditAndFull': len(source) == 252 and source == audit['sourceTest'] == full['sourceAfter'],
        'currentSpecialtyAndFullIdentitiesExact': all(runs[n]['identityMatchesCurrent'] for n in ('p17-final-03', 'full-final-02')),
        'allThreeRecordedRunsCompleteAndConsistent': all(all(r[k] for k in ('identityUnchangedDuringRun', 'completed', 'countConsistent', 'rawOutputsPresent')) for r in runs.values()),
        'historicalCompatibilityHasOnlyDeclaredFourFileDelta': len(compatibility_delta) == 4 and compatibility_delta == set(audit['tests']['compatibility-final-01']['sourceDelta']),
        'all645CompatibilityIdsCoveredByCurrentFull': len(compatibility['testIdentities']) == 645 and set(compatibility['testIdentities']) <= set(full['testIdentities']),
        'original1286IdentitiesRetained': len(before['testIdentities']) == 1286 and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact62NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 62,
        'originalTestFilesByteUnchanged': not drift({p:h for p,h in before['sourceTest'].items() if p.startswith('tests/')}),
        'sourceChangesOnlyFourOldAndNineNewPaths': len(delta) == 13 and len(source.keys() - before['sourceTest'].keys()) == 9 and modified == set(audit['existingModifiedSource']),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'planning3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']) and base.tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31ScriptsUnchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'otherExcludedReportUnchanged': len(before['otherPreserved']) == 1 and not drift(before['otherPreserved']),
        'kickoffThreeOriginalsAndCopiesExact': len(before['kickoff']) == 3 and not archive_drift,
        'pending136Plus32ExclusionsExact': len(audit['pending']) == 136 and (set(tracked) | set(untracked)) == set(audit['pending']) | set(before['excluded']),
        'recorded135PendingHashesMatch': len(audit['pendingHashes']) == 135 and not drift(audit['pendingHashes']),
        'python242SyntaxValid': sum(p.endswith('.py') for p in source) == 242 and not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse','HEAD') == git('rev-parse','origin/main') == before['head'] == '0c440b0476b07723abafe93777fe895b64fd8d0e',
        'stagingEmpty': not git('diff','--cached','--name-only'),
        'trackedDiffCheckClean': not git('diff','--check'),
        'versionAndPyprojectUnchanged': audit['version'] == '0.1.0' and sha(ENGINE / 'pyproject.toml') == audit['pyprojectHash'],
    }
    result = dict(checks=checks, allIdentityChecksPass=all(checks.values()), notFormalAcceptance=True,
        citedRunsNotIndependent=runs, sourceTestCount=len(source), sourceDelta=sorted(delta),
        compatibilityBeforeLateRepairDelta=sorted(compatibility_delta),
        trackedModifiedCount=len(tracked), untrackedCount=len(untracked), branch=git('branch','--show-current'),
        head=git('rev-parse','HEAD'), aheadBehindLocal=git('rev-list','--left-right','--count','HEAD...origin/main'),
        formalTreeHash=before['formalTreeHash'], syntaxErrors=syntax_errors, archiveDrift=archive_drift,
        gitWrites=False, remoteNetworkChecked=False)
    with (OUT / 'identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
