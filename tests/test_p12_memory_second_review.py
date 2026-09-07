"""Independent adjacent-path probes; all Engine data is isolated in Temp."""
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.memory import MemoryRecord, MemoryRetrievalRequest
from continuity_engine.services.context_router_service import MemoryContextSource, ContextSourceQuery
from continuity_engine.services.memory_service import MemoryService, RepositoryMemoryRetriever
from continuity_engine.testing.p12_memory_fixture import P12MemoryFixture


class P12ExistingAliasProbes(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='p12-recheck-alias-')
        self.addCleanup(temporary.cleanup)
        self.f = P12MemoryFixture(Path(temporary.name) / 'fixture')
        self.original = self.f.golden.memories[0]
        body = self.original.to_dict()
        body.update(memory_id='independent-existing-alias', scope='independent:alias',
                    consolidation_id='independent-existing-alias-operation',
                    consolidation_input_hash=None)
        self.alias = self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory
        self.assertEqual(self.original.root_evidence_ids, self.alias.root_evidence_ids)
        self.assertEqual(self.original.content, self.alias.content)
        self.assertFalse(self.alias.source_memory_ids)
        self.query = ContextSourceQuery('independent-alias-query', self.f.subject_id,
            'TEST', 0, self.f.now, purpose=('memory',),
            query_terms=tuple(self.alias.content.split()), limit=100)
        self.assertIn(self.alias.memory_id, self.router_ids())

    def router_ids(self):
        source = MemoryContextSource(self.f.repository, environment='TEST')
        return {c.stable_id for c in source.retrieve(self.query).candidates}

    def act(self, action, **kwargs):
        self.f.service.submit(self.f.command(self.original.memory_id, action, **kwargs))

    def assert_existing_alias_excluded(self, action):
        self.act(action)
        self.f.reopen()
        original = self.f.repository.load_memory(self.f.subject_id, self.original.memory_id)
        self.assertFalse(original.is_available)
        self.assertNotIn(self.original.memory_id, self.router_ids())
        self.assertNotIn(self.alias.memory_id, self.router_ids(),
            f'{action} excluded the original but an existing same-root, identical-body alias remained consumable')

    def test_existing_alias_cannot_bypass_deactivation(self):
        self.assert_existing_alias_excluded('deactivate')

    def test_existing_alias_cannot_bypass_archive(self):
        self.assert_existing_alias_excluded('archive')

    def test_existing_alias_cannot_bypass_logical_delete(self):
        self.assert_existing_alias_excluded('delete')

    def test_zero_weight_alias_cannot_be_selected_by_legacy_service(self):
        self.act('downweight', factor=0)
        self.f.reopen()
        self.assertNotIn(self.alias.memory_id, self.router_ids(), 'normal Router control must exclude zero weight')
        alias = self.f.repository.load_memory(self.f.subject_id, self.alias.memory_id)
        self.assertEqual(alias.effective_weight, 0)
        request = MemoryRetrievalRequest('independent-zero-request', self.f.subject_id,
            self.alias.content, self.f.now, minimum_relevance=0, limit=100)
        service = MemoryService(RepositoryMemoryRetriever(self.f.repository), None,
                                clock=lambda: self.f.now)
        result = service.retrieve(request)
        self.assertNotIn(self.alias.memory_id, {m.memory_id for m in result.selected_memories},
            'valid minimum_relevance=0 selected a zero-weight alias through the legacy service')

    def test_positive_nonzero_downweight_is_inherited(self):
        self.act('downweight', factor=.1)
        self.f.reopen()
        source = MemoryContextSource(self.f.repository, environment='TEST')
        candidate = next(c for c in source.retrieve(self.query).candidates if c.stable_id == self.alias.memory_id)
        self.assertGreater(candidate.relevance, 0)
        self.assertLessEqual(candidate.relevance, .1)

    def test_positive_untouched_alias_is_legitimately_selected(self):
        request = MemoryRetrievalRequest('independent-positive-request', self.f.subject_id,
            self.alias.content, self.f.now, minimum_relevance=0, limit=100)
        service = MemoryService(RepositoryMemoryRetriever(self.f.repository), None,
                                clock=lambda: self.f.now)
        self.assertIn(self.alias.memory_id, {m.memory_id for m in service.retrieve(request).selected_memories})

    def test_positive_explicit_restore_reopens_existing_alias(self):
        self.act('archive')
        self.act('restore')
        self.f.reopen()
        self.assertIn(self.original.memory_id, self.router_ids())
        self.assertIn(self.alias.memory_id, self.router_ids())


class SameRootConsumptionTests(unittest.TestCase):
    setUp=P12ExistingAliasProbes.setUp
    router_ids=P12ExistingAliasProbes.router_ids
    act=P12ExistingAliasProbes.act

    def snapshot(self):
        return {str(p.relative_to(self.f.root)):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}

    def reference(self,memory):
        from continuity_engine.domain.context_routing import ContextCandidateReference,ContextPartition
        return ContextCandidateReference('engine.memory',ContextPartition.MEMORY,memory.memory_id,
            memory.subject_id,memory.environment,f'revision:{memory.revision}',memory.canonical_hash(),
            'MEMORY_RECORD',1,.9,memory.occurred_at,('TEST',))

    def summary(self):
        return self.f.consolidation.generate_summary(self.f.subject_id,summary_id='same-root-summary',
            summary_type='same.root',scope='same:root',source_memory_ids=[self.alias.memory_id],confidence=.8)

    def check_consumers(self,action):
        from continuity_engine.domain.context_routing import ContextCandidateReference,ContextPartition
        from continuity_engine.domain.errors import ContextCompositionSourceError
        from continuity_engine.services.context_material_resolvers import MemoryMaterialResolver,DerivedSummaryMaterialResolver
        from continuity_engine.services.context_router_service import DerivedSummaryContextSource
        summary=self.summary()
        ref=ContextCandidateReference('engine.derived-summary',ContextPartition.DERIVED_SUMMARY,summary.summary_id,
            summary.subject_id,summary.environment,f'version:{summary.summary_version}',summary.canonical_hash(),
            'DERIVED_MEMORY_VIEW',1,.9,summary.generated_at,('TEST',))
        source=MemoryContextSource(self.f.repository,environment='TEST'); batch=source.retrieve(self.query)
        candidate=next(c for c in batch.candidates if c.stable_id==self.alias.memory_id)
        summary_source=DerivedSummaryContextSource(self.f.repository,environment='TEST'); sb=summary_source.retrieve(self.query)
        sc=next(c for c in sb.candidates if c.stable_id==summary.summary_id)
        self.act(action); self.f.reopen(); before=self.snapshot()
        self.assertFalse(self.f.repository.current_usable(self.f.subject_id,self.alias.memory_id))
        self.assertFalse(source.revalidate(self.query,candidate,batch.source_version).valid)
        self.assertFalse(summary_source.revalidate(self.query,sc,sb.source_version).valid)
        with self.assertRaises(ContextCompositionSourceError):
            MemoryMaterialResolver(self.f.repository,environment='TEST').resolve(self.reference(self.alias))
        with self.assertRaises(ContextCompositionSourceError):
            DerivedSummaryMaterialResolver(self.f.repository,environment='TEST').resolve(ref)
        self.assertNotIn(summary.summary_id,{c.stable_id for c in summary_source.retrieve(self.query).candidates})
        self.assertEqual(before,self.snapshot(),'normal rejection cannot write, wake, allocate or bill')
        current=self.f.repository.load_memory(self.f.subject_id,self.alias.memory_id)
        self.assertEqual(current.content,self.alias.content)
        self.assertEqual(current.canonical_hash(),self.alias.canonical_hash(),'consume policy does not rewrite raw alias facts')

    def test_archive_blocks_alias_summary_exact_and_old_windows(self): self.check_consumers('archive')
    def test_deactivate_blocks_alias_summary_exact_and_old_windows(self): self.check_consumers('deactivate')
    def test_delete_blocks_alias_summary_exact_and_old_windows(self): self.check_consumers('delete')

    def test_summary_stays_invalid_after_restore_until_explicit_rebuild(self):
        summary=self.summary(); self.act('archive')
        self.assertEqual(self.f.repository.load_summary(self.f.subject_id,summary.summary_id).status.value,'INVALIDATED')
        self.act('restore'); self.f.reopen()
        self.assertIn(self.alias.memory_id,self.router_ids())
        self.assertEqual(self.f.repository.load_summary(self.f.subject_id,summary.summary_id).status.value,'INVALIDATED')
        rebuilt=self.summary()
        self.assertGreater(rebuilt.summary_version,summary.summary_version)
        self.assertEqual(self.f.repository.summary_weight(rebuilt),1)

    def test_restoring_original_does_not_rebind_old_explicit_child(self):
        body=self.original.to_dict()
        body.update(memory_id='bound-child',consolidation_id='bound-child-op',consolidation_input_hash=None,
                    scope='bound:child',source_event_ids=[],source_memory_ids=[self.original.memory_id])
        child=self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory
        self.act('archive'); self.act('restore'); self.f.reopen()
        self.assertFalse(self.f.repository.current_usable(self.f.subject_id,child.memory_id))
        self.assertIn(self.alias.memory_id,self.router_ids())

    def test_lifecycle_restriction_does_not_block_new_independent_root(self):
        self.act('delete'); other=self.f.golden.memories[1]; body=other.to_dict()
        body.update(memory_id='independent-new-root',consolidation_id='independent-new-root-op',
                    consolidation_input_hash=None,scope='independent:new-root')
        result=self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory
        self.assertTrue(result.is_available)
        self.assertEqual(result.effective_weight,1)
        self.assertTrue(self.f.repository.current_usable(self.f.subject_id,result.memory_id))

    def test_new_alias_after_governance_is_rejected_without_writes(self):
        from continuity_engine.domain.errors import MemoryValidationError
        self.act('archive'); body=self.original.to_dict()
        body.update(memory_id='late-alias',consolidation_id='late-alias-op',consolidation_input_hash=None,scope='late:alias')
        before=self.snapshot()
        with self.assertRaises(MemoryValidationError): self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
        self.assertEqual(before,self.snapshot())

    def test_authorized_archived_history_and_event_audit_remain_read_only(self):
        event=self.f.timeline.load_entry(self.f.subject_id,self.original.source_event_ids[0]).event
        event_hash=event.canonical_hash(); self.act('archive'); before=self.snapshot()
        result=self.f.service.recall_history(cue=' '.join(self.original.content.split()[:2]),limit=5,
            permission_id=self.f.permission.permission_id,permission_revision=self.f.permission.revision)
        self.assertIn(self.original.memory_id,{r['memory_id'] for r in result})
        self.assertEqual(event_hash,self.f.timeline.load_entry(self.f.subject_id,event.event_id).event.canonical_hash())
        self.assertEqual(before,self.snapshot())

    def test_deleted_root_cannot_leak_through_archived_alias_history_or_restore(self):
        from continuity_engine.domain.errors import MemoryValidationError
        self.f.service.submit(self.f.command(self.alias.memory_id,'archive'))
        self.act('delete'); self.f.reopen(); before=self.snapshot()
        with self.assertRaises(MemoryValidationError):
            self.f.service.recall_history(cue=' '.join(self.alias.content.split()[:2]),limit=5,
                permission_id=self.f.permission.permission_id,permission_revision=self.f.permission.revision)
        with self.assertRaises(MemoryValidationError):
            self.f.service.submit(self.f.command(self.alias.memory_id,'restore'))
        self.assertEqual(before,self.snapshot())

    def test_zero_weight_is_filtered_at_retriever_not_by_changing_zero_threshold(self):
        self.act('downweight',factor=0); request=MemoryRetrievalRequest('zero-threshold',self.f.subject_id,
            self.alias.content,self.f.now,minimum_relevance=0,limit=100)
        before=self.snapshot(); retriever=RepositoryMemoryRetriever(self.f.repository)
        candidates=retriever.retrieve(request)
        self.assertNotIn(self.alias.memory_id,{c.memory_id for c in candidates})
        result=MemoryService(retriever,None,clock=lambda:self.f.now).retrieve(request)
        self.assertTrue(result.selected_memories,'unrelated valid candidates remain selectable at threshold zero')
        self.assertNotIn(self.original.memory_id,{c.memory_id for c in result.selected_memories})
        self.assertNotIn(self.alias.memory_id,{c.memory_id for c in result.selected_memories})
        self.assertEqual(before,self.snapshot())

    def test_true_legacy_archive_temperature_enumeration_remains_compatible(self):
        body=self.alias.to_dict()
        body.update(revision=self.alias.revision+1,memory_version=self.alias.memory_version+1,temperature='ARCHIVED')
        saved=MemoryRecord.from_dict(body); self.f.repository.save_memory(saved); self.f.reopen()
        before=self.snapshot()
        self.assertIn(self.alias.memory_id,{m.memory_id for m in self.f.repository.list_memories(self.f.subject_id)})
        request=MemoryRetrievalRequest('legacy-archive',self.f.subject_id,self.alias.content,self.f.now,minimum_relevance=0,limit=100)
        self.assertNotIn(self.alias.memory_id,{m.memory_id for m in RepositoryMemoryRetriever(self.f.repository).retrieve(request)})
        current=self.f.repository.load_memory(self.f.subject_id,self.alias.memory_id)
        self.assertEqual(current.canonical_hash(),saved.canonical_hash())
        self.assertNotIn('lifecycle',current.to_dict())
        self.assertEqual(before,self.snapshot())

    def test_normal_c1_rejects_old_context_and_excludes_existing_alias_after_restart(self):
        from test_p12_memory_integration import CoreLifecycleTests
        from continuity_engine.services.memory_consolidation_service import MemoryConsolidationService
        from continuity_engine.domain.integration_results import FirstRoundSuccessResult
        host=CoreLifecycleTests(); host.setUp(); self.addCleanup(host.doCleanups)
        host.f.event('f1-core-event',content='f1 same root continuity evidence')
        self.assertIsInstance(host.f.submit(host.f.request()),FirstRoundSuccessResult)
        original=host.f.core.memory.load_memory(host.f.core.subject_id,'memory:f1-core-event')
        body=original.to_dict(); body.update(memory_id='f1-core-alias',scope='f1:core-alias',
            consolidation_id='f1-core-alias-op',consolidation_input_hash=None)
        MemoryConsolidationService(host.f.core.memory,clock=host.f.runtime.clock.now).consolidate(MemoryRecord.from_dict(body))
        request=host.f.request(); self.assertIsInstance(host.f.submit(request),FirstRoundSuccessResult)
        context=host.f.context(request)
        self.assertIn('f1-core-alias',{c.stable_id for c in context.route.manifest.candidates})
        revision=host.f.runtime.subject_state().revision; effects=host.f.adapter.path.read_bytes()
        host.service().submit(host.command(original.memory_id,'archive'))
        self.assertEqual(host.f.runtime.subject_state().revision,revision)
        self.assertEqual(host.f.adapter.path.read_bytes(),effects)
        self.assertFalse(host.f.core.current(context))
        host.f.reopen(); request=host.f.request()
        self.assertIsInstance(host.f.submit(request),FirstRoundSuccessResult)
        ids={c.stable_id for c in host.f.context(request).route.manifest.candidates}
        self.assertNotIn('f1-core-alias',ids)
        self.assertNotIn(original.memory_id,ids)
        self.assertNotIn('f1-core-event',ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
