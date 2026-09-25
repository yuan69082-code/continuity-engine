"""N06 regression: terminal compaction, explicit legacy identity, current roots."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.events import (ChangeOperation, Event, EventClassification,
    StateMutation, StateSection)
from continuity_engine.domain.memory import (MemoryEvidenceType, MemoryKind, MemoryRecord,
    MemoryTimeRange, MemoryLineageType)
from continuity_engine.domain.unfinished_item import UnfinishedItem, active_titles
from continuity_engine.services.unfinished_item_service import UnfinishedItemService
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.w02_c_fixture import W02CFixture


class W03N06RepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='w03-n06-repair-')
        self.addCleanup(temp.cleanup)
        self.f = P09Fixture(Path(temp.name))
        self.f.event('n06-root', content='Synthetic original matter source.')
        self.service = UnfinishedItemService(self.f.core)

    def item(self, name, *, title=None, roots=('event:n06-root',), **changes):
        now = self.f.runtime.clock.now().isoformat().replace('+00:00','Z')
        fields = dict(item_id=name, subject_id=self.f.runtime.descriptor.subject_id,
            environment='TEST', title=title or 'Synthetic '+name, source_roots=roots,
            willing=True, importance_reason='Subject chose a TEST matter.', urgency='NORMAL',
            due_at=None, wait_condition=None, next_step='Review original source',
            status='OPEN', created_at=now, updated_at=now, revision=0,
            completion=None, last_progress=None)
        return UnfinishedItem(**{**fields, **changes})

    def context(self):
        request=self.f.request(); self.f.submit(request)
        return self.f.context(request)

    def submit(self, item, command, *, context=None, **kwargs):
        return self.service.submit(item, command_id=command,
            expected_revision=self.f.runtime.subject_state().revision,
            context=context, reason='Bound original N06 command.', **kwargs)

    def test_completed_and_cancelled_sink_without_exhausting_64_current_slots(self):
        for number in range(65):
            item=self.item('matter-%03d' % number)
            self.submit(item,'create-%03d' % number)
            terminal=replace(item, revision=1, status='CANCELLED')
            self.submit(terminal,'cancel-%03d' % number)
        self.assertEqual(self.f.runtime.subject_state().continuity.item_records, [])
        history=self.f.runtime.subject_states.get_update_history(self.f.runtime.descriptor.subject_id)
        self.assertEqual(sum(u.event.source=='w03.subject-item' for u in history),130)
        self.f.reopen(); self.service=UnfinishedItemService(self.f.core)
        self.submit(self.item('new-matter'),'new-after-65')
        self.assertEqual([x['item_id'] for x in self.f.runtime.subject_state().continuity.item_records],
                         ['new-matter'])
        before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(StateEvolutionError):
            self.submit(self.item('matter-000'),'reuse-terminal-identity')
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)

    def test_same_title_needs_explicit_version_bound_legacy_migration(self):
        title='Synthetic same concern'
        now=self.f.runtime.clock.now()
        self.f.runtime.subject_states.apply_event(self.f.runtime.descriptor.subject_id,
            Event.create(event_id='legacy-matter',occurred_at=now,
                source='w03.synthetic-old-state',event_type='legacy_item_update',
                content='Original TEST old-format matter.',
                impact_scope=[StateSection.CONTINUITY],
                classification=EventClassification.STATE_CHANGE,
                mutations=[StateMutation('continuity.unfinished_items',
                    ChangeOperation.SET,[title],'Synthetic old-format item.')],
                reason='Original legacy format fixture'))
        self.assertIn(title,active_titles(self.f.runtime.subject_state().continuity))
        item=self.item('typed-matter',title=title)
        before=tree_inventory_hash(self.f.runtime.data_root)
        wrong=dict(index=0,title=title,list_hash=digest(['other item']))
        with self.assertRaises(StateEvolutionError):
            self.submit(item,'bad-migration',legacy_binding=wrong)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)
        binding=dict(index=0,title=title,list_hash=digest([title]))
        first=self.submit(item,'linked-create',legacy_binding=binding)
        self.assertEqual(self.f.runtime.subject_state().continuity.unfinished_items,[])
        self.assertEqual(self.service.submit(item,command_id='linked-create',
            expected_revision=first.before_revision, reason='Bound original N06 command.',
            legacy_binding=binding).update_id,first.update_id)
        self.submit(replace(item,revision=1,status='CANCELLED'),'linked-cancel')
        self.f.reopen(); self.service=UnfinishedItemService(self.f.core)
        self.assertNotIn(title,active_titles(self.f.runtime.subject_state().continuity))
        self.assertEqual(self.service.read(self.context())['legacy'],[])

    def test_same_title_without_binding_keeps_ambiguous_legacy_item(self):
        title='Synthetic ambiguous concern'
        now=self.f.runtime.clock.now()
        self.f.runtime.subject_states.apply_event(self.f.runtime.descriptor.subject_id,
            Event.create(event_id='legacy-ambiguous',occurred_at=now,
                source='w03.synthetic-old-state',event_type='legacy_item_update',
                content='Original TEST old-format matter.',impact_scope=[StateSection.CONTINUITY],
                classification=EventClassification.STATE_CHANGE,
                mutations=[StateMutation('continuity.unfinished_items',ChangeOperation.SET,
                    [title],'Synthetic old-format item.')],reason='Original legacy format fixture'))
        item=self.item('typed-ambiguous',title=title)
        self.submit(item,'unlinked-create')
        self.submit(replace(item,revision=1,status='CANCELLED'),'unlinked-cancel')
        self.assertIn(title,active_titles(self.f.runtime.subject_state().continuity))
        self.assertEqual(self.service.read(self.context())['legacy'][0]['status'],
                         'LEGACY_UNSTRUCTURED')

    def test_original_w03_command_hash_replays_without_new_revision(self):
        item=self.item('old-command')
        command='historical-command'
        reason='Bound original N06 command.'
        before=self.f.runtime.subject_state().revision
        identity=digest({'item':item.to_dict(),'expected_revision':before,
                         'reason':reason,'command_id':command})
        event=Event.create(event_id='w03-item:'+digest([
            self.f.core.subject_id,self.f.core.environment,command])[7:],
            occurred_at=self.f.runtime.clock.now(),source='w03.subject-item',
            event_type='unfinished_item_update',content='Subject matter state changed.',
            impact_scope=[StateSection.CONTINUITY],
            classification=EventClassification.STATE_CHANGE,
            mutations=[StateMutation('continuity.item_records',ChangeOperation.SET,
                [item.to_dict()],reason)],reason=reason,
            metadata={'w03_command_hash':identity,'item_id':item.item_id})
        original=self.f.runtime.subject_states.apply_event(
            self.f.runtime.descriptor.subject_id,event,expected_revision=before).update
        stable=tree_inventory_hash(self.f.runtime.data_root)
        self.assertEqual(self.service.submit(item,command_id=command,
            expected_revision=before,reason=reason).update_id,original.update_id)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),stable)

    def test_existing_structured_item_can_bind_legacy_on_terminal_transition(self):
        title='Synthetic existing concern'
        now=self.f.runtime.clock.now()
        self.f.runtime.subject_states.apply_event(self.f.runtime.descriptor.subject_id,
            Event.create(event_id='legacy-existing',occurred_at=now,
                source='w03.synthetic-old-state',event_type='legacy_item_update',
                content='Original TEST old-format matter.',impact_scope=[StateSection.CONTINUITY],
                classification=EventClassification.STATE_CHANGE,
                mutations=[StateMutation('continuity.unfinished_items',ChangeOperation.SET,
                    [title],'Synthetic old-format item.')],reason='Original legacy format fixture'))
        item=self.item('typed-existing',title=title)
        self.submit(item,'existing-create')
        self.assertIn(title,active_titles(self.f.runtime.subject_state().continuity))
        binding=dict(index=0,title=title,list_hash=digest([title]))
        completed=replace(item,revision=1,status='CANCELLED')
        self.submit(completed,'existing-cancel-with-binding',legacy_binding=binding)
        self.f.reopen();self.service=UnfinishedItemService(self.f.core)
        self.assertNotIn(title,active_titles(self.f.runtime.subject_state().continuity))

    def test_unavailable_local_memory_is_not_ready_and_read_is_read_only(self):
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        with tempfile.TemporaryDirectory(prefix='n06-local-') as root:
            f=P09Fixture(Path(root),gates=ContinuityCoreGates(memory=False))
            f.event('n06-root',content='Synthetic original matter source.')
            service=UnfinishedItemService(f.core)
            now=f.runtime.clock.now()
            memory=MemoryRecord(memory_id='n06-local-memory',subject_id=f.runtime.descriptor.subject_id,
                environment='TEST',kind=MemoryKind.SEMANTIC,
                evidence_type=MemoryEvidenceType.EXPERIENTIAL,content='Synthetic matter evidence',
                root_evidence_ids=['event:n06-root'],source_event_ids=['n06-root'],
                occurred_at=now,observed_at=now,recorded_at=now,consolidated_at=now,
                confidence=0.8,importance=0.5,activation=0.0,scope='n06.synthetic',
                time_range=MemoryTimeRange(now,now),consolidation_id='n06-memory-consolidation')
            memory=f.core.consolidation.consolidate(memory).memory
            item=self.item('memory-matter',roots=('memory:'+memory.memory_id,))
            item=replace(item,subject_id=f.runtime.descriptor.subject_id)
            service.submit(item,command_id='memory-create',expected_revision=f.runtime.subject_state().revision,
                reason='Bound original N06 command.')
            request=f.request();f.submit(request);context=f.context(request)
            self.assertEqual(len(service.ready(context)),1)
            from continuity_engine.services.context_router_service import ContextPermissionDecision
            original_authorize=f.permission.authorize_source
            def deny_only_memory(query,source_id,partition):
                if source_id=='engine.memory':
                    return ContextPermissionDecision(False,'TEST_MEMORY_SOURCE_REVOKED','test-n06-v1')
                return original_authorize(query,source_id,partition)
            permission_before=tree_inventory_hash(f.runtime.data_root)
            with patch.object(f.permission,'authorize_source',side_effect=deny_only_memory):
                self.assertTrue(f.core.current(context))
                self.assertEqual(service.ready(context),())
            self.assertEqual(tree_inventory_hash(f.runtime.data_root),permission_before)
            unavailable=replace(f.core.memory.load_memory(f.runtime.descriptor.subject_id,memory.memory_id),
                                retrieval_weight=0.0)
            before=tree_inventory_hash(f.runtime.data_root)
            with patch.object(f.core.memory,'load_memory',return_value=unavailable):
                self.assertEqual(service.ready(context),())
            wrong_subject=replace(f.core.memory.load_memory(f.runtime.descriptor.subject_id,
                memory.memory_id),subject_id='other-test-subject')
            with patch.object(f.core.memory,'load_memory',return_value=wrong_subject):
                self.assertEqual(service.ready(context),())
            self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
            f.event('n06-memory-revoked',content='TEST Memory revocation event.')
            f.core.consolidation.propagate_signal(f.runtime.descriptor.subject_id,
                lineage_id='n06-memory-revocation',target_memory_id=memory.memory_id,
                signal=MemoryLineageType.REVOCATION,source_event_id='n06-memory-revoked',
                root_evidence_ids=['event:n06-memory-revoked','event:n06-root'])
            self.assertFalse(f.core.memory.load_memory(f.runtime.descriptor.subject_id,
                                                       memory.memory_id).is_available)
            f.reopen();service=UnfinishedItemService(f.core)
            request=f.request();f.submit(request);fresh=f.context(request)
            before=tree_inventory_hash(f.runtime.data_root)
            self.assertEqual(service.ready(fresh),())
            self.assertEqual(service.read(fresh)['source_status']['memory-matter'],
                             'SOURCE_NOT_CURRENT')
            self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_withdrawn_external_rendering_stops_item_after_reopen(self):
        with tempfile.TemporaryDirectory(prefix='wc-') as root:
            f=W02CFixture(Path(root))
            roots=('external:n06-one','external:n06-two')
            original='continuity: original report remains available'
            derived='continuity: derived report is withdrawn'
            for content in (original,derived):
                for root_id in roots:
                    f.base.fake.candidate_hook=lambda c,root_id=root_id,content=content:replace(
                        c,roots=(root_id,),content=content,content_hash=digest(content),
                        source_id='item:n06-derived' if content==derived else c.source_id)
                    if not f.base.fake.facts():f.submit()
                    else:f.next_round()
            candidate=next(c for _,result,_ in f.base.external.absorbed()
                for c in result.candidates if c.content_hash==digest(derived))
            memory=f.absorption.adopt_corroborated(candidate.source_id,candidate.content_hash,
                reason='Two independent current TEST roots').memory
            now=f.base.runtime.clock.now().isoformat().replace('+00:00','Z')
            item=UnfinishedItem(item_id='external-matter',subject_id=f.state.subject_id,
                environment='TEST',title='Current external evidence matter',
                source_roots=('memory:'+memory.memory_id,),willing=True,
                importance_reason='Subject chose a TEST matter.',urgency='NORMAL',due_at=None,
                wait_condition=None,next_step='Check current source',status='OPEN',
                created_at=now,updated_at=now)
            service=UnfinishedItemService(f.core)
            service.submit(item,command_id='external-create',expected_revision=f.state.revision,
                reason='Current external source')
            f.next_round(); context=f.last_context
            self.assertEqual(len(service.ready(context)),1)
            original=f.source(roots[0])
            self.assertIn(digest(derived),original.material_hashes)
            self.assertNotEqual(original.canonical_hash,digest(derived))
            f.roots.change(roots[0],material_hashes=(original.canonical_hash,))
            self.assertEqual(f.source(roots[0]).binding_hash,original.binding_hash)
            self.assertFalse(f.absorption.memory_current(memory))
            f.reopen(); service=UnfinishedItemService(f.core)
            f.next_round(); context=f.last_context
            before=tree_inventory_hash(f.base.runtime.data_root)
            self.assertEqual(service.ready(context),())
            self.assertEqual(service.read(context)['source_status']['external-matter'],
                             'SOURCE_NOT_CURRENT')
            self.assertEqual(tree_inventory_hash(f.base.runtime.data_root),before)
            f.base.revoke()
            revoked_before=tree_inventory_hash(f.base.runtime.data_root)
            with self.assertRaises(StateEvolutionError):
                service.ready(context)
            self.assertEqual(tree_inventory_hash(f.base.runtime.data_root),revoked_before)


if __name__=='__main__': unittest.main()
