from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import tempfile
import unittest
import subprocess
import sys
import os
from unittest.mock import patch

from continuity_engine.domain.errors import MemoryValidationError, MemoryIdentityConflictError, MemoryPersistenceError
from continuity_engine.domain.memory import MemoryRecord, MemoryLifecycle, MemoryTemperature, MemoryStatus, DerivedSummaryStatus
from continuity_engine.domain.memory_lifecycle import LifecycleAction, ForgettingPolicy, MemoryLifecycleCommand
from continuity_engine.services.memory_lifecycle_service import MemoryLifecycleService
from continuity_engine.services.memory_service import RepositoryMemoryRetriever
from continuity_engine.domain.memory import MemoryRetrievalRequest
from continuity_engine.testing.p12_memory_fixture import P12MemoryFixture, run_golden
from continuity_engine.testing.models import SandboxOperationError


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='p12-test-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.f=P12MemoryFixture(self.root/'fixture')
        self.memory=self.f.golden.memories[0]

    def snapshot(self):
        return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def current(self):
        return self.f.repository.load_memory(self.f.subject_id,self.memory.memory_id)

    def act(self, action, **kw):
        command=self.f.command(self.memory.memory_id,action,**kw)
        return self.f.service.submit(command)

    def reject(self,command):
        before=self.snapshot()
        with self.assertRaises((MemoryValidationError,MemoryIdentityConflictError)):
            self.f.service.submit(command)
        self.assertEqual(before,self.snapshot(),'rejection must not write, wake or allocate resources')

    def test_legacy_roundtrip_hash_and_no_lifecycle_fields(self):
        body=self.memory.to_dict()
        self.assertNotIn('lifecycle',body)
        self.assertEqual(body,MemoryRecord.from_dict(body).to_dict())
        self.assertEqual(self.memory.canonical_hash(),MemoryRecord.from_dict(body).canonical_hash())

    def test_legacy_archive_temperature_maps_without_write(self):
        body=self.memory.to_dict(); body['temperature']='ARCHIVED'
        memory=MemoryRecord.from_dict(body)
        self.assertEqual(memory.effective_lifecycle,MemoryLifecycle.ARCHIVED)
        self.assertEqual(memory.to_dict(),body)

    def test_lifecycle_is_distinct_from_temperature_and_fact_validity(self):
        temperature=self.current().temperature
        self.act('deactivate')
        memory=self.current()
        self.assertEqual(memory.temperature,temperature)
        self.assertEqual(memory.status,MemoryStatus.ACTIVE)
        self.assertEqual(memory.effective_lifecycle,MemoryLifecycle.INACTIVE)

    def test_legal_sequence_archive_restore_delete(self):
        for action,state in [('deactivate','inactive'),('archive','archived'),('restore','active'),('delete','deleted')]:
            self.assertEqual(self.act(action).lifecycle,state)

    def test_restore_active_rejected_zero_writes(self):
        self.reject(self.f.command(self.memory.memory_id,'restore'))

    def test_repeated_deactivate_new_identity_rejected(self):
        self.act('deactivate')
        self.reject(self.f.command(self.memory.memory_id,'deactivate'))

    def test_current_permission_revocation_denied(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        self.f.permissions.revoke_permission(self.f.subject_id,self.f.permission.permission_id,reason='TEST',source='TEST')
        self.reject(cmd)

    def test_permission_revision_change_denied(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        self.f.permissions.restrict_permission(self.f.subject_id,self.f.permission.permission_id,
            scope=[self.memory.scope],capabilities=['memory.lifecycle.deactivate'],reason='TEST',source='TEST')
        self.reject(cmd)

    def test_permission_scope_denied(self):
        permission=self.f.permissions.create_permission(self.f.subject_id,permission_type='TEST',name='TEST',
            description='TEST',scope=['unrelated:*'],capabilities=['memory.lifecycle.deactivate'],source='TEST',reason='TEST').permission
        cmd=replace(self.f.command(self.memory.memory_id,'deactivate'),permission_id=permission.permission_id)
        self.f.approved[cmd.confirmation_id]=cmd.canonical_hash()
        self.reject(cmd)

    def test_missing_confirmation_denied(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        self.f.approved.clear()
        self.reject(cmd)

    def test_confirmation_binds_entire_command(self):
        self.reject(replace(self.f.command(self.memory.memory_id,'deactivate'),reason='changed'))

    def test_hash_mismatch_rejected(self):
        cmd=replace(self.f.command(self.memory.memory_id,'deactivate'),expected_hash='sha256:'+'0'*64)
        self.f.approved[cmd.confirmation_id]=cmd.canonical_hash()
        self.reject(cmd)

    def test_stale_version_rejected(self):
        cmd=self.f.command(self.memory.memory_id,'archive')
        self.act('downweight',factor=.5)
        self.reject(cmd)

    def test_expiry_boundary_and_future_time_rejected(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        self.f.now=cmd.expires_at
        self.reject(cmd)

    def test_permission_rechecked_after_confirmation_callback(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        original=self.f.service.confirmation_verifier
        def revoke(command):
            self.f.permissions.revoke_permission(self.f.subject_id,self.f.permission.permission_id,reason='TEST',source='TEST')
            return original(command)
        # Only the explicit TEST revocation may write; Memory must remain byte-identical.
        before=self.f.repository._path(self.f.subject_id).read_bytes()
        with patch.object(self.f.service,'confirmation_verifier',side_effect=revoke):
            with self.assertRaises(MemoryValidationError): self.f.service.submit(cmd)
        self.assertEqual(before,self.f.repository._path(self.f.subject_id).read_bytes())

    def test_expiry_rechecked_after_confirmation_callback(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        def expire(command):
            self.f.now=command.expires_at
            return True
        with patch.object(self.f.service,'confirmation_verifier',side_effect=expire): self.reject(cmd)
        self.f.now=cmd.issued_at-timedelta(microseconds=1)
        self.reject(cmd)

    def test_wrong_subject_and_environment_before_repository_read(self):
        cmd=self.f.command(self.memory.memory_id,'deactivate')
        with patch.object(self.f.repository,'apply_lifecycle',side_effect=AssertionError('repository read')):
            self.reject(replace(cmd,subject_id='another-subject'))
            self.reject(replace(cmd,environment='ENGINE'))

    def test_invalid_decay_policy_not_defaulted(self):
        for half_life in (0,-1,float('inf'),float('nan'),True):
            with self.subTest(half_life=half_life),self.assertRaises(MemoryValidationError):
                ForgettingPolicy('TEST',half_life)
        with self.assertRaises(MemoryValidationError): self.f.command(self.memory.memory_id,'decay')

    def test_downweight_affects_actual_retrieval_score(self):
        request=MemoryRetrievalRequest.create(subject_id=self.f.subject_id,query='noodles',requested_at=self.f.now)
        retriever=RepositoryMemoryRetriever(self.f.repository)
        initial=next(x for x in retriever.retrieve(request) if x.memory_id==self.memory.memory_id)
        self.act('downweight',factor=.25)
        current=next(x for x in retriever.retrieve(request) if x.memory_id==self.memory.memory_id)
        self.assertAlmostEqual(current.provider_relevance,initial.provider_relevance*.25,places=6)
        self.assertEqual(self.current().confidence,self.memory.confidence,'weight is not a fact correction')

    def test_elapsed_decay_repeat_same_time_does_not_compound(self):
        self.act('downweight',factor=.5)
        self.f.now+=timedelta(days=7)
        policy=ForgettingPolicy('TEST-seven-days',7*86400)
        self.act('decay',policy=policy)
        self.assertEqual(self.current().effective_weight,.25)
        self.act('decay',policy=policy)
        self.assertEqual(self.current().effective_weight,.25)

    def test_decay_clock_rollback_rejected(self):
        self.act('downweight',factor=.5)
        self.f.now-=timedelta(seconds=1)
        self.reject(self.f.command(self.memory.memory_id,'decay',policy=ForgettingPolicy('TEST',60)))

    def test_zero_weight_excluded_without_becoming_deleted(self):
        self.act('downweight',factor=0)
        self.assertNotIn(self.memory.memory_id,[m.memory_id for m in self.f.repository.list_memories(self.f.subject_id)])
        self.assertEqual(self.current().effective_lifecycle,MemoryLifecycle.ACTIVE)

    def test_inactive_and_archived_exit_ordinary_retrieval(self):
        for action in ('deactivate','archive'):
            self.act(action)
            request=MemoryRetrievalRequest.create(subject_id=self.f.subject_id,query='noodles',requested_at=self.f.now)
            self.assertNotIn(self.memory.memory_id,[m.memory_id for m in RepositoryMemoryRetriever(self.f.repository).retrieve(request)])

    def test_authorized_trace_is_read_only_and_no_body(self):
        self.act('archive'); before=self.snapshot()
        trace=self.f.service.trace(self.memory.memory_id,permission_id=self.f.permission.permission_id,permission_revision=0)
        self.assertNotIn('content',trace)
        self.assertEqual(trace['lifecycle'],'archived')
        self.assertEqual(trace['physical_erasure'],'NOT_READY')
        self.assertTrue(trace['lineage_ids'])
        self.assertEqual(before,self.snapshot())

    def test_strong_history_recall_is_bounded_and_never_restores(self):
        self.act('archive'); before=self.snapshot()
        cue=' '.join(self.memory.content.split()[:2])
        args=dict(permission_id=self.f.permission.permission_id,permission_revision=0,limit=1)
        matches=self.f.service.recall_history(cue=cue,**args)
        self.assertEqual(len(matches),1)
        self.assertFalse(matches[0]['restored'])
        self.assertEqual(self.f.service.recall_history(cue='no-related-cue',**args),())
        self.assertEqual(before,self.snapshot())

    def test_history_recall_requires_current_permission(self):
        self.act('archive')
        self.f.permissions.revoke_permission(self.f.subject_id,self.f.permission.permission_id,reason='TEST',source='TEST')
        before=self.snapshot()
        with self.assertRaises(MemoryValidationError):
            self.f.service.recall_history(cue=' '.join(self.memory.content.split()[:2]),limit=1,
                                         permission_id=self.f.permission.permission_id,permission_revision=0)
        self.assertEqual(before,self.snapshot())

    def test_restore_resets_explicit_use_weight_and_preserves_history(self):
        self.act('downweight',factor=.1); self.act('archive'); self.act('restore')
        self.assertEqual(self.current().effective_weight,1)
        self.assertIn(self.memory.memory_id,[m.memory_id for m in self.f.repository.list_memories(self.f.subject_id)])
        self.assertEqual(len(self.f.repository.memory_history(self.f.subject_id,self.memory.memory_id)),4)

    def test_restore_invalid_source_denied(self):
        self.act('archive'); cmd=self.f.command(self.memory.memory_id,'restore')
        with patch.object(self.f.service,'source_snapshot',return_value=None): self.reject(cmd)

    def test_restore_source_hash_drift_denied(self):
        self.act('archive'); cmd=self.f.command(self.memory.memory_id,'restore')
        with patch.object(self.f.service,'source_snapshot',return_value={'event:changed':'sha256:'+'1'*64}): self.reject(cmd)

    def test_deleted_cannot_restore_after_restart(self):
        self.act('delete'); self.f.reopen()
        self.reject(self.f.command(self.memory.memory_id,'restore'))
        self.assertEqual(self.current().effective_lifecycle,MemoryLifecycle.DELETED)

    def test_delete_replay_returns_tombstone_without_writes(self):
        command=self.f.command(self.memory.memory_id,'delete'); self.f.service.submit(command)
        self.f.reopen(); before=self.snapshot()
        replay=self.f.service.submit(command)
        self.assertTrue(replay.replay); self.assertEqual(replay.lifecycle,'deleted')
        self.assertEqual(before,self.snapshot())

    def test_old_archive_replay_after_delete_never_restores(self):
        command=self.f.command(self.memory.memory_id,'archive'); self.f.service.submit(command)
        self.act('delete'); before=self.snapshot()
        replay=self.f.service.submit(command)
        self.assertEqual(replay.lifecycle,'deleted'); self.assertTrue(replay.replay)
        self.assertEqual(before,self.snapshot())

    def test_production_delete_not_ready_without_read_or_write(self):
        self.f.service.allow_test_delete=False
        with patch.object(self.f.repository,'apply_lifecycle',side_effect=AssertionError('read')):
            self.reject(self.f.command(self.memory.memory_id,'delete'))

    def test_duplicate_command_replays_exactly_without_revision_increment(self):
        command=self.f.command(self.memory.memory_id,'deactivate')
        first=self.f.service.submit(command); before=self.snapshot()
        second=self.f.service.submit(command)
        self.assertTrue(second.replay); self.assertEqual(first.revision,second.revision)
        self.assertEqual(before,self.snapshot())

    def test_command_identity_conflict_no_write(self):
        command=self.f.command(self.memory.memory_id,'deactivate'); self.f.service.submit(command)
        self.reject(replace(command,reason='conflicting duplicate'))

    def test_concurrent_duplicate_single_revision(self):
        command=self.f.command(self.memory.memory_id,'archive')
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(self.f.service.submit,[command,command]))
        self.assertEqual(sorted(r.replay for r in results),[False,True])
        self.assertEqual(self.current().revision,1)

    def test_concurrent_conflicting_commands_one_winner(self):
        commands=[self.f.command(self.memory.memory_id,x) for x in ('deactivate','archive')]
        def run(c):
            try: return self.f.service.submit(c)
            except MemoryValidationError: return 'conflict'
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(run,commands))
        self.assertEqual(results.count('conflict'),1)
        self.assertEqual(self.current().revision,1)

    def test_atomic_replace_failure_preserves_document_and_no_receipt(self):
        command=self.f.command(self.memory.memory_id,'archive'); before=self.snapshot()
        with patch('continuity_engine.storage.json_memory_repository.os.replace',side_effect=OSError('P12 controlled replace failure')):
            with self.assertRaises(OSError): self.f.service.submit(command)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.current().revision,0)
        self.assertFalse(self.f.service.submit(command).replay)

    def test_restart_after_saved_result_replays_once(self):
        command=self.f.command(self.memory.memory_id,'archive'); self.f.service.submit(command)
        self.f.reopen(); before=self.snapshot()
        self.assertTrue(self.f.service.submit(command).replay)
        self.assertEqual(before,self.snapshot())

    def test_actual_fresh_process_recovers_deleted_receipt_without_write(self):
        command=self.f.command(self.memory.memory_id,'delete'); self.f.service.submit(command)
        before=self.snapshot()
        code='''import json,sys,os
from pathlib import Path
from dataclasses import asdict
from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand
from continuity_engine.services.memory_lifecycle_service import MemoryLifecycleService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
c=MemoryLifecycleCommand.from_dict(json.load(sys.stdin))
r=Path(sys.argv[1])
s=MemoryLifecycleService(JsonMemoryRepository(r,environment='TEST'),subject_id=c.subject_id,environment='TEST',
 permissions=PermissionService(JsonPermissionRepository(r)),clock=lambda:c.issued_at,
 source_snapshot=lambda m:None,confirmation_verifier=lambda value:value.canonical_hash()==c.canonical_hash(),allow_test_delete=True)
print(json.dumps({'pid':os.getpid(),'result':asdict(s.submit(c))}))
'''
        completed=subprocess.run([sys.executable,'-c',code,str(self.f.root)],input=json.dumps(command.to_dict()),
            capture_output=True,text=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        result=json.loads(completed.stdout)
        self.assertNotEqual(result['pid'],os.getpid())
        self.assertTrue(result['result']['replay']); self.assertEqual(result['result']['lifecycle'],'deleted')
        self.assertEqual(before,self.snapshot())

    def test_tampered_lifecycle_binding_fails_closed_even_with_document_hash(self):
        self.act('archive')
        path=self.f.repository._path(self.f.subject_id)
        data=json.loads(path.read_text(encoding='utf-8'))
        data['lineage_records'][-1]['command']['input']['reason']='tampered'
        data['document_hash']=self.f.repository._document_hash(data)
        path.write_text(json.dumps(data),encoding='utf-8')
        before=self.snapshot()
        with self.assertRaises(MemoryPersistenceError): self.current()
        self.assertEqual(before,self.snapshot())

    def test_raw_save_cannot_resurrect_deleted(self):
        self.act('delete'); memory=self.current(); body=memory.to_dict()
        body.update(revision=memory.revision+1,memory_version=memory.memory_version+1,lifecycle='active')
        before=self.snapshot()
        with self.assertRaises(MemoryValidationError): self.f.repository.save_memory(MemoryRecord.from_dict(body))
        self.assertEqual(before,self.snapshot())

    def test_summary_invalidated_atomically_then_rebuilt_only_after_restore(self):
        memory=self.f.golden.memories[2]; sid=self.f.golden.relational_summary.summary_id
        self.f.service.submit(self.f.command(memory.memory_id,'archive'))
        self.assertEqual(self.f.repository.load_summary(self.f.subject_id,sid).status,DerivedSummaryStatus.INVALIDATED)
        before=self.snapshot()
        args=dict(summary_id=sid,summary_type='relationship.day',scope='relationship:day2',
                  source_memory_ids=[m.memory_id for m in self.f.golden.memories[2:]],confidence=.9)
        with self.assertRaises(MemoryValidationError): self.f.consolidation.generate_summary(self.f.subject_id,**args)
        self.assertEqual(before,self.snapshot())
        self.f.service.submit(self.f.command(memory.memory_id,'restore'))
        summary=self.f.consolidation.generate_summary(self.f.subject_id,**args)
        self.assertEqual(summary.status,DerivedSummaryStatus.ACTIVE)
        self.assertGreater(summary.summary_version,1)

    def test_archive_delete_keep_event_and_subject_state_bytes(self):
        before={p:p.read_bytes() for p in self.f.root.glob('*.json')}
        self.act('archive'); self.act('delete')
        self.assertEqual(before,{p:p.read_bytes() for p in self.f.root.glob('*.json')})
        self.assertFalse(list(self.f.root.rglob('*receipt*')))
        self.assertFalse((self.f.root/'resources').exists())
        self.assertFalse((self.f.root/'awakening').exists())

    def test_seven_day_golden_actual_recall_difference_and_delete_replay(self):
        result=run_golden(self.root/'golden')
        self.assertEqual(result['initialRecall']-result['archivedRecall'],1)
        self.assertEqual(result['weightAfterDownweightAndDecay'],.25)
        self.assertEqual(result['finalLifecycle'],'deleted')


class FixtureIsolationTests(unittest.TestCase):
    def test_protected_names_case_variants_self_and_children_zero_write(self):
        with tempfile.TemporaryDirectory(prefix='p12-path-') as temp:
            root=Path(temp)
            for name in ('.continuity-data','.CONTINUITY-DATA','.CoNtInUiTy-DaTa','.assistant-data','.ASSISTANT-DATA'):
                protected=root/name; protected.mkdir(exist_ok=True)
                (protected/'canary').write_bytes(b'preserve')
                for target in (protected,protected/'child'):
                    with self.subTest(name=name,target=str(target)):
                        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                        with self.assertRaises(SandboxOperationError): P12MemoryFixture(target,formal_data_roots=(protected,))
                        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
                        self.assertFalse((protected/'child').exists())

    def test_repository_overlap_in_temp_rejected_before_writes(self):
        with tempfile.TemporaryDirectory(prefix='p12-path-') as temp:
            root=Path(temp); (root/'.git').mkdir()
            for target in (root,root/'child'):
                with self.assertRaises(SandboxOperationError): P12MemoryFixture(target)
            self.assertEqual(list(root.iterdir()),[root/'.git'])

    def test_link_components_rejected_without_writes(self):
        with tempfile.TemporaryDirectory(prefix='p12-path-') as temp:
            root=Path(temp); target=root/'target'; target.mkdir(); link=root/'link'
            # Deterministic reparse detection boundary, no privilege-dependent SKIP.
            with patch('continuity_engine.testing.p08_action_fixture.assert_no_link_components',
                       side_effect=SandboxOperationError('SANDBOX_LINK_FORBIDDEN','controlled reparse point')):
                with self.assertRaises(SandboxOperationError): P12MemoryFixture(link)
            self.assertEqual(list(root.iterdir()),[target])


if __name__=='__main__': unittest.main()
