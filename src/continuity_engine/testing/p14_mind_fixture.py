"""Isolated P14 cognition on the normal Engine C1 path; no production adapters."""
from pathlib import Path
from .p08_action_fixture import _validate_fixture_root
from .p13_expression_fixture import P13Fixture


class P14Fixture(P13Fixture):
    def __init__(self, root: Path, *, mind_enabled=True, **options):
        _validate_fixture_root(root)
        super().__init__(root, dynamic_mind=mind_enabled, **options)

    def opportunity(self, session_id):
        from continuity_engine.services.wake_perception_thinking_action_service import WakePerceptionThinkingActionService
        original = self.app.adapter._service
        service = WakePerceptionThinkingActionService(original._awakening, original._perception,
            original._thinking, original._action, original._subject_states,
            available_permissions=original._available_permissions,
            resource_limits=original._resource_limits, clock=self.runtime.clock.now, continuity_core=self.core)
        return service.wake_manual(self.app.binding.cycle_id, detail='Authorized native P14 computation opportunity.',
                                   session_id=session_id)

    def owner_projection(self):
        from continuity_engine.domain.errors import PermissionNotFoundError
        from continuity_engine.services.permission_service import PermissionService
        from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
        from continuity_engine.services.mind_ports import VerifiedMindReader
        from continuity_engine.services.mind_projection_service import MindProjectionService
        self.view_permissions = PermissionService(JsonPermissionRepository(self.runtime.data_root),
                                                  clock=self.runtime.clock.now)
        subject = self.state.subject_id
        try:
            self.view_permissions.get_permission(subject, 'p14-test-owner-read')
        except PermissionNotFoundError:
            self.view_permissions.create_permission(subject, permission_id='p14-test-owner-read',
                permission_type='experimental-owner-read', name='Explicit TEST Owner mind visibility',
                description='Synthetic authenticated Owner projection; no production authentication claim.',
                scope=['mind:TEST:' + subject + ':test-owner'],
                capabilities=['mind:read:detailed', 'mind:read:summary', 'mind:read:history'],
                source='P14-explicit-test-owner', reason='Authorized isolated experiment fixture.')
        class TestAuthenticatedHost:
            def resolve(self, handle):
                # A host-established session table, not a caller-provided owner flag.
                return {'test-owner-session': VerifiedMindReader('test-owner', subject, 'TEST'),
                        'test-other-session': VerifiedMindReader('other', subject, 'TEST')}.get(handle)
        return MindProjectionService(self.runtime.subject_states, self.view_permissions, TestAuthenticatedHost(),
            subject_id=subject, environment='TEST', owner_principal_id='test-owner')

    def revoke_owner_view(self):
        self.view_permissions.revoke_permission(self.state.subject_id, 'p14-test-owner-read',
            source='P14-explicit-test-owner', reason='Explicit TEST revocation of display access only.')

    def affective_event(self, event_id, *, object_id, observation, impact=0.7):
        import json
        from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, StateSection
        now = self.runtime.clock.now()
        event = Event.create(event_id=event_id, occurred_at=now, observed_at=now, recorded_at=now,
            source='p14.synthetic-experience', source_kind=EventSourceKind.TEST,
            event_type='experienced_interaction', classification=EventClassification.INTERACTION,
            impact_scope=[StateSection.RELATIONSHIP, StateSection.CONTINUITY], mutations=[],
            reason='Synthetic interpersonal experience; no state mutation or emotional conclusion.',
            content=json.dumps({'experienced': {
            'object': object_id, 'observation': observation,
            'expectation': 'mutual respect',
            'consequence': observation.replace('_', ' '),
            'impact': impact}}, ensure_ascii=False))
        return self.runtime.subject_states.apply_event(self.state.subject_id, event)


def _golden_worker(root, sandbox_id, segment):
    from datetime import timedelta
    from .sandbox import P01SandboxManager
    manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    fixture=P14Fixture(root,manager=manager,runtime=manager.open_runtime(sandbox_id))
    before=fixture.state.revision
    original_times=[(u.event.event_id,u.event.occurred_at.isoformat())
                    for u in fixture.runtime.subject_states.get_update_history(fixture.state.subject_id)]
    for i in range(2):
        fixture.runtime.clock.advance(timedelta(hours=1))
        value=fixture.opportunity('golden-'+str(segment*2+i))
        if value.state_update is None:
            raise AssertionError('authorized golden opportunity did not commit through Evolution')
    state=fixture.state.to_dict()
    fixture.opportunity('golden-'+str(segment*2+1))
    if fixture.state.to_dict()!=state:
        raise AssertionError('duplicate native opportunity repeated a state effect')
    after_times={u.event.event_id:u.event.occurred_at.isoformat()
                 for u in fixture.runtime.subject_states.get_update_history(fixture.state.subject_id)}
    if any(after_times[k]!=v for k,v in original_times):
        raise AssertionError('objective event time was changed')
    mind=fixture.state.intentions.dynamic_mind
    return {'subjectId':fixture.state.subject_id,'revisionBefore':before,'revisionAfter':fixture.state.revision,
            'subjectiveSeconds':mind['subjective_seconds'],'providerCalls':fixture.provider.calls,
            'adapterEffects':fixture.adapter.effect_count,'adapterCredits':fixture.adapter.credits,
            'desires':len(mind['desires']),'thoughts':len(mind['thoughts']),
            'retainedTrajectoryPoints':sum(len(d['trajectory']) for d in mind['desires']),
            'stateBytes':len(__import__('json').dumps(mind).encode('utf8')),
            'objectiveEventTimesUnchanged':True,'noDuplicateNativeCommit':True}


def run_golden(root):
    """Six authorized opportunities over six logical hours and three processes.

    No real-time sleeping, background runtime, new observation, or external action.
    Child failures are printed before isolated data cleanup by the caller.
    """
    import json,os,subprocess,sys
    _validate_fixture_root(root)
    f=P14Fixture(root)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1',
         'PYTHONPATH':str(Path(__file__).resolve().parents[2])}
    segments=[]
    for segment in range(3):
        command=[sys.executable,'-m','continuity_engine.testing.p14_mind_fixture',
                 '--root',str(root),'--worker',str(segment),'--sandbox-id',f.runtime.descriptor.sandbox_id]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf8',env=env)
        if result.returncode:
            print(json.dumps({'stage':'golden-child','command':command,'exitCode':result.returncode}),file=sys.stderr)
            print(result.stdout,file=sys.stdout);print(result.stderr,file=sys.stderr)
            raise RuntimeError('P14 Golden child failed; original output preserved above')
        segments.append(json.loads(result.stdout))
    if any(s['revisionAfter']-s['revisionBefore']!=2 for s in segments):
        raise AssertionError('Golden revision count mismatch')
    return {'fixture':'p14-mind-golden-v1','rounds':6,'logicalSeconds':21600,
            'processRestarts':2,'subjectIds':[s['subjectId'] for s in segments],
            'subjectiveSeconds':segments[-1]['subjectiveSeconds'],
            'noDuplicateNativeCommit':all(s['noDuplicateNativeCommit'] for s in segments),
            'segments':segments,'productionRuntime':'NOT_READY','externalCalls':0}


def main():
    import argparse,json,tempfile
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--worker',type=int,choices=range(3))
    parser.add_argument('--sandbox-id')
    args=parser.parse_args()
    if args.worker is not None:
        if args.root is None or not args.sandbox_id:parser.error('worker requires root and sandbox identity')
        _validate_fixture_root(args.root)
        result=_golden_worker(args.root,args.sandbox_id,args.worker)
    elif args.root is not None:
        result=run_golden(args.root)
    else:
        with tempfile.TemporaryDirectory(prefix='p14-golden-') as temp:
            result=run_golden(Path(temp))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
