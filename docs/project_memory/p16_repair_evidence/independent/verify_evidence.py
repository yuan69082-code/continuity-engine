"""Independent P16 evidence identity audit; no Engine or Git writes."""
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
EVIDENCE = ENGINE / 'docs/project_memory/p16_evidence'

if __name__ == '__main__':
    before = read(EVIDENCE / 'before.json')
    audit = read(EVIDENCE / 'final.audit.json')
    full = read(EVIDENCE / 'full-final.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in sorted((ENGINE / folder).rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('p16-final', 'compatibility-final', 'full-final'):
        result = read(EVIDENCE / (name + '.json'))
        stderr = (EVIDENCE / (name + '.stderr.log')).read_text(encoding='utf-8')
        runs[name] = dict(identityMatches=result['sourceBefore'] == result['sourceAfter'] == source,
            completed=result['status'] == 'FINISHED' and result['exitCode'] == 0 and
                not result['loaderErrors'] and not result['failures'] and not result['errors'],
            countConsistent=result['run'] == len(set(result['testIdentities'])) == result['passed'] + len(result['skips']),
            stdoutPresent=(EVIDENCE / (name + '.stdout.log')).is_file(),
            stderrSummaryPresent=f"Ran {result['run']} tests" in stderr and '\nOK' in stderr,
            run=result['run'], passed=result['passed'], skips=result['skips'], seconds=result['seconds'])
    tracked = git('diff', '--name-only').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    pending = set(tracked) | set(untracked)
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append(dict(path=path, error=str(error)))
    checks = {
        'source241MatchesFinalAuditAndFull': len(source) == 241 and source == audit['sourceTest'] == full['sourceAfter'],
        'allThreeCitedRunsMatchAndAreClean': all(all(r[k] for k in ('identityMatches','completed','countConsistent','stdoutPresent','stderrSummaryPresent')) for r in runs.values()),
        'original1208IdentitiesRetained': len(before['testIdentities']) == 1208 and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact53NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 53,
        'originalTestFilesUnchanged': not drift({p:h for p,h in before['sourceTest'].items() if p.startswith('tests/')}),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'planning3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']) and base.tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31Unchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'otherPreservedReportUnchanged': len(before['otherPreserved']) == 1 and not drift(before['otherPreserved']),
        'pending118Plus32ExclusionsExactlyMatch': len(audit['pending']) == 118 and pending == set(audit['pending']) | set(before['excludedP10']) | set(before['otherPreserved']),
        'recordedPendingHashesMatch': not drift(audit['pendingHashes']),
        'python231SyntaxValid': sum(p.endswith('.py') for p in source) == 231 and not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse','HEAD') == git('rev-parse','origin/main') == before['head'] == 'a41a733635b0f5978c19b287274b4c63925b8979',
        'stagingEmpty': not git('diff','--cached','--name-only'),
        'diffCheckClean': not git('diff','--check'),
    }
    result = dict(checks=checks, allIdentityChecksPass=all(checks.values()), notBehavioralAcceptance=True,
        citedRunsNotIndependent=runs, sourceTestCount=len(source), pendingHashCount=len(audit['pendingHashes']),
        trackedModifiedCount=len(tracked), untrackedCount=len(untracked), branch=git('branch','--show-current'),
        head=git('rev-parse','HEAD'), aheadBehindLocal=git('rev-list','--left-right','--count','HEAD...origin/main'),
        formalTreeHash=before['formalTreeHash'], syntaxErrors=syntax_errors, gitWrites=False, remoteNetworkChecked=False)
    with (OUT / 'identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
