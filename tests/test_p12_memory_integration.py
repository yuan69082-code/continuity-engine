"""P12 regressions against actual P04/P05/P06/Learning interfaces."""
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace
from datetime import timedelta
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import MemoryValidationError, LearningValidationError
from continuity_engine.domain.memory import MemoryRecord, MemoryLineageType
from continuity_engine.domain.events import StateMutation, ChangeOperation
from continuity_engine.services.learning_service import LearningService
from continuity_engine.services.memory_consolidation_service import MemoryConsolidationService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.json_learning_repository import JsonLearningRepository
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.testing.p04_memory_fixture import run_p04_golden_scenario
from continuity_engine.testing.p12_memory_fixture import P12MemoryFixture
from continuity_engine.domain.context_routing import ContextCandidateReference, ContextPartition
from continuity_engine.domain.errors import ContextCompositionSourceError
from continuity_engine.services.context_material_resolvers import MemoryMaterialResolver, DerivedSummaryMaterialResolver
from continuity_engine.services.context_router_service import MemoryContextSource, DerivedSummaryContextSource, ContextSourceQuery, TimelineContextSource
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand, LifecycleAction
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
from continuity_engine.domain.integration_results import FirstRoundSuccessResult


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class ExistingUseRegressions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.golden = run_p04_golden_scenario(self.root)
        self.subject = self.golden.p03.subject_state.subject_id
        self.repo = JsonMemoryRepository(self.root, environment='TEST')
        self.service = MemoryConsolidationService(self.repo, clock=lambda: NOW)

    def revoke(self, memory, signal=MemoryLineageType.REVOCATION):
        self.service.propagate_signal(self.subject, lineage_id='p12-signal',
            target_memory_id=memory.memory_id, signal=signal,
            source_event_id='p12-signal-event',
            root_evidence_ids=[*memory.root_evidence_ids, 'event:p12-signal-event'])

    def test_deleted_consolidation_replay_cannot_return_active_material(self):
        memory = self.golden.memories[0]
        operation = self.repo.load_consolidation_operation(self.subject, memory.consolidation_id)
        candidate = MemoryRecord.from_dict(operation.canonical_input)
        self.revoke(memory, MemoryLineageType.DELETION)
        before = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        restarted = MemoryConsolidationService(JsonMemoryRepository(self.root, environment='TEST'), clock=lambda: NOW)
        with self.assertRaises(MemoryValidationError):
            restarted.consolidate(candidate)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.json')})

    def test_pending_learning_rechecks_revoked_memory_support(self):
        learning = LearningService(JsonLearningRepository(self.root), clock=lambda: NOW)
        candidates = []
        for memory in self.golden.memories[:3]:
            candidates.append(learning.create_candidate(self.subject,
                source_event_id=None, source_memory_id=memory.memory_id,
                root_evidence_ids=memory.root_evidence_ids, related_state_revision=0,
                observation='synthetic observation', hypothesis='synthetic hypothesis',
                proposed_change=StateMutation('identity.expression_preferences', ChangeOperation.APPEND,
                    'P12 synthetic preference', 'explicit test'), confidence=.8,
                original_experience={'memory_id':memory.memory_id, 'metadata':{
                    'memory_environment':'TEST', 'memory_revision':memory.revision,
                    'memory_hash':memory.canonical_hash()}}, reason='TEST', source='TEST').learning_event)
        learning.validate_learning(self.subject, candidates[0].learning_id,
            [c.learning_id for c in candidates[1:]], reason='TEST', source='TEST')
        self.revoke(self.golden.memories[1])
        state = SubjectStateService(JsonSubjectStateRepository(self.root/'states'), clock=lambda: NOW).create(self.subject)
        before = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        with self.assertRaises(LearningValidationError):
            learning.solidify_learning(self.subject, candidates[0].learning_id, state,
                trait_name='TEST', trait_description='TEST', reason='TEST', source='TEST',
                confirmed=True, expected_revision=0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*.json')})


class ContextAndLineageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='p12-integration-'); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.f=P12MemoryFixture(self.root/'f')
        self.memory=self.f.golden.memories[2]

    def reference(self,memory):
        return ContextCandidateReference('engine.memory',ContextPartition.MEMORY,memory.memory_id,
            memory.subject_id,memory.environment,f'revision:{memory.revision}',memory.canonical_hash(),
            'MEMORY_RECORD',1,.9,memory.occurred_at,('TEST',))

    def query(self):
        return ContextSourceQuery('p12-query',self.f.subject_id,'TEST',0,self.f.now,('relationship',),('relationship',),10)

    def test_router_excludes_archived_and_revalidates_old_candidate(self):
        source=MemoryContextSource(self.f.repository,environment='TEST'); query=self.query()
        batch=source.retrieve(query); candidate=next(c for c in batch.candidates if c.stable_id==self.memory.memory_id)
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.assertNotIn(self.memory.memory_id,[c.stable_id for c in source.retrieve(query).candidates])
        self.assertFalse(source.revalidate(query,candidate,batch.source_version).valid)

    def test_router_weight_changes_actual_candidate_relevance(self):
        source=MemoryContextSource(self.f.repository,environment='TEST'); query=self.query()
        before=next(c for c in source.retrieve(query).candidates if c.stable_id==self.memory.memory_id)
        self.f.service.submit(self.f.command(self.memory.memory_id,'downweight',factor=.2))
        after=next(c for c in source.retrieve(query).candidates if c.stable_id==self.memory.memory_id)
        self.assertAlmostEqual(after.relevance,before.relevance*.2)
        self.assertAlmostEqual(after.importance,before.importance*.2)

    def test_normal_timeline_material_honors_weight_without_rewriting_event(self):
        source=TimelineContextSource(self.f.timeline,environment='TEST',memory_repository=self.f.repository)
        query=replace(self.query(),purpose=('temporal',),query_terms=('argument',))
        event_id=self.memory.source_event_ids[0]
        original=self.f.timeline.load_entry(self.f.subject_id,event_id).event.canonical_hash()
        batch=source.retrieve(query); before=next(c for c in batch.candidates if c.stable_id==event_id)
        self.f.service.submit(self.f.command(self.memory.memory_id,'downweight',factor=.2))
        after=next(c for c in source.retrieve(query).candidates if c.stable_id==event_id)
        self.assertAlmostEqual(after.relevance,before.relevance*.2)
        self.assertFalse(source.revalidate(query,before,batch.source_version).valid)
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.assertNotIn(event_id,[c.stable_id for c in source.retrieve(query).candidates])
        self.assertEqual(original,self.f.timeline.load_entry(self.f.subject_id,event_id).event.canonical_hash())

    def test_composer_exact_old_reference_blocked_after_archive(self):
        resolver=MemoryMaterialResolver(self.f.repository,environment='TEST'); reference=self.reference(self.memory)
        self.assertEqual(resolver.resolve(reference).content,self.memory.content)
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        with self.assertRaises(ContextCompositionSourceError): resolver.resolve(reference)

    def test_old_reference_stays_stale_after_restore(self):
        resolver=MemoryMaterialResolver(self.f.repository,environment='TEST'); reference=self.reference(self.memory)
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.f.service.submit(self.f.command(self.memory.memory_id,'restore'))
        with self.assertRaises(ContextCompositionSourceError): resolver.resolve(reference)
        current=self.f.repository.load_memory(self.f.subject_id,self.memory.memory_id)
        self.assertEqual(resolver.resolve(self.reference(current)).content,current.content)

    def test_old_summary_reference_rejected_and_rebuild_keeps_downweight(self):
        summary=self.f.golden.relational_summary
        reference=ContextCandidateReference('engine.derived-summary',ContextPartition.DERIVED_SUMMARY,summary.summary_id,
            summary.subject_id,summary.environment,f'version:{summary.summary_version}',summary.canonical_hash(),
            'DERIVED_MEMORY_VIEW',1,.9,summary.generated_at,('TEST',))
        resolver=DerivedSummaryMaterialResolver(self.f.repository,environment='TEST')
        before=resolver.resolve(reference).confidence
        self.f.service.submit(self.f.command(self.memory.memory_id,'downweight',factor=.2))
        with self.assertRaises(ContextCompositionSourceError): resolver.resolve(reference)
        rebuilt=self.f.consolidation.generate_summary(self.f.subject_id,summary_id=summary.summary_id,
            summary_type=summary.summary_type,scope=summary.scope,source_memory_ids=summary.source_memory_ids,confidence=summary.confidence)
        reference=replace(reference,version=f'version:{rebuilt.summary_version}',content_hash=rebuilt.canonical_hash())
        self.assertAlmostEqual(resolver.resolve(reference).confidence,before*.2)
        source=DerivedSummaryContextSource(self.f.repository,environment='TEST')
        candidate=next(c for c in source.retrieve(self.query()).candidates if c.stable_id==rebuilt.summary_id)
        self.assertLessEqual(candidate.relevance,.2)

    def child(self):
        body=self.memory.to_dict()
        body.update(memory_id='p12-child',consolidation_id='p12-child-operation',consolidation_input_hash=None,
                    scope='p12:child',source_event_ids=[],source_memory_ids=[self.memory.memory_id],content='synthetic child memory')
        return self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory

    def test_transitive_child_and_summary_disabled_by_parent(self):
        child=self.child()
        summary=self.f.consolidation.generate_summary(self.f.subject_id,summary_id='p12-child-summary',
            summary_type='child.test',scope='child',source_memory_ids=[child.memory_id],confidence=.8)
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.assertFalse(self.f.repository.current_usable(self.f.subject_id,child.memory_id))
        self.assertNotIn(child.memory_id,[m.memory_id for m in self.f.repository.list_memories(self.f.subject_id)])
        self.assertNotEqual(self.f.repository.load_summary(self.f.subject_id,summary.summary_id).status.value,'ACTIVE')

    def test_parent_restore_cannot_reactivate_old_child_version(self):
        child=self.child()
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.f.service.submit(self.f.command(self.memory.memory_id,'restore'))
        self.assertFalse(self.f.repository.current_usable(self.f.subject_id,child.memory_id),
                         'old child must not silently adopt the new parent version')

    def test_partial_root_merge_retains_source_bindings_and_new_evidence(self):
        child=self.child(); other=self.f.golden.memories[3]
        body=self.memory.to_dict(); body.update(memory_id='p12-child-alias',consolidation_id='p12-child-merge',
            consolidation_input_hash=None,scope=child.scope,content=child.content,source_event_ids=[],
            source_memory_ids=[self.memory.memory_id,other.memory_id],
            root_evidence_ids=[*self.memory.root_evidence_ids,*other.root_evidence_ids])
        result=self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
        self.assertEqual(result.memory.memory_id,child.memory_id)
        self.assertEqual(result.unique_evidence_added,len(other.root_evidence_ids))
        self.assertEqual(set(result.memory.root_evidence_ids),set(body['root_evidence_ids']))
        self.assertEqual(set(result.memory.source_memory_bindings),set(body['source_memory_ids']))
        self.assertTrue(self.f.repository.current_usable(self.f.subject_id,child.memory_id))

    def test_reconsolidation_cannot_recreate_deleted_evidence_under_new_identity(self):
        self.f.service.submit(self.f.command(self.memory.memory_id,'delete'))
        body=self.memory.to_dict(); body.update(memory_id='p12-alias',consolidation_id='p12-alias-operation',consolidation_input_hash=None)
        before={p:p.read_bytes() for p in self.root.rglob('*.json')}
        with self.assertRaises(MemoryValidationError): self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.json')})

    def test_new_alias_cannot_bypass_inactive_or_archived_state(self):
        for action in ('deactivate','archive'):
            self.f.service.submit(self.f.command(self.memory.memory_id,action))
            body=self.memory.to_dict(); body.update(memory_id='p12-alias-'+action,
                consolidation_id='p12-alias-operation-'+action,consolidation_input_hash=None)
            before={p:p.read_bytes() for p in self.root.rglob('*.json')}
            with self.subTest(action=action),self.assertRaises(MemoryValidationError):
                self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
            self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.json')})

    def test_invalid_source_after_real_revocation_cannot_restore(self):
        self.f.service.submit(self.f.command(self.memory.memory_id,'archive'))
        self.f.consolidation.propagate_signal(self.f.subject_id,lineage_id='p12-real-revoke',target_memory_id=self.memory.memory_id,
            signal=MemoryLineageType.REVOCATION,source_event_id='p12-revoke-event',root_evidence_ids=['event:p12-revoke-event'])
        before={p:p.read_bytes() for p in self.root.rglob('*.json')}
        with self.assertRaises(MemoryValidationError): self.f.service.submit(self.f.command(self.memory.memory_id,'restore'))
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.json')})


class CoreLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='p12-core-'); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.f=P09Fixture(self.root)
        self.approved={}
        self.permissions=PermissionService(JsonPermissionRepository(self.f.runtime.data_root),clock=self.f.runtime.clock.now)
        self.permission=self.permissions.create_permission(self.f.core.subject_id,permission_id='p12-core-grant',
            permission_type='TEST',name='TEST',description='TEST',scope=['*'],
            capabilities=['memory.lifecycle.'+a.value for a in LifecycleAction],source='TEST',reason='TEST').permission

    def service(self):
        return self.f.core.memory_lifecycle(self.permissions,
            confirmation_verifier=lambda c:self.approved.get(c.confirmation_id)==c.canonical_hash(),allow_test_delete=True)

    def command(self,identifier,action):
        memory=self.f.core.memory.load_memory(self.f.core.subject_id,identifier)
        now=self.f.runtime.clock.now(); service=self.service()
        key=f'core-p12:{identifier}:{memory.revision}:{action}'
        cmd=MemoryLifecycleCommand(key,memory.subject_id,'TEST',identifier,LifecycleAction(action),memory.revision,
            memory.canonical_hash(),self.permission.permission_id,0,memory.scope,'TEST normal Core lifecycle',
            now,now+timedelta(hours=1),'confirm:'+key,tuple(sorted(service.source_snapshot(memory).items())))
        self.approved[cmd.confirmation_id]=cmd.canonical_hash()
        return cmd

    def test_normal_context_before_after_and_no_memory_resurrection(self):
        self.f.event('p12-normal',content='continuity synthetic history')
        request=self.f.request(); self.assertIsInstance(self.f.submit(request),FirstRoundSuccessResult)
        context=self.f.context(request)
        ids=[r.stable_id for r in context.route.manifest.candidates]
        self.assertIn('memory:p12-normal',ids)
        revision=self.f.runtime.subject_state().revision
        before=self.f.adapter.path.read_bytes()
        self.service().submit(self.command('memory:p12-normal','archive'))
        self.assertEqual(self.f.runtime.subject_state().revision,revision)
        self.assertEqual(self.f.adapter.path.read_bytes(),before)
        self.assertFalse(self.f.core.current(context))
        self.f.reopen()
        next_request=self.f.request(); self.assertIsInstance(self.f.submit(next_request),FirstRoundSuccessResult)
        self.assertNotIn('memory:p12-normal',[r.stable_id for r in self.f.context(next_request).route.manifest.candidates])
        self.assertNotIn('p12-normal',[r.stable_id for r in self.f.context(next_request).route.manifest.candidates],
                         'ordinary C1 must not reintroduce forgotten material through raw Timeline recall')
        self.assertEqual(self.f.core.memory.load_memory(self.f.core.subject_id,'memory:p12-normal').effective_lifecycle.value,'archived')

    def test_disabled_memory_entry_has_zero_component_reads(self):
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        self.f.gates=ContinuityCoreGates(memory=False); self.f.reopen()
        with patch.object(self.f.core.memory,'load_memory',side_effect=AssertionError('disabled component read')):
            with self.assertRaises(ValueError): self.service()

    def test_thirty_days_bounded_normal_entry_and_restart_invariants(self):
        observations=[]
        with patch('socket.socket',side_effect=AssertionError('P12 must not open transport')):
            for step in range(6):
                self.f.runtime.clock.advance(timedelta(days=5))
                for index in range(2): self.f.event(f'p12-day-{step}-{index}',content='continuity synthetic durable history')
                request=self.f.request(); self.assertIsInstance(self.f.submit(request),FirstRoundSuccessResult)
                context=self.f.context(request)
                self.assertLessEqual(context.route.trace.budget_used,50)
                self.assertLessEqual(context.composition.trace.tokens_used,768)
                target=f'memory:p12-day-{step}-0'
                self.service().submit(self.command(target,'archive'))
                self.assertNotIn(target,[m.memory_id for m in self.f.core.memory.list_memories(self.f.core.subject_id)])
                self.assertEqual(self.f.runtime.subject_state().revision,1)
                self.assertEqual(self.f.adapter.effect_count,step+1)
                self.assertEqual(self.f.adapter.credits,step+1)
                observations.append({'day':(step+1)*5,'events':(step+1)*2,'effects':self.f.adapter.effect_count,
                    'tokens':context.composition.trace.tokens_used,
                    'bytes':sum(p.stat().st_size for p in self.f.runtime.data_root.rglob('*') if p.is_file())})
                if step in (1,3): self.f.reopen()
            self.assertEqual(self.f.manager.formal_access_count,0)
            self.assertLess(max(x['bytes'] for x in observations),8*1024*1024)
            self.assertEqual(len(self.f.core.memory.list_memories(self.f.core.subject_id,include_inactive=True)),13)
            self.assertEqual(len(self.f.core.memory.list_memories(self.f.core.subject_id)),7)
            print('P12_LONG_GOLDEN',{'logical_days':30,'events':12,'rounds':6,'reopen_after':[2,4],
                                   'observations':observations,'formal_access_count':0})


class MemoryLearningTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='p12-learning-'); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name); self.f=P12MemoryFixture(self.root/'f')
        self.learning=LearningService(JsonLearningRepository(self.f.root),clock=lambda:self.f.now)
        self.states=SubjectStateService(JsonSubjectStateRepository(self.root/'state'),clock=lambda:self.f.now)
        self.state=self.states.create(self.f.subject_id)

    def prepare(self,confidences=(.8,.8,.8),generator=False):
        candidates=[]
        for memory,confidence in zip(self.f.golden.memories[:3],confidences):
            roots=(x for x in memory.root_evidence_ids) if generator else memory.root_evidence_ids
            candidates.append(self.learning.create_candidate(self.f.subject_id,source_event_id=None,source_memory_id=memory.memory_id,
                root_evidence_ids=roots,related_state_revision=0,observation='synthetic',hypothesis='synthetic',
                proposed_change=StateMutation('identity.expression_preferences',ChangeOperation.APPEND,'P12 verified preference','TEST'),
                confidence=confidence,original_experience={'metadata':{'memory_environment':'TEST',
                    'memory_revision':memory.revision,'memory_hash':memory.canonical_hash()}},reason='TEST',source='TEST').learning_event)
        self.learning.validate_learning(self.f.subject_id,candidates[0].learning_id,
            [c.learning_id for c in candidates[1:]],reason='TEST',source='TEST')
        return candidates

    def solidify(self,candidate):
        return self.learning.solidify_learning(self.f.subject_id,candidate.learning_id,self.state,
            trait_name='P12 test',trait_description='TEST',reason='TEST',source='TEST',confirmed=True,expected_revision=0)

    def test_valid_memory_learning_preserves_confidence_policy_and_evolution_boundary(self):
        candidate=self.prepare((.95,.2,.2))[0]
        result=self.solidify(candidate)
        self.assertEqual(result.trait.confidence,.95)
        self.assertIsNotNone(result.event)
        self.assertEqual(self.states.load(self.f.subject_id).to_dict(),self.state.to_dict())
        self.assertEqual(self.states.get_update_history(self.f.subject_id),[])

    def test_iterable_roots_retained_without_double_consumption(self):
        candidate=self.prepare(generator=True)[0]
        actual=self.learning.get_learning_event(self.f.subject_id,candidate.learning_id).root_evidence_ids
        self.assertEqual(len(actual),3)
        self.assertEqual(set(actual),{root for m in self.f.golden.memories[:3] for root in m.root_evidence_ids})
        self.assertIsNotNone(self.solidify(candidate).event)

    def test_pending_support_rejects_archive_and_old_version_after_restore(self):
        candidate=self.prepare()[0]
        target=self.f.golden.memories[1]
        for action in ('archive','restore'):
            self.f.service.submit(self.f.command(target.memory_id,action))
            before={p:p.read_bytes() for p in self.root.rglob('*.json')}
            with self.subTest(action=action),self.assertRaises(LearningValidationError): self.solidify(candidate)
            self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.json')})

    def test_pending_support_rejects_downweight_and_zero_learning_write(self):
        candidate=self.prepare()[0]; target=self.f.golden.memories[1]
        self.f.service.submit(self.f.command(target.memory_id,'downweight',factor=.5))
        before={p:p.read_bytes() for p in self.root.rglob('*.json')}
        with self.assertRaises(LearningValidationError): self.solidify(candidate)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.json')})

    def test_valid_memory_learning_restart_can_solidify(self):
        candidate=self.prepare()[0]
        self.learning=LearningService(JsonLearningRepository(self.f.root),clock=lambda:self.f.now)
        self.assertIsNotNone(self.solidify(candidate).event)

    def test_missing_bound_memory_never_falls_back_to_legacy(self):
        candidate=self.prepare()[0]
        # Rename only the owned isolated fixture file to model missing persisted support.
        path=self.f.repository._path(self.f.subject_id); path.rename(path.with_suffix('.unavailable'))
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(LearningValidationError): self.solidify(candidate)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})


if __name__ == '__main__': unittest.main()
