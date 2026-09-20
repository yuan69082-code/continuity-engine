"""Bounded extra normal-chain observation, not added to the formal suite count."""
import contextlib,hashlib,json,sys,tempfile,time,traceback
from pathlib import Path
from datetime import datetime,timezone,timedelta
DIRECTORY=Path(__file__).resolve().parent
sys.path.insert(0,str(DIRECTORY))
from run import ROOT,source_hashes
from continuity_engine.testing.p18_runtime_fixture import P18Fixture
from continuity_engine.domain.persistent_runtime import RuntimePolicy
from continuity_engine.domain.dynamic_mind import MindState

label=sys.argv[1]
assert all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label)
record={'command':[sys.executable,*sys.argv],'status':'STARTED','sourceBefore':source_hashes(),
        'startedAt':datetime.now(timezone.utc).isoformat(),'kind':'extra bounded scenario, not formal test count',
        'logicalStepSeconds':21600,'testClockJumpAllowanceSeconds':86400,'rows':[]}
path=DIRECTORY/(label+'.json')
with path.open('x',encoding='utf8') as out:json.dump(record,out,indent=2)
start=time.perf_counter();code=1;fixture=None;root=None
with (DIRECTORY/(label+'.stdout.log')).open('x',encoding='utf8') as stdout, (DIRECTORY/(label+'.stderr.log')).open('x',encoding='utf8') as stderr:
 with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
  try:
   root=Path(tempfile.mkdtemp(prefix='pg-'));record['isolatedRoot']=str(root)
   fixture=P18Fixture(root,policy=RuntimePolicy(clock_jump_seconds=86400))
   initial=fixture.state.revision
   with fixture.host.running():
    try:
     for step in range(1,16):
      fixture.advance(21600)
      previous=fixture.state
      mind=MindState.from_dict(previous.intentions.dynamic_mind) if previous.intentions.dynamic_mind else None
      projected=fixture.core.mind.dynamics.advance(mind,at=fixture.clock.now()) if mind else None
      delta=max(abs(projected.state.drives[k]-mind.drives[k]) for k in mind.drives) if mind else None
      calls=fixture.provider.calls
      fixture.host.tick();fixture.advance(60);fixture.host.tick()
      current=fixture.state
      row={'step':step,'at':fixture.clock.now().isoformat(),'driveDeltaBeforeTick':delta,
           'revisionBefore':previous.revision,'revisionAfter':current.revision,
           'callsBefore':calls,'callsAfter':fixture.provider.calls,
           'drives':current.intentions.dynamic_mind['drives'] if current.intentions.dynamic_mind else None,
           'effects':fixture.fake.effect_count,'credits':fixture.fake.credits,
           'activity':fixture.host.query()['activity']}
      record['rows'].append(row);print(json.dumps(row))
      assert current.revision>previous.revision
      assert current.revision-initial==fixture.provider.calls
      assert (fixture.fake.execute_calls,fixture.fake.effect_count,fixture.fake.credits)==(0,0,0)
      assert fixture.provider.inputs[-1].external_facts==()
     plateau=[r for r in record['rows'] if r['driveDeltaBeforeTick'] is not None and r['driveDeltaBeforeTick']<fixture.work.policy.need_delta]
     assert len(plateau)>=3
     record['belowDeltaGateAdvancingRounds']=[r['step'] for r in plateau]
     record['defaultNeedDelta']=fixture.work.policy.need_delta
     record['finalResources']=fixture.host.query()['resources']
    except BaseException as exc:
     record['failureBeforeStop']={'type':type(exc).__name__,'host':fixture.host.query(),
       'revision':fixture.state.revision,'providerCalls':fixture.provider.calls,
       'effects':fixture.fake.effect_count,'credits':fixture.fake.credits}
     raise
    finally:
     fixture.control('STOP');record['stopStatus']=fixture.host.query()
   record['status']='FINISHED';record['scenarioPassed']=True;code=0
  except BaseException as exc:
   traceback.print_exc();record['status']='FAILED';record['scenarioPassed']=False;record['errorType']=type(exc).__name__
  finally:
   if code==0 and root is not None:
    import shutil
    # Only this freshly created, isolated fixture root; retain it on failure.
    assert root.parent==Path(tempfile.gettempdir()) and root.name.startswith('pg-')
    shutil.rmtree(root);record['ownFixtureRemoved']=True
   else:record['ownFixtureRemoved']=False
   record.update(exitCode=code,seconds=round(time.perf_counter()-start,3),
     finishedAt=datetime.now(timezone.utc).isoformat(),sourceAfter=source_hashes())
   path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in record.items() if k not in ('sourceBefore','sourceAfter','rows','stopStatus')},ensure_ascii=False))
raise SystemExit(code)
