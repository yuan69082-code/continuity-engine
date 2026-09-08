"""Disposable P15 host/confirmation fixture; no production authorization defaults."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.subject_lifecycle import LifecycleCommand, LifecycleError, LifecyclePolicy, lifecycle_status
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.subject_lifecycle_service import SubjectLifecycleService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from .p08_action_fixture import _validate_fixture_root


class TestLifecycleAuthority:
    def __init__(self):
        self.credentials = {}
        self.revoked = False

    def confirm(self, command, principal, at):
        token = digest([command.to_dict(), principal, 'synthetic-confirmation'])
        self.credentials[token] = (command.to_dict(), principal, at + timedelta(minutes=5))
        return token

    def identify(self, command, credential):
        entry = self.credentials.get(credential)
        if entry is None or entry[0] != command.to_dict():
            raise LifecycleError('SUBJECT_CREDENTIAL_BINDING_INVALID')
        return entry[1]

    def authorize(self, command, credential, *, at):
        principal = self.identify(command, credential)
        if self.revoked or at >= self.credentials[credential][2]:
            raise LifecycleError('SUBJECT_CURRENT_PERMISSION_DENIED')
        return principal


class P15Fixture:
    def __init__(self, root, *, subject_id='p15-subject'):
        self.root = _validate_fixture_root(Path(root))
        self.subject_id, self.now = subject_id, datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.authority, self.policy, self.commands = TestLifecycleAuthority(), LifecyclePolicy(), {}
        self.reopen()

    def clock(self): return self.now

    def reopen(self):
        self.states = SubjectStateService(JsonSubjectStateRepository(self.root / 'states'), clock=self.clock)
        self.grant = PermissionGrant('subject.lifecycle', self.subject_id,
            datetime(2020, 1, 1, tzinfo=timezone.utc), scopes=[self.subject_id])
        # assess_local_action is read-only and never accesses its Action repository.
        self.gate = ActionService(InMemoryPermissionProvider([self.grant]), None)
        self.lifecycle = SubjectLifecycleService(self.states, environment='TEST', authority=self.authority,
            action_gate=self.gate, clock=self.clock, policy=self.policy)

    def state(self): return self.states.load(self.subject_id)
    def status(self): return lifecycle_status(self.state())

    def prepare(self, operation, *, identity=None, initiator='OWNER'):
        identity = identity or 'command-' + str(len(self.commands))
        exists = self.states._repository.exists(self.subject_id)
        command = LifecycleCommand(identity, self.subject_id, 'TEST', self.state().revision if exists else 0,
                                   self.clock(), 'Explicit synthetic lifecycle test', operation, initiator)
        token = self.authority.confirm(command, 'owner' if initiator == 'OWNER' else self.subject_id, self.clock())
        self.commands[identity] = command, token
        return command, token

    def command(self, operation, **kwargs):
        return self.lifecycle.submit(*self.prepare(operation, **kwargs))

    def replay(self, identity): return self.lifecycle.submit(*self.commands[identity])

    def import_observation(self,source,event,*,confirmed):
        from continuity_engine.domain.subject_lifecycle import TestMigrationCommand
        command=TestMigrationCommand('import:'+event.event_id,self.subject_id,source.subject_id,event.event_id,
            event.canonical_hash(),source.state().revision,self.state().revision)
        token=self.authority.confirm(command,'owner',self.clock()) if confirmed else 'unconfirmed'
        source_token=source.authority.confirm(command,'owner',source.clock()) if confirmed else 'unconfirmed'
        return self.lifecycle.import_test_observation(command,token,source_states=source.states,
            source_authority=source.authority,source_credential=source_token,allowed_types=('PUBLIC_OBSERVATION',))

    def inventory(self):
        return {p.relative_to(self.root).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}


from .p14_mind_fixture import P14Fixture


class TestSubjectSelection:
    """Host pointer only; switching/ending a session never changes a Subject."""
    def __init__(self,root,subjects,*,owner):
        self.root=_validate_fixture_root(root)
        self.subjects,self.owner=subjects,owner
        self.path=self.root/'test-host-selection.json'

    def select(self,*,subject_id,environment,principal_id):
        from .persistence import atomic_write_json
        if principal_id!=self.owner or environment!='TEST' or subject_id not in self.subjects:
            raise LifecycleError('SUBJECT_HOST_BINDING_DENIED')
        state=self.subjects[subject_id].require_active(subject_id,environment)
        if state.temporal.subject_lifecycle['owner_principal_id']!=principal_id:
            raise LifecycleError('SUBJECT_HOST_OWNER_MISMATCH')
        atomic_write_json(self.path,{'version':'p15-test-host-selection-v1','subject_id':subject_id,'environment':'TEST'})

    def unbind(self,*,principal_id):
        from .persistence import atomic_write_json
        if principal_id!=self.owner:raise LifecycleError('SUBJECT_HOST_BINDING_DENIED')
        atomic_write_json(self.path,{'version':'p15-test-host-selection-v1','subject_id':None,'environment':'TEST'})

    def selected(self):
        from .persistence import read_json
        if not self.path.exists():return None
        data=read_json(self.path)
        if (set(data)!={'version','subject_id','environment'} or data['environment']!='TEST'
                or data['version']!='p15-test-host-selection-v1'
                or data['subject_id'] is not None and data['subject_id'] not in self.subjects):
            raise LifecycleError('SUBJECT_HOST_SELECTION_INVALID')
        return data['subject_id']


class P15GrowthFixture(P14Fixture):
    def __init__(self,root,**options):
        self.growth_authority=TestLifecycleAuthority()
        self.growth_commands={}
        super().__init__(root,subject_growth=True,**options)

    def reopen(self):
        app=super().reopen()
        self.growth=self.core.growth
        self.growth.authority=self.growth_authority
        original=self.provider.think
        def think(perception,budget):
            from dataclasses import replace
            import json
            result=original(perception,budget)
            context=perception.continuity_context
            # TEST provider interpretation consumes actual authorized Context;
            # it cannot write a trait, relationship, narrative or final state.
            if context is not None:
                for fragment in context.composition.snapshot.fragments:
                    if fragment.source_id=='engine.subject-state' and fragment.stable_source_id.endswith(':identity'):
                        if 'consider evidence' in json.loads(fragment.content).get('stable_traits',[]):
                            return replace(result,request_more_memory=True,additional_memory_query='independent evidence',
                                rationale_summary='The current authorized trait motivates checking evidence before proceeding.')
            return result
        self.provider.think=think
        return app

    def experiences(self,roots=('one','two','three'),confidences=(0.8,0.8,0.8)):
        from continuity_engine.domain.events import Event,EventClassification,EventSourceKind,StateSection
        ids=[]
        for root,confidence in zip(roots,confidences):
            found=next((e for e in self.growth.learning.list_learning_events(self.state.subject_id)
                        if e.source_event_id==root),None)
            if found is None:
                self.runtime.clock.advance(timedelta(seconds=1))
                now=self.runtime.clock.now()
                event=Event.create(event_id=root,occurred_at=now,observed_at=now,recorded_at=now,
                    source='p15.synthetic-experience',source_kind=EventSourceKind.TEST,event_type='growth_experience',
                    classification=EventClassification.INTERACTION,content='continuity: evidence was considered '+root,
                    impact_scope=[StateSection.IDENTITY],mutations=[],reason='Explicit synthetic experience',
                    metadata={'learning_observation':'Evidence considered in a separate experience',
                        'learning_hypothesis':'Considering evidence is a useful stable approach',
                        'learning_field_path':'identity.stable_traits','learning_value':'consider evidence',
                        'learning_confidence':confidence})
                self.runtime.subject_states.apply_event(self.state.subject_id,event)
                self.submit(self.request())
                found=next((e for e in self.growth.learning.list_learning_events(self.state.subject_id)
                            if e.source_event_id==root),None)
                if found is None:raise AssertionError('normal C1 did not consume learning experience '+root)
            ids.append(found.learning_id)
        return ids

    def solidify(self,learning_id,identity=None):
        return self._growth_command('SOLIDIFY',learning_id,None,identity)

    def rollback(self,learning_id,trait_id,identity=None):
        return self._growth_command('ROLLBACK',learning_id,trait_id,identity)

    def _growth_command(self,operation,learning_id,trait_id,identity):
        from continuity_engine.domain.subject_growth import GrowthCommand
        command=GrowthCommand(identity or 'growth-'+str(len(self.growth_commands)),self.state.subject_id,
            'TEST',self.state.revision,learning_id,operation,'Explicit synthetic growth confirmation',trait_id)
        token=self.growth_authority.confirm(command,'owner',self.runtime.clock.now())
        self.growth_commands[command.command_id]=(command,token)
        return self.growth.submit(command,token)

    def replay(self,identity):return self.growth.submit(*self.growth_commands[identity])

    def inventory(self):
        return {p.relative_to(self.root).as_posix():sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}


def _p15_worker(root,sandbox_id,segment):
    import os
    from .sandbox import P01SandboxManager
    manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    f=P15GrowthFixture(root,manager=manager,runtime=manager.open_runtime(sandbox_id))
    before=f.state.revision
    old_will={item['desire_id'] for item in (f.state.intentions.dynamic_mind or {}).get('will',[])}
    f.runtime.clock.advance(timedelta(hours=1))
    identity='p15-golden-'+str(segment)
    f.opportunity(identity)
    current=f.state.to_dict()
    f.opportunity(identity)
    if current!=f.state.to_dict():raise AssertionError('native replay repeated subject mutation')
    mind=f.state.intentions.dynamic_mind
    return {'process_id':os.getpid(),'revision_before':before,'revision_after':f.state.revision,
            'retained_trait':'consider evidence' in f.state.identity.stable_traits,
            'retained_will_ids':old_will<={item['desire_id'] for item in mind['will']},
            'duplicate_revision_delta':f.state.revision-current['revision'],
            'provider_calls':f.provider.calls,'thoughts':len(mind['thoughts']),
            'subject_id':f.state.subject_id,'objective_time':f.runtime.clock.now().isoformat()}


def run_p15_golden(root):
    import os,sys,json,subprocess,time
    root=_validate_fixture_root(Path(root))
    f=P15GrowthFixture(root)
    ids=f.experiences();f.growth.validate(ids[0],ids[1:]);f.solidify(ids[0])
    segments=[]
    env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPATH':str(Path(__file__).resolve().parents[2])}
    for segment in range(2):
        command=[sys.executable,'-m','continuity_engine.testing.p15_subject_fixture','--root',str(root),
                 '--worker',str(segment),'--sandbox-id',f.runtime.descriptor.sandbox_id]
        started=time.perf_counter()
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=env)
        if result.returncode:
            print(json.dumps({'stage':'p15-golden-child','command':command,'exitCode':result.returncode,
                'seconds':time.perf_counter()-started}),file=sys.stderr)
            print(result.stdout);print(result.stderr,file=sys.stderr)
            raise RuntimeError('P15 Golden child failed; original evidence emitted outside cleanup root')
        entry=json.loads(result.stdout);entry['command']=command;entry['seconds']=time.perf_counter()-started
        segments.append(entry)
    return {'fixture':'p15-golden-v1','process_ids':[s['process_id'] for s in segments],
            'retained_trait':all(s['retained_trait'] for s in segments),
            'retained_will_ids':all(s['retained_will_ids'] for s in segments),
            'duplicate_revision_delta':sum(s['duplicate_revision_delta'] for s in segments),
            'logical_seconds':7203,'event_rounds':3,'native_opportunities':2,'restarts':2,
            'segments':segments,'production_adapter_calls':0,'production_lifecycle_policy':'NOT_READY'}


def main():
    import argparse,json,tempfile
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--worker',type=int,choices=(0,1))
    parser.add_argument('--sandbox-id')
    args=parser.parse_args()
    if args.worker is not None:
        if args.root is None or not args.sandbox_id:parser.error('worker requires root and sandbox-id')
        _validate_fixture_root(args.root)
        result=_p15_worker(args.root,args.sandbox_id,args.worker)
    elif args.root is not None:result=run_p15_golden(args.root)
    else:
        with tempfile.TemporaryDirectory(prefix='g15-') as folder:result=run_p15_golden(Path(folder))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
