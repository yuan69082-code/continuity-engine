"""Independent P16 repair source, preservation and evidence checks; read-only Engine."""
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
EVIDENCE = ENGINE / 'docs/project_memory/p16_repair_evidence'

if __name__ == '__main__':
    before, audit = read(EVIDENCE / 'before.json'), read(EVIDENCE / 'final.audit.json')
    full = read(EVIDENCE / 'full-final-01.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in sorted((ENGINE / folder).rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('independent-after-01', 'p16-final-01', 'compatibility-final-01', 'full-final-01'):
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
    allowed = {'src/continuity_engine/services/continuity_interaction_service.py',
               'src/continuity_engine/services/external_capability_service.py',
               'src/continuity_engine/services/thinking_service.py',
               'tests/test_p16_repair_edges.py', 'tests/test_p16_review_regressions.py'}
    archive_drift = [name for name,row in before['reviewArchive'].items()
        if sha(EVIDENCE / 'independent' / name) != row['sha256'] or sha(Path(row['source'])) != row['sha256']]
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append(dict(path=path, error=str(error)))
    checks = {
        'source243MatchesRepairAuditAndFull': len(source) == 243 and source == audit['sourceTest'] == full['sourceAfter'],
        'allFourCitedRunsMatchAndAreClean': all(all(r[k] for k in ('identityMatches','completed','countConsistent','rawOutputsPresent')) for r in runs.values()),
        'original1261IdentitiesRetained': len(before['testIdentities']) == 1261 and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact25NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 25,
        'originalTestFilesUnchanged': not drift({p:h for p,h in before['sourceTest'].items() if p.startswith('tests/')}),
        'exactFiveSourceTestRepairPaths': delta == allowed == set(audit['repairSourceDelta']),
        'originalReviewSourceSnapshotMatchesRepairBaseline': all(read(OUT / 'independent-edges-03.after.json').get(p) == h for p,h in before['sourceTest'].items()),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'planning3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']) and base.tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31Unchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'otherPreservedReportUnchanged': len(before['otherPreserved']) == 1 and not drift(before['otherPreserved']),
        'historicalEvidence78Unchanged': len(before['historicalEvidence']) == 78 and not drift(before['historicalEvidence']),
        'independentOriginalsAnd30ArchivedCopiesUnchanged': len(before['reviewArchive']) == 30 and not archive_drift,
        'formalNineProbeCopyByteExact': sha(ENGINE / 'tests/test_p16_review_regressions.py') == sha(OUT / 'test_independent_edges.py'),
        'pending192Plus32ExclusionsExactlyMatch': len(audit['pending']) == 192 and (set(tracked) | set(untracked)) == set(audit['pending']) | set(before['excludedP10']) | set(before['otherPreserved']),
        'prior118PendingPreserved': len(before['previousPending']) == 118 and set(before['previousPending']) <= set(audit['pending']),
        'recorded191PendingHashesMatch': len(audit['pendingHashes']) == 191 and not drift(audit['pendingHashes']),
        'python233SyntaxValid': sum(p.endswith('.py') for p in source) == 233 and not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse','HEAD') == git('rev-parse','origin/main') == before['head'] == 'a41a733635b0f5978c19b287274b4c63925b8979',
        'stagingEmpty': not git('diff','--cached','--name-only'),
        'diffCheckClean': not git('diff','--check'),
    }
    result = dict(checks=checks, allIdentityChecksPass=all(checks.values()), notFormalAcceptance=True,
        citedRunsNotIndependent=runs, sourceTestCount=len(source), repairSourceDelta=sorted(delta),
        trackedModifiedCount=len(tracked), untrackedCount=len(untracked), branch=git('branch','--show-current'),
        head=git('rev-parse','HEAD'), aheadBehindLocal=git('rev-list','--left-right','--count','HEAD...origin/main'),
        formalTreeHash=before['formalTreeHash'], syntaxErrors=syntax_errors, archiveDrift=archive_drift,
        gitWrites=False, remoteNetworkChecked=False)
    with (OUT / 'repair-identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
