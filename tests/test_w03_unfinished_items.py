"""N06 uses the original SubjectState and Action/Evolution audit."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import StateEvolutionError
from continuity_engine.domain.events import EventClassification, EventReference, EventRelationType
from continuity_engine.domain.unfinished_item import UnfinishedItem
from continuity_engine.services.unfinished_item_service import UnfinishedItemService
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class W03UnfinishedItemTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='w03-items-')
        self.addCleanup(temp.cleanup)
        self.f=P09Fixture(Path(temp.name))
        self.f.event('w03-root',content='Synthetic subject intends a local matter.')
        self.service=UnfinishedItemService(self.f.core,action_repository=self.f.app.ledger,
                                           receipt_verifier=self.f.adapter)

    def context(self):
        request=self.f.request()
        self.f.submit(request)
        return self.f.context(request)

    def item(self, name='one', **changes):
        at=self.f.runtime.clock.now().isoformat().replace('+00:00','Z')
        fields=dict(item_id=name,subject_id=self.f.runtime.descriptor.subject_id,
            environment='TEST',title='Synthetic '+name,source_roots=('event:w03-root',),
            willing=True,importance_reason='Subject chose to keep this matter in view.',
            urgency='NORMAL',due_at=None,wait_condition=None,next_step='Review local evidence',
            status='OPEN',created_at=at,updated_at=at,revision=0,completion=None,last_progress=None)
        return UnfinishedItem(**{**fields,**changes})

    def test_create_replay_restart_and_read_only_view(self):
        f=self.f; item=self.item(); context=self.context()
        before=f.runtime.subject_state().revision
        update=self.service.submit(item,command_id='create-one',expected_revision=before,
                                   context=context,reason='Bounded local intention')
        after=f.runtime.subject_state().revision
        self.assertEqual(after,before+1)
        self.assertEqual(self.service.submit(item,command_id='create-one',expected_revision=before,
                                             context=context,reason='Bounded local intention').update_id,
                         update.update_id)
        self.assertEqual(f.runtime.subject_state().revision,after)
        with self.assertRaises(StateEvolutionError):
            self.service.read(context)
        f.reopen(); self.service=UnfinishedItemService(f.core,action_repository=f.app.ledger,
                                                       receipt_verifier=f.adapter)
        fresh=self.context()
        inventory=tree_inventory_hash(f.runtime.data_root)
        view=self.service.read(fresh)
        self.assertEqual(view['items'][0]['item_id'],'one')
        self.assertEqual(view['change_history'][0]['reason'],'Bounded local intention')
        self.assertEqual(view['change_count'],1)
        self.assertEqual(self.service.ready(fresh)[0].item_id,'one')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),inventory)

    def test_blocked_urgent_does_not_starve_normal_and_identity_is_stable(self):
        f=self.f
        urgent=self.item('urgent',urgency='URGENT',status='WAITING',wait_condition='Await local result')
        self.service.submit(urgent,command_id='create-urgent',expected_revision=f.runtime.subject_state().revision,
                            context=self.context(),reason='Local waiting matter')
        normal=self.item('normal')
        self.service.submit(normal,command_id='create-normal',expected_revision=f.runtime.subject_state().revision,
                            context=self.context(),reason='Local ordinary matter')
        fresh=self.context()
        self.assertEqual([item.item_id for item in self.service.ready(fresh)],['normal'])
        self.assertEqual([item.item_id for item in self.service.ready(fresh,
                         wait_satisfied=lambda item:True)],['urgent','normal'])
        newer=replace(urgent,revision=1,urgency='LOW',status='OPEN',wait_condition=None,
                      updated_at=f.runtime.clock.now().isoformat().replace('+00:00','Z'))
        self.service.submit(newer,command_id='release-urgent',expected_revision=f.runtime.subject_state().revision,
                            context=fresh,reason='Waiting condition verified')
        records=f.runtime.subject_state().continuity.item_records
        self.assertEqual(len(records),2)
        self.assertEqual(next(item for item in records if item['item_id']=='urgent')['urgency'],'LOW')

    def test_unverified_completion_and_stale_revision_fail_without_write(self):
        f=self.f; item=self.item(); context=self.context()
        revision=f.runtime.subject_state().revision
        bad=replace(item,status='COMPLETED',completion={'kind':'ACTION_RECEIPT',
            'identity':'missing','hash':'sha256:'+'0'*64})
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(StateEvolutionError):
            self.service.submit(bad,command_id='bad-complete',expected_revision=revision,
                                context=context,reason='No real receipt')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.service.submit(item,command_id='create',expected_revision=revision,
                            context=context,reason='Create matter')
        with self.assertRaises(StateEvolutionError):
            self.service.submit(self.item('other'),command_id='stale',expected_revision=revision,
                                context=context,reason='Stale matter')

    def test_verified_effect_completes_once_and_cancel_is_terminal(self):
        f=self.f; context=self.context(); request=f.core.last_action.requests[0]
        result=f.core.last_action.results[0]
        self.assertEqual(result.status.value,'SUCCEEDED')
        item=self.item('effect')
        revision=f.runtime.subject_state().revision
        self.service.submit(item,command_id='effect-create',expected_revision=revision,
                            context=context,reason='Intended test action')
        context=self.context()
        completed=replace(item,revision=1,status='COMPLETED',
            completion={'kind':'ACTION_RECEIPT','identity':request.capability_request_id,
                        'hash':result.receipt.canonical_hash()},
            updated_at=f.runtime.clock.now().isoformat().replace('+00:00','Z'))
        revision=f.runtime.subject_state().revision
        update=self.service.submit(completed,command_id='effect-complete',expected_revision=revision,
                                   context=context,reason='Verified original E5-A result')
        self.assertEqual(self.service.submit(completed,command_id='effect-complete',
            expected_revision=revision,context=context,
            reason='Verified original E5-A result').update_id,update.update_id)
        self.assertEqual(len(f.adapter.receipts()),2)  # Two separate normal C1 rounds, no item-effect replay.
        self.assertNotIn('Synthetic effect',
            [title for title in __import__('continuity_engine.domain.unfinished_item',fromlist=['active_titles']).active_titles(
                f.runtime.subject_state().continuity)])
        with self.assertRaises(StateEvolutionError):
            self.service.submit(replace(completed,revision=2,status='CANCELLED',completion=None),
                command_id='terminal-backwards',expected_revision=f.runtime.subject_state().revision,
                reason='Cannot move terminal result')

    def test_internal_result_must_bind_the_same_item_not_its_creation(self):
        from continuity_engine.domain.events import Event, StateSection
        f=self.f;item=self.item('local')
        self.service.submit(item,command_id='local-create',
            expected_revision=f.runtime.subject_state().revision,context=self.context(),
            reason='Local matter')
        item_create=next(u.event for u in f.runtime.subject_states.get_update_history(
            f.runtime.descriptor.subject_id) if u.event.metadata.get('item_id')=='local')
        with self.assertRaises(StateEvolutionError):
            self.service.submit(replace(item,revision=1,status='COMPLETED',
                completion={'kind':'INTERNAL_EVENT','identity':item_create.event_id,
                            'hash':item_create.canonical_hash()}),
                command_id='false-local-result',expected_revision=f.runtime.subject_state().revision,
                context=self.context(),reason='Creation is not completion')
        now=f.runtime.clock.now()
        fact=Event.create(event_id='w03-local-result',occurred_at=now,source='w03.synthetic-result',
            event_type='local_result',content='Isolated verified local result.',
            impact_scope=[StateSection.CONTINUITY],classification=EventClassification.FACT,
            mutations=[],reason='Original local result evidence',
            metadata={'w03_item_result':'local'})
        f.runtime.subject_states.apply_event(f.runtime.descriptor.subject_id,fact)
        completed=replace(item,revision=1,status='COMPLETED',
            completion={'kind':'INTERNAL_EVENT','identity':fact.event_id,
                        'hash':fact.canonical_hash()})
        revision=f.runtime.subject_state().revision
        self.service.submit(completed,command_id='verified-local-result',
            expected_revision=revision,context=self.context(),reason='Bound original result')
        self.assertEqual(self.service.ready(self.context()),())

    def test_older_low_priority_eventually_passes_continuous_urgent_arrivals(self):
        f=self.f
        old=self.item('old',urgency='LOW',created_at=(f.runtime.clock.now()-timedelta(hours=12))
                      .isoformat().replace('+00:00','Z'))
        self.service.submit(old,command_id='old-create',expected_revision=f.runtime.subject_state().revision,
                            context=self.context(),reason='Old ordinary matter')
        urgent=self.item('new',urgency='URGENT')
        self.service.submit(urgent,command_id='new-create',expected_revision=f.runtime.subject_state().revision,
                            context=self.context(),reason='Later urgent matter')
        self.assertEqual([item.item_id for item in self.service.ready(self.context())],['old','new'])

    def test_future_deadline_does_not_hide_actionable_matter(self):
        f=self.f
        deadline=(f.runtime.clock.now()+timedelta(hours=1)).isoformat().replace('+00:00','Z')
        self.service.submit(self.item('deadline',due_at=deadline),
            command_id='deadline-create',expected_revision=f.runtime.subject_state().revision,
            context=self.context(),reason='Deadline does not mean wait until due')
        self.assertEqual([item.item_id for item in self.service.ready(self.context())],
                         ['deadline'])
        distant=(f.runtime.clock.now()+timedelta(days=7)).isoformat().replace('+00:00','Z')
        self.service.submit(self.item('distant',due_at=distant),
            command_id='distant-create',expected_revision=f.runtime.subject_state().revision,
            context=self.context(),reason='Same urgency, later deadline')
        self.assertEqual([item.item_id for item in self.service.ready(self.context())],
                         ['deadline','distant'])

    def test_defer_due_and_cancel_keep_one_identity_without_dispatch(self):
        f=self.f;item=self.item('later',status='DEFERRED')
        self.service.submit(item,command_id='later-create',
            expected_revision=f.runtime.subject_state().revision,context=self.context(),
            reason='Subject deferred matter')
        self.assertEqual(self.service.ready(self.context()),())
        delayed=replace(item,revision=1,status='OPEN',
            due_at=(f.runtime.clock.now()+timedelta(hours=1)).isoformat().replace('+00:00','Z'))
        self.service.submit(delayed,command_id='later-resume',
            expected_revision=f.runtime.subject_state().revision,context=self.context(),
            reason='Subject chose later opportunity')
        self.assertEqual([record.item_id for record in self.service.ready(self.context())],['later'])
        f.runtime.clock.advance(timedelta(hours=2))
        self.assertEqual([record.item_id for record in self.service.ready(self.context())],['later'])
        cancelled=replace(delayed,revision=2,status='CANCELLED',
            updated_at=f.runtime.clock.now().isoformat().replace('+00:00','Z'))
        revision=f.runtime.subject_state().revision
        result=self.service.submit(cancelled,command_id='later-cancel',
            expected_revision=revision,context=self.context(),reason='Subject cancelled matter')
        self.assertEqual(self.service.submit(cancelled,command_id='later-cancel',
            expected_revision=revision,reason='Subject cancelled matter').update_id,result.update_id)
        view=self.service.read(self.context())
        self.assertEqual(view['items'][0]['status'],'CANCELLED')
        self.assertEqual(view['change_count'],3)
        self.assertEqual(self.service.ready(self.context()),())

    def test_two_writers_with_one_revision_accept_one_item_only(self):
        from concurrent.futures import ThreadPoolExecutor
        f=self.f;context=self.context();revision=f.runtime.subject_state().revision
        before=tree_inventory_hash(f.runtime.data_root)
        def attempt(name):
            try:
                self.service.submit(self.item(name),command_id='parallel-'+name,
                    expected_revision=revision,context=context,reason='Concurrent bounded matter')
                return 'SAVED'
            except StateEvolutionError:
                return 'REJECTED'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(attempt,('one','two')))
        self.assertCountEqual(outcomes,['SAVED','REJECTED'])
        self.assertEqual(f.runtime.subject_state().revision,revision+1)
        self.assertEqual(len(f.runtime.subject_state().continuity.item_records),1)
        self.assertNotEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_revoked_source_stops_new_opportunity_but_keeps_item_history(self):
        f=self.f
        self.service.submit(self.item('rooted'),command_id='rooted-create',
            expected_revision=f.runtime.subject_state().revision,context=self.context(),
            reason='Current original source')
        f.event('root-revoked',classification=EventClassification.REVOCATION,
            references=(EventReference('w03-root',f.runtime.descriptor.subject_id,
                                       EventRelationType.REVOKES),))
        fresh=self.context()
        self.assertEqual(self.service.read(fresh)['items'][0]['item_id'],'rooted')
        self.assertEqual(self.service.ready(fresh),())

    def test_read_rechecks_permission_before_return_without_writing(self):
        from unittest.mock import patch
        f=self.f;context=self.context()
        before=tree_inventory_hash(f.runtime.data_root)
        original=f.core.subject_states.get_update_history
        def revoke(subject_id):
            rows=original(subject_id)
            f.permission.references_allowed=False
            return rows
        with patch.object(f.core.subject_states,'get_update_history',side_effect=revoke):
            with self.assertRaises(StateEvolutionError):
                self.service.read(context)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_atomic_storage_failure_and_legacy_serialization(self):
        from unittest.mock import patch
        from continuity_engine.domain.models import SubjectState
        f=self.f
        legacy=SubjectState.create('legacy',now=f.runtime.clock.now()).to_dict()
        self.assertNotIn('item_records',legacy['continuity'])
        self.assertEqual(SubjectState.from_dict(legacy).to_dict(),legacy)
        context=self.context()
        before=tree_inventory_hash(f.runtime.data_root)
        with patch.object(f.core.subject_states._repository,'save_transition',
                          side_effect=OSError('synthetic isolated write failure')):
            with self.assertRaises(OSError):
                self.service.submit(self.item('failure'),command_id='store-failure',
                    expected_revision=f.runtime.subject_state().revision,context=context,
                    reason='Atomic failure evidence')
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)


if __name__=='__main__':
    unittest.main()
