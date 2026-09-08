"""Independent source/evidence identity and preservation checks, no Engine writes."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ENGINE = Path(r'C:\Users\Administrator\Documents\continuity-engine')
EVIDENCE = ENGINE / 'docs/project_memory/p15_evidence'
sys.path.insert(0, str(ENGINE / 'src'))
from continuity_engine.testing.persistence import tree_inventory_hash

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def drift(mapping):
    return [p for p, h in mapping.items() if not (ENGINE / p).is_file() or sha(ENGINE / p) != h]

def git(*args):
    proc = subprocess.run([r'E:\Git\cmd\git.exe', '-c', f'safe.directory={ENGINE.as_posix()}',
        '-c', 'core.quotepath=false', '-c', 'core.safecrlf=false', '-C', str(ENGINE), *args],
        capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'GIT_OPTIONAL_LOCKS':'0'})
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return proc.stdout.strip()

if __name__ == '__main__':
    before = read(EVIDENCE / 'before.json')
    audit = read(EVIDENCE / 'final.audit.json')
    full = read(EVIDENCE / 'full-final-2.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p) for folder in ('src', 'tests')
              for p in sorted((ENGINE / folder).rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('p15-final-2', 'compatibility-final-2', 'full-final-2'):
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
    accepted_pending = set(audit['pending'])
    other = {'docs/project_memory/p14_evidence/handoff-discrepancy-20260908.json'}
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append(dict(path=path, error=str(error)))
    checks = {
        'source230MatchesFinalAuditAndFull': len(source) == 230 and source == audit['sourceTest'] == full['sourceAfter'],
        'allThreeCitedRunsMatchAndAreClean': all(all(r[k] for k in ('identityMatches','completed','countConsistent','stdoutPresent','stderrSummaryPresent')) for r in runs.values()),
        'original1137IdentitiesRetained': len(before['testIdentities']) == 1137 and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact39NewTestIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 39,
        'originalTestFilesUnchanged': not drift({p:h for p,h in before['sourceTest'].items() if p.startswith('tests/')}),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'planning3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles']) and tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31Unchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'pending151Plus32ExclusionsExactlyMatch': len(accepted_pending) == 151 and pending == accepted_pending | set(before['excludedP10']) | other,
        'pending150RecordedHashesMatch': len(audit['pendingHashes']) == 150 and not drift(audit['pendingHashes']),
        'pythonSyntaxValid': not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse','HEAD') == git('rev-parse','origin/main') == before['head'] == 'f1185d20da06f52e7e85015bc6b963cf9769d08c',
        'stagingEmpty': not git('diff','--cached','--name-only'),
        'diffCheckClean': not git('diff','--check'),
    }
    result = dict(checks=checks, allIdentityChecksPass=all(checks.values()), notBehavioralAcceptance=True,
        citedRunsNotIndependent=runs, sourceTestCount=len(source), pythonCount=sum(p.endswith('.py') for p in source),
        trackedModifiedCount=len(tracked), untrackedCount=len(untracked), branch=git('branch','--show-current'),
        head=git('rev-parse','HEAD'), aheadBehindLocal=git('rev-list','--left-right','--count','HEAD...origin/main'),
        formalTreeHash=before['formalTreeHash'], syntaxErrors=syntax_errors, gitWrites=False, remoteNetworkChecked=False)
    with (OUT / 'identity-check.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if all(checks.values()) else 1)
