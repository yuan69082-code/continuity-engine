"""Independent P15 repair identity audit; never writes the Engine repository."""
import ast
import json
import sys
from verify_evidence import ENGINE, OUT, read, sha, drift, git, tree_inventory_hash


def main():
    evidence = ENGINE / 'docs/project_memory/p15_repair_evidence'
    before = read(evidence / 'before.json')
    audit = read(evidence / 'final.audit.json')
    full = read(evidence / 'full-final.json')
    source = {p.relative_to(ENGINE).as_posix(): sha(p)
              for folder in ('src', 'tests') for p in sorted((ENGINE / folder).rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    runs = {}
    for name in ('independent-stable', 'targeted-stable', 'p15-stable', 'compatibility-final', 'full-final'):
        result = read(evidence / (name + '.json'))
        log = (evidence / (name + '.stderr.log')).read_text(encoding='utf-8')
        runs[name] = {
            'identityMatches': result['sourceBefore'] == result['sourceAfter'] == source,
            'completed': result['status'] == 'FINISHED' and result['exitCode'] == 0
                and not result['loaderErrors'] and not result['failures'] and not result['errors'],
            'countConsistent': result['run'] == len(set(result['testIdentities']))
                == len(result['testIdentities']) == result['passed'] + len(result['skips']),
            'stderrSummaryPresent': f"Ran {result['run']} tests" in log and '\nOK' in log,
            'stdoutPresent': (evidence / (name + '.stdout.log')).is_file(),
            'run': result['run'], 'passed': result['passed'], 'skips': result['skips'], 'seconds': result['seconds'],
        }
    delta = sorted(p for p in set(source) | set(before['sourceTest']) if source.get(p) != before['sourceTest'].get(p))
    expected_delta = {
        'src/continuity_engine/storage/json_repository.py',
        'src/continuity_engine/domain/learning.py',
        'src/continuity_engine/services/learning_service.py',
        'src/continuity_engine/services/subject_growth_service.py',
        'src/continuity_engine/storage/json_learning_repository.py',
        'src/continuity_engine/services/mind_projection_service.py',
        'tests/test_p15_review_regressions.py', 'tests/test_p15_repair_edges.py',
    }
    tracked = git('diff', '--name-only').splitlines()
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    pending = set(tracked) | set(untracked)
    old_evidence = {p: h for p, h in before['workspace'].items()
                    if p.startswith(('docs/project_memory/p15_evidence/', 'docs/project_memory/p14_evidence/'))}
    syntax_errors = []
    for path in source:
        if path.endswith('.py'):
            try:
                ast.parse((ENGINE / path).read_text(encoding='utf-8-sig'), filename=path)
            except (SyntaxError, UnicodeError) as exc:
                syntax_errors.append({'path': path, 'error': str(exc)})
    checks = {
        'source232MatchesFinalAuditAndFull': len(source) == 232 and source == audit['sourceTest'] == full['sourceAfter'],
        'fiveCitedRunsMatchAndAreClean': all(all(r[k] for k in (
            'identityMatches', 'completed', 'countConsistent', 'stderrSummaryPresent', 'stdoutPresent')) for r in runs.values()),
        'original1176IdentitiesRetained': len(before['testIdentities']) == 1176
            and set(before['testIdentities']) <= set(full['testIdentities']),
        'exact32NewIdentities': len(set(full['testIdentities']) - set(before['testIdentities'])) == 32,
        'allOriginalTestFilesUnchanged': not drift({p: h for p, h in before['sourceTest'].items() if p.startswith('tests/')}),
        'onlySixApprovedSourcesAndTwoNewTests': set(delta) == expected_delta,
        'originalIndependentMaterialUnchanged': len(before['reviewSources']) == 11 and not drift(before['reviewSources']),
        'formalRegressionEqualsOriginalProbeBytes': sha(ENGINE / 'tests/test_p15_review_regressions.py') == sha(OUT / 'p15_review_probe.py'),
        'independentEvidenceCopiesExact': all(sha(p) == sha(OUT / p.name) for p in (evidence / 'independent').iterdir() if p.is_file()),
        'historicalP14P15EvidencePreserved': not drift(old_evidence),
        'protected63Unchanged': len(before['protected']) == 63 and not drift(before['protected']),
        'plans3Unchanged': len(before['plans']) == 3 and not drift(before['plans']),
        'formal7AndTreeUnchanged': len(before['formalFiles']) == 7 and not drift(before['formalFiles'])
            and tree_inventory_hash(ENGINE / '.continuity-data') == before['formalTreeHash'],
        'excluded31Unchanged': len(before['excludedP10']) == 31 and not drift(before['excludedP10']),
        'pending218Plus32ExclusionsExactlyMatch': len(audit['pending']) == 218
            and pending == set(audit['pending']) | set(before['excludedP10']) | set(audit['otherPreserved']),
        'recordedPending217HashesMatch': len(audit['pendingHashes']) == 217 and not drift(audit['pendingHashes']),
        'otherPreservedUnchanged': not drift(audit['otherPreserved']),
        'pythonSyntaxValid': not syntax_errors,
        'headAndTrackingUnchanged': git('rev-parse', 'HEAD') == git('rev-parse', 'origin/main')
            == before['head'] == 'f1185d20da06f52e7e85015bc6b963cf9769d08c',
        'stagingEmpty': not git('diff', '--cached', '--name-only'),
        'diffCheckClean': not git('diff', '--check'),
    }
    result = {'checks': checks, 'allIdentityChecksPass': all(checks.values()),
              'notBehavioralAcceptance': True, 'citedRunsNotIndependent': runs,
              'sourceCount': len(source), 'pythonCount': sum(p.endswith('.py') for p in source),
              'repairDelta': delta, 'trackedModifiedCount': len(tracked), 'untrackedCount': len(untracked),
              'branch': git('branch', '--show-current'), 'head': git('rev-parse', 'HEAD'),
              'formalTreeHash': before['formalTreeHash'], 'syntaxErrors': syntax_errors,
              'gitWrites': False, 'remoteNetworkChecked': False}
    with (OUT / 'repair-identity-check-20260909.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: result[k] for k in ('checks', 'allIdentityChecksPass', 'sourceCount', 'pythonCount', 'trackedModifiedCount', 'untrackedCount')}, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
