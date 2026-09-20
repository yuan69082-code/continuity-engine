"""Read-only Engine review. All mutable subjects are disposable TEST fixtures.

Run with PYTHONDONTWRITEBYTECODE=1. This is reviewer evidence, not an Engine test
addition or acceptance. No network, real adapters, or source edits.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stderr
from copy import deepcopy
from dataclasses import replace
from io import StringIO
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

ENGINE = Path('C:/Users/Administrator/Documents/continuity-engine')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE / 'src'))


def git(*args):
    return subprocess.check_output([
        'E:/Git/cmd/git.exe', '-c', 'safe.directory=' + ENGINE.as_posix(),
        '-c', 'core.quotepath=false', '-c', 'core.safecrlf=false', '-C', str(ENGINE), *args
    ], env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode('utf8')


def snapshot():
    tracked = git('ls-files', '-z').split('\0')
    untracked = git('ls-files', '--others', '--exclude-standard', '-z').split('\0')
    hashes = {}
    for name in tracked + untracked:
        if name:
            hashes[name] = hashlib.sha256((ENGINE / name).read_bytes()).hexdigest()
    return dict(head=git('rev-parse', 'HEAD').strip(), status=git('status', '--porcelain=v1'),
                tracked_count=sum(bool(p) for p in tracked),
                untracked_count=sum(bool(p) for p in untracked), hashes=hashes)


def pure_probes():
    from continuity_engine.domain.action import ActionIntent, ActionType, RiskLevel, ResourceLimits, PermissionCheck
    from continuity_engine.services.action_service import ActionService
    from continuity_engine.domain.resources import ResourceState, ResourceRequest, RuntimeMode, ResourceSessionType
    from continuity_engine.domain.resource_policy import ResourcePolicy
    from continuity_engine.domain.thinking import ThinkingDepth
    from continuity_engine.domain.learning import validate_learning_mutation
    from continuity_engine.domain.events import StateMutation, ChangeOperation
    from continuity_engine.services.continuity_core_service import CoreDecisionPolicy
    from continuity_engine.domain.action_planning import digest
    from continuity_engine.domain.dynamic_mind import MindState
    from continuity_engine.services.dynamic_mind_service import MindDynamics
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    class Permissions:
        def check(self, permission, **kwargs):
            return PermissionCheck(permission, True, True, False, False, False, True, 'isolated valid permission')
    gate = ActionService(Permissions(), None)
    results = {'risk': [], 'depth': [], 'learning': []}
    for action_type, target, confirmed in [
        (ActionType.UPDATE_STATE, 'subject:ordinary', True),
        (ActionType.UPDATE_STATE, 'subject:noncritical', True),
        (ActionType.USE_TOOL, 'local-readonly-notes', False),
        (ActionType.USE_TOOL, 'local-readonly-notes', True),
        (ActionType.USE_TOOL, 'local-readonly-critical-notes', True),
    ]:
        intent = ActionIntent('probe', action_type, 'review intent', 'same evidence', target,
                              'isolated local operation', 1.0, RiskLevel.LOW, ['test:permit'], 0, now)
        d = gate.assess_local_action(intent, subject_id='review-subject', environment='TEST',
                                    limits=ResourceLimits(), confirmed=confirmed)
        results['risk'].append(dict(action=action_type.value, target=target, confirmed=confirmed,
                                   risk=d.evaluated_risks.risk_level.value, approved=d.approved,
                                   reason=d.rejection_reason, automatic=d.can_execute_automatically))
    request = ResourceRequest.create(subject_id='review-subject', session_id='review-session',
        session_type=ResourceSessionType.THINKING, estimated_tokens=4096, estimated_compute=4,
        model_name='review-no-provider-call', reason='internal request for deeper reflection',
        requested_at=now, requested_depth=ThinkingDepth.DEEP)
    for mode in RuntimeMode:
        state = ResourceState.create(subject_id='review-subject', token_budget=100000,
                                     compute_budget=1000, current_mode=mode, updated_at=now)
        d = ResourcePolicy().evaluate(state, request, decided_at=now)
        results['depth'].append(dict(mode=mode.value, requested='DEEP', approved=d.approved_depth.value,
                                    allowed=d.allowed, reason=d.reason))
    for path, operation, value in [
        ('identity.stable_traits', ChangeOperation.APPEND, 'curious'),
        ('identity.stable_traits', ChangeOperation.REMOVE, 'curious'),
        ('identity.self_concept', ChangeOperation.SET, 'a changing explorer'),
    ]:
        try:
            validate_learning_mutation(StateMutation(path, operation, value, 'review learning'))
            outcome = 'accepted'
        except Exception as exc:
            outcome = type(exc).__name__ + ': ' + str(exc)
        results['learning'].append(dict(field=path, operation=operation.value, outcome=outcome))
    thinking = NS(session=NS(result=NS(update_subject_state=False, request_more_memory=False,
                        suggest_future_user_contact=True, should_wait=False, result_id='test-result')))
    context = NS(mind=None, composition=NS(snapshot=NS(environment='TEST', snapshot_hash=digest('snapshot'),
                       source_revision=0, fragments=(NS(fragment_id='review-fragment'),))))
    operation = NS(subject_id='review-subject', operation_id='review-op')
    results['core_choice'] = []
    for approved in (True, False):
        action = NS(decision=NS(approved=approved, created_at=now))
        choice = CoreDecisionPolicy().choose(operation, context, thinking, action)
        results['core_choice'].append(dict(execution_approval=approved,
                       internal_contact_intent=thinking.session.result.suggest_future_user_contact,
                       structured_choice=None if choice is None else [s.capability for s in choice.steps]))
    initial = MindState.create('review-subject', 'TEST', now)
    frame = MindDynamics().advance(initial, at=now + timedelta(hours=1))
    results['endogenous'] = dict(desire_count=len(frame.state.desires),
        origins=sorted({d['origin'] for d in frame.state.desires}),
        thoughts=len(frame.state.thoughts), will_count=len(frame.state.will),
        dispositions=frame.state.dispositions)
    previous_a = deepcopy(frame.state.will)
    previous_b = deepcopy(frame.state.will)
    previous_a[0]['commitment'] = 'Maintain a long-term promise to explore this relationship.'
    previous_b[0]['commitment'] = 'Maintain a long-term promise to avoid this relationship.'
    next_a = MindDynamics().advance(replace(frame.state, will=previous_a), at=now + timedelta(hours=2))
    next_b = MindDynamics().advance(replace(frame.state, will=previous_b), at=now + timedelta(hours=2))
    results['prior_will'] = dict(different_prior_commitments=True,
        next_states_identical=next_a.state.to_dict() == next_b.state.to_dict(),
        resulting_commitment=next_a.state.will[0]['commitment'],
        interpretation='bounded counterfactual: prior Will.commitment is not an input to deliberation')
    from continuity_engine.domain.persistent_runtime import RuntimePolicy
    from continuity_engine.services.runtime_cognition import RuntimeCognition
    saturated = MindDynamics().advance(initial, at=now + timedelta(days=365)).state
    stable_state = NS(revision=7, intentions=NS(dynamic_mind=saturated.to_dict()))
    work = NS(subject_id='review-subject', environment='TEST', policy=RuntimePolicy(),
        scheduler=NS(list_tasks=lambda **kwargs: []),
        core=NS(subject_states=NS(require_active=lambda *args: stable_state),
                mind=NS(dynamics=MindDynamics()), memory=NS(list_memories=lambda *args, **kwargs: []),
                timeline=NS(rebuild=lambda *args: NS(entries=[]))))
    results['saturation'] = dict(drives=saturated.drives, desires=len(saturated.desires),
        unresolved_thoughts=sum(t['unresolved'] for t in saturated.thoughts),
        task_counts=[dict(additional_days=days, needs=len(RuntimeCognition.needs(work,
            saturated.updated_at + timedelta(days=days)))) for days in (1, 7, 365)],
        interpretation='native needs selector only, synthetic saturated state; not a one-year endurance run')
    return results


def native_fixture_probe(allow_world):
    from continuity_engine.testing.p18_runtime_fixture import P18Fixture
    with tempfile.TemporaryDirectory(prefix='p19-') as root:
        f = P18Fixture(Path(root), mode='contact')
        f.boundary.allowed = allow_world
        initial = f.state
        with f.host.running():
            f.advance(3600)
            f.host.tick()
            f.advance(60)
            f.host.tick()
            latest = f.state
            captured = f.provider.inputs[-1].continuity_context.mind if f.provider.inputs else None
            result = dict(world_allowed=allow_world, calls=f.provider.calls,
                computed_desires=len(captured['proposal']['desires']) if captured else None,
                before_revision=initial.revision, after_revision=latest.revision,
                committed_mind=latest.intentions.dynamic_mind is not None,
                effects=f.fake.effect_count, credits=f.fake.credits,
                action_status=f.core.last_action.status if f.core.last_action else None,
                action_results=[r.to_dict() for r in f.core.last_action.results if r] if f.core.last_action else [],
                host=f.host.query())
            f.control('STOP')
            f.host.tick()
        if not f.provider.calls:
            result['probe_status'] = 'INCONCLUSIVE: native provider was not reached'
        else:
            result['probe_status'] = 'OBSERVED'
        return result


def main():
    before = snapshot()
    results = {'scope': 'bounded independent diagnostic probes, not full regression', 'head': before['head']}
    errors = []
    try:
        results['pure'] = pure_probes()
        results['native'] = []
        for allowed in (True, False):
            diagnostics = StringIO()
            with redirect_stderr(diagnostics):
                observed = native_fixture_probe(allowed)
            observed['diagnostic_stderr'] = diagnostics.getvalue()
            results['native'].append(observed)
    except Exception:
        errors.append(traceback.format_exc())
    after = snapshot()
    results['errors'] = errors
    results['engine_unchanged'] = before == after
    results['inventory'] = {k: before[k] for k in ('tracked_count', 'untracked_count')}
    run = 2
    while (OUT / f'probe-results-{run:02}.json').exists():
        run += 1
    for name, value in [(f'snapshot-before-{run:02}.json', before), (f'snapshot-after-{run:02}.json', after), (f'probe-results-{run:02}.json', results)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(run=run, head=results['head'], engine_unchanged=results['engine_unchanged'],
        errors=errors, evidence_file=str(OUT / f'probe-results-{run:02}.json'),
        native=[{k: row[k] for k in ('world_allowed','calls','computed_desires','before_revision',
             'after_revision','committed_mind','effects','action_status','probe_status')}
             for row in results.get('native', [])],
        prior_will=results.get('pure', {}).get('prior_will')), ensure_ascii=False, indent=2))
    if errors or before != after:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
