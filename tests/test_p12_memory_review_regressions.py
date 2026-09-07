"""Independent P12 counterexamples against public Engine entry points, Temp only."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import MemoryValidationError, MemoryPersistenceError
from continuity_engine.domain.memory import MemoryRecord
from continuity_engine.testing.p12_memory_fixture import P12MemoryFixture
from continuity_engine.services.context_router_service import MemoryContextSource, ContextSourceQuery


class P12IndependentProbes(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='p12-independent-')
        self.addCleanup(temporary.cleanup)
        self.f = P12MemoryFixture(Path(temporary.name) / 'fixture')
        self.memory = self.f.golden.memories[0]

    def current(self):
        return self.f.repository.load_memory(self.f.subject_id, self.memory.memory_id)

    def act(self, action, **kwargs):
        return self.f.service.submit(self.f.command(self.memory.memory_id, action, **kwargs))

    def recall(self):
        return self.f.service.recall_history(cue=' '.join(self.memory.content.split()[:2]), limit=1,
            permission_id=self.f.permission.permission_id, permission_revision=self.f.permission.revision)

    def test_history_recall_rechecks_permission_after_source_port(self):
        self.act('archive')
        source = self.f.service.source_snapshot
        def revoke_during_lookup(memory):
            result = source(memory)
            self.f.permissions.revoke_permission(self.f.subject_id, self.f.permission.permission_id,
                reason='independent revoke while lookup is in flight', source='TEST')
            return result
        self.f.service.source_snapshot = revoke_during_lookup
        try:
            result = self.recall()
        except MemoryValidationError:
            return
        self.assertEqual(result, (), 'recall returned archived body after its permission was revoked')

    def test_history_recall_does_not_return_body_deleted_during_lookup(self):
        self.act('archive')
        source = self.f.service.source_snapshot
        def delete_during_lookup(memory):
            result = source(memory)
            self.act('delete')
            return result
        self.f.service.source_snapshot = delete_during_lookup
        try:
            result = self.recall()
        except MemoryValidationError:
            return
        self.assertEqual(self.current().effective_lifecycle.value, 'deleted')
        self.assertEqual(result, (), 'recall returned deleted body from its stale initial snapshot')

    def test_unbound_successor_cannot_drop_lifecycle_and_restore_archived_memory(self):
        self.act('archive')
        current = self.current()
        payload = current.to_dict()
        for field in ('lifecycle', 'retrieval_weight', 'weight_updated_at', 'lifecycle_command_id'):
            payload.pop(field, None)
        payload.update(revision=current.revision + 1, memory_version=current.memory_version + 1)
        before = {p: p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        try:
            self.f.repository.save_memory(MemoryRecord.from_dict(payload))
        except (MemoryValidationError, MemoryPersistenceError):
            self.assertEqual(before, {p: p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
            return
        self.f.reopen()
        self.assertFalse(self.current().is_available,
            'an unconfirmed successor stripped P12 fields and revived archived memory after restart')

    def test_new_derived_memory_cannot_restore_downweighted_root_influence(self):
        self.act('downweight', factor=.1)
        parent = self.current()
        payload = self.memory.to_dict()
        payload.update(memory_id='review-child', consolidation_id='review-child-operation',
            consolidation_input_hash=None, source_event_ids=[], source_memory_ids=[parent.memory_id],
            scope='review:derived', content='review derived evidence', tags=['review', 'derived'])
        child = self.f.consolidation.consolidate(MemoryRecord.from_dict(payload)).memory
        source = MemoryContextSource(self.f.repository, environment='TEST')
        query = ContextSourceQuery('review-query', self.f.subject_id, 'TEST', 0, self.f.now,
                                   purpose=('memory',), query_terms=('review', 'derived'), limit=10)
        candidate = next(c for c in source.retrieve(query).candidates if c.stable_id == child.memory_id)
        self.assertGreater(candidate.relevance, 0, 'probe must actually query the matching terms')
        self.assertLessEqual(candidate.relevance, .1,
            'same downweighted root became a full-weight derived memory without new independent evidence')

    def test_consolidation_race_cannot_return_fresh_active_material_after_archive(self):
        operation = self.f.repository.load_consolidation_operation(self.f.subject_id, self.memory.consolidation_id)
        payload = dict(operation.canonical_input)
        payload.update(memory_id='review-alias', consolidation_id='review-alias-operation', consolidation_input_hash=None)
        candidate = MemoryRecord.from_dict(payload)
        original = self.f.repository.save_consolidation
        archived = False
        def archive_before_persist(memory, operation):
            nonlocal archived
            if not archived:
                archived = True
                self.act('archive')
            return original(memory, operation)
        self.f.repository.save_consolidation = archive_before_persist
        try:
            result = self.f.consolidation.consolidate(candidate)
        except (MemoryValidationError, MemoryPersistenceError):
            return
        self.assertFalse(self.current().is_available)
        self.assertFalse(result.memory.is_available,
            'consolidation returned old active payload as fresh material after transaction observed archive')

    def test_control_new_independent_evidence_still_creates_memory(self):
        self.act('downweight', factor=.1)
        payload = self.memory.to_dict()
        payload.update(memory_id='review-independent', consolidation_id='review-independent-operation',
            consolidation_input_hash=None, source_event_ids=['review-new-event'], source_memory_ids=[],
            root_evidence_ids=['event:review-new-event'], scope='review:new', content='new independent event')
        created = self.f.consolidation.consolidate(MemoryRecord.from_dict(payload)).memory
        self.assertTrue(created.is_available)
        self.assertEqual(created.effective_weight, 1)

    def test_confirmation_reentry_does_not_overwrite_another_successful_command(self):
        other = self.f.golden.memories[1]
        nested = self.f.command(other.memory_id, 'archive')
        outer = self.f.command(self.memory.memory_id, 'downweight', factor=.5)
        original = self.f.service.confirmation_verifier
        nested_done = False
        def confirm_with_other_command(command):
            nonlocal nested_done
            if command.command_id == outer.command_id and not nested_done:
                nested_done = True
                receipt = self.f.service.submit(nested)
                self.assertEqual(receipt.lifecycle, 'archived')
            return original(command)
        self.f.service.confirmation_verifier = confirm_with_other_command
        try:
            self.f.service.submit(outer)
        except (MemoryValidationError, MemoryPersistenceError):
            pass
        self.f.reopen()
        self.assertEqual(self.f.repository.load_memory(self.f.subject_id, other.memory_id).effective_lifecycle.value,
                         'archived', 'outer transaction erased an already successful nested archive command')

    def test_control_current_authorized_history_recall_still_works(self):
        self.act('archive')
        result = self.recall()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'], self.memory.content)
        self.assertFalse(result[0]['restored'])

    def test_control_approved_restore_and_deleted_recovery_rejection(self):
        self.act('archive')
        self.act('restore')
        self.assertTrue(self.current().is_available)
        self.act('delete')
        with self.assertRaises(MemoryValidationError):
            self.act('restore')


class P12ReviewInterleavingTests(unittest.TestCase):
    setUp = P12IndependentProbes.setUp
    current = P12IndependentProbes.current
    act = P12IndependentProbes.act
    recall = P12IndependentProbes.recall

    def snapshot(self):
        return {str(p.relative_to(self.f.root)):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}

    def alias(self, identifier='extra-alias', *, parent=None):
        body=self.memory.to_dict()
        body.update(memory_id=identifier,consolidation_id=identifier+'-operation',consolidation_input_hash=None,
                    scope=identifier,content='review derived evidence',tags=['review','derived'])
        if parent is not None:
            body.update(source_event_ids=[],source_memory_ids=[parent.memory_id])
        return self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory

    def test_r1_later_candidate_deletes_earlier_match_no_body(self):
        self.act('archive')
        other=self.f.golden.memories[1]
        self.f.service.submit(self.f.command(other.memory_id,'archive'))
        source=self.f.service.source_snapshot
        changed=False
        def interleave(memory):
            nonlocal changed
            result=source(memory)
            if memory.memory_id==other.memory_id and not changed:
                changed=True
                self.act('delete')
            return result
        self.f.service.source_snapshot=interleave
        with self.assertRaises(MemoryValidationError):
            self.f.service.recall_history(cue='the subject',limit=5,
                permission_id=self.f.permission.permission_id,permission_revision=0)
        self.assertTrue(changed)
        self.assertEqual(self.current().effective_lifecycle.value,'deleted')

    def test_r1_source_binding_changed_between_checks_zero_write(self):
        self.act('archive'); source=self.f.service.source_snapshot; calls=0
        def drift(memory):
            nonlocal calls
            calls+=1
            result=source(memory)
            return result if calls==1 else {k:'sha256:'+'0'*64 for k in result}
        self.f.service.source_snapshot=drift
        before=self.snapshot()
        with self.assertRaises(MemoryValidationError): self.recall()
        self.assertEqual(before,self.snapshot())

    def test_r1_restore_during_lookup_rejects_old_version(self):
        self.act('archive'); source=self.f.service.source_snapshot; changed=False
        def interleave(memory):
            nonlocal changed
            result=source(memory)
            if not changed:
                changed=True
                self.f.service.source_snapshot=source
                self.act('restore')
            return result
        self.f.service.source_snapshot=interleave
        with self.assertRaises(MemoryValidationError): self.recall()
        self.assertTrue(self.current().is_available)

    def test_r1_legal_history_reopen_zero_write(self):
        self.act('archive'); self.f.reopen(); before=self.snapshot()
        self.assertEqual(self.recall()[0]['content'],self.memory.content)
        self.assertEqual(before,self.snapshot())
        self.assertFalse(self.current().is_available)

    def test_r2_each_missing_field_rejected_at_save_zero_write(self):
        self.act('downweight',factor=.5); self.act('archive'); current=self.current(); before=self.snapshot()
        for field in ('lifecycle','retrieval_weight','weight_updated_at','lifecycle_command_id'):
            with self.subTest(field=field):
                body=current.to_dict(); body.pop(field)
                body.update(revision=current.revision+1,memory_version=current.memory_version+1)
                with self.assertRaises((MemoryValidationError,MemoryPersistenceError)):
                    self.f.repository.save_memory(MemoryRecord.from_dict(body))
                self.assertEqual(before,self.snapshot())

    def test_r2_hash_consistent_downgrade_rejected_on_load_zero_write(self):
        import json
        self.act('archive'); current=self.current()
        path=self.f.repository._path(self.f.subject_id)
        doc=json.loads(path.read_text(encoding='utf-8')); doc.pop('document_hash')
        body=current.to_dict()
        for field in ('lifecycle','retrieval_weight','weight_updated_at','lifecycle_command_id'): body.pop(field,None)
        body.update(revision=current.revision+1,memory_version=current.memory_version+1)
        doc['memory_records'].append(body)
        doc['document_hash']=self.f.repository._document_hash(doc)
        path.write_text(json.dumps(doc),encoding='utf-8'); before=self.snapshot()
        self.f.reopen()
        with self.assertRaises(MemoryPersistenceError): self.current()
        self.assertEqual(before,self.snapshot())

    def test_r2_legacy_successor_retains_missing_fields_and_hash(self):
        body=self.current().to_dict(); body.update(revision=1,memory_version=self.memory.memory_version+1)
        memory=MemoryRecord.from_dict(body)
        self.f.repository.save_memory(memory); self.f.reopen()
        self.assertEqual(self.current().canonical_hash(),memory.canonical_hash())
        self.assertNotIn('lifecycle',self.current().to_dict())

    def test_r2_governed_ordinary_successor_preserves_archive(self):
        self.act('archive'); body=self.current().to_dict()
        body.update(revision=body['revision']+1,memory_version=body['memory_version']+1)
        self.f.repository.save_memory(MemoryRecord.from_dict(body)); self.f.reopen()
        self.assertFalse(self.current().is_available)
        self.act('restore'); self.assertTrue(self.current().is_available)

    def test_r3_same_target_nested_fact_survives_outer_rejection(self):
        nested=self.f.command(self.memory.memory_id,'archive')
        outer=self.f.command(self.memory.memory_id,'downweight',factor=.5)
        original=self.f.service.confirmation_verifier; nested_snapshot=None
        def confirm(command):
            nonlocal nested_snapshot
            if command.command_id==outer.command_id:
                self.f.service.submit(nested); nested_snapshot=self.snapshot()
            return original(command)
        self.f.service.confirmation_verifier=confirm
        with self.assertRaises(MemoryValidationError): self.f.service.submit(outer)
        self.assertEqual(nested_snapshot,self.snapshot())
        self.f.reopen()
        self.assertEqual(self.current().revision,1)
        self.assertEqual(self.current().effective_lifecycle.value,'archived')
        self.assertFalse(any(x.lineage_id==outer.command_id for x in self.f.repository.list_lineage(self.f.subject_id)))

    def test_r3_source_callback_nested_other_commit_survives_and_outer_retry(self):
        other=self.f.golden.memories[1]
        nested=self.f.command(other.memory_id,'archive'); outer=self.f.command(self.memory.memory_id,'downweight',factor=.5)
        source=self.f.service.source_snapshot; nested_snapshot=None
        def interleave(memory):
            nonlocal nested_snapshot
            result=source(memory)
            self.f.service.submit(nested); nested_snapshot=self.snapshot()
            return result
        self.f.service.source_snapshot=interleave
        with self.assertRaises(MemoryValidationError): self.f.service.submit(outer)
        self.assertEqual(nested_snapshot,self.snapshot())
        self.f.reopen()
        self.f.service.submit(outer)
        before=self.snapshot(); self.assertTrue(self.f.service.submit(outer).replay)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.f.repository.load_memory(self.f.subject_id,other.memory_id).effective_lifecycle.value,'archived')
        self.assertEqual(self.current().effective_weight,.5)

    def test_r4_first_alias_archive_interleaving_does_not_append_operation(self):
        op=self.f.repository.load_consolidation_operation(self.f.subject_id,self.memory.consolidation_id)
        body=dict(op.canonical_input); body.update(memory_id='r4-alias',consolidation_id='r4-op',consolidation_input_hash=None)
        save=self.f.repository.save_consolidation; archived_snapshot=None
        def interleave(memory,operation):
            nonlocal archived_snapshot
            self.act('archive'); archived_snapshot=self.snapshot()
            return save(memory,operation)
        self.f.repository.save_consolidation=interleave
        with self.assertRaises(MemoryValidationError): self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
        self.assertEqual(archived_snapshot,self.snapshot())
        self.assertIsNone(self.f.repository.load_consolidation_operation(self.f.subject_id,'r4-op'))

    def test_r4_after_commit_archive_blocks_body_but_preserves_true_operation(self):
        op=self.f.repository.load_consolidation_operation(self.f.subject_id,self.memory.consolidation_id)
        body=dict(op.canonical_input); body.update(memory_id='r4-alias',consolidation_id='r4-op',consolidation_input_hash=None)
        save=self.f.repository.save_consolidation
        def interleave(memory,operation):
            result=save(memory,operation); self.act('archive'); return result
        self.f.repository.save_consolidation=interleave
        with self.assertRaises(MemoryValidationError): self.f.consolidation.consolidate(MemoryRecord.from_dict(body))
        self.assertIsNotNone(self.f.repository.load_consolidation_operation(self.f.subject_id,'r4-op'))
        self.assertFalse(self.current().is_available)

    def test_r4_legal_new_alias_and_exact_replay_remain_compatible(self):
        op=self.f.repository.load_consolidation_operation(self.f.subject_id,self.memory.consolidation_id)
        body=dict(op.canonical_input); body.update(memory_id='r4-alias',consolidation_id='r4-op',consolidation_input_hash=None)
        candidate=MemoryRecord.from_dict(body)
        first=self.f.consolidation.consolidate(candidate)
        self.assertEqual(first.memory.canonical_hash(),self.memory.canonical_hash())
        self.f.reopen(); before=self.snapshot()
        replay=self.f.consolidation.consolidate(candidate)
        self.assertEqual(replay.memory.canonical_hash(),first.memory.canonical_hash())
        self.assertTrue(replay.memory.is_available)
        self.assertEqual(before,self.snapshot())

    def test_r5_raw_root_new_scope_and_transitive_chain_retain_ceiling_after_restart(self):
        self.act('downweight',factor=.1)
        raw=self.alias('raw-root')
        child=self.alias('child',parent=self.current())
        grandchild=self.alias('grandchild',parent=child)
        self.f.reopen(); before=self.snapshot()
        query=ContextSourceQuery('r5',self.f.subject_id,'TEST',0,self.f.now,purpose=('memory',),query_terms=('review','derived'),limit=10)
        candidates=MemoryContextSource(self.f.repository,environment='TEST').retrieve(query).candidates
        for m in (raw,child,grandchild):
            with self.subTest(memory_id=m.memory_id):
                current=self.f.repository.load_memory(self.f.subject_id,m.memory_id)
                self.assertEqual(current.effective_weight,.1)
                self.assertEqual(current.confidence,m.confidence)
                candidate=next(c for c in candidates if c.stable_id==m.memory_id)
                self.assertGreater(candidate.relevance,0)
                self.assertLessEqual(candidate.relevance,.1)
                self.assertNotIn('consumption_weight',current.to_dict())
        self.assertEqual(before,self.snapshot())

    def test_r5_composer_summary_and_legacy_retriever_use_current_ceiling(self):
        from continuity_engine.domain.context_routing import ContextCandidateReference, ContextPartition
        from continuity_engine.services.context_material_resolvers import MemoryMaterialResolver, DerivedSummaryMaterialResolver
        from continuity_engine.services.memory_service import RepositoryMemoryRetriever
        from continuity_engine.domain.memory import MemoryRetrievalRequest
        self.act('downweight',factor=.1); child=self.alias(parent=self.current())
        ref=ContextCandidateReference('engine.memory',ContextPartition.MEMORY,child.memory_id,self.f.subject_id,'TEST',
            f'revision:{child.revision}',child.canonical_hash(),'MEMORY_RECORD',1,.9,child.occurred_at,('TEST',))
        payload=MemoryMaterialResolver(self.f.repository,environment='TEST').resolve(ref)
        self.assertAlmostEqual(payload.confidence,child.confidence*.1)
        summary=self.f.consolidation.generate_summary(self.f.subject_id,summary_id='r5-summary',summary_type='review.test',
            scope='TEST',source_memory_ids=[child.memory_id],confidence=.8)
        ref=ContextCandidateReference('engine.derived-summary',ContextPartition.DERIVED_SUMMARY,summary.summary_id,
            self.f.subject_id,'TEST',f'version:{summary.summary_version}',summary.canonical_hash(),
            'DERIVED_MEMORY_VIEW',1,.9,summary.generated_at,('TEST',))
        self.assertAlmostEqual(DerivedSummaryMaterialResolver(self.f.repository,environment='TEST').resolve(ref).confidence,.08)
        request=MemoryRetrievalRequest('r5-retrieve',self.f.subject_id,'review derived',self.f.now,limit=10)
        result=next(c for c in RepositoryMemoryRetriever(self.f.repository).retrieve(request) if c.memory_id==child.memory_id)
        self.assertLessEqual(result.provider_relevance,.1)

    def test_r5_same_root_alias_before_downweight_revalidated_without_hash_rewrite(self):
        child=self.alias()
        source=MemoryContextSource(self.f.repository,environment='TEST')
        query=ContextSourceQuery('r5',self.f.subject_id,'TEST',0,self.f.now,purpose=('memory',),query_terms=('review','derived'),limit=10)
        before=source.retrieve(query); reference=next(c for c in before.candidates if c.stable_id==child.memory_id)
        self.act('downweight',factor=.1)
        self.assertEqual(self.f.repository.load_memory(self.f.subject_id,child.memory_id).canonical_hash(),child.canonical_hash())
        self.assertFalse(source.revalidate(query,reference,before.source_version).valid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
