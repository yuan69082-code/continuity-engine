"""W04-4 real C1/P13/P17/E5-A entry, identity, transfer and recovery tests."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import tempfile
import unittest

from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.domain.errors import IntegrationExecutionError


class CrossEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='w04-4-')
        self.root = Path(self.temp.name)
        self.f = W04EntryFixture(self.root)

    def tearDown(self):
        capture_failure(self, self.root)
        if self._outcome and not self._outcome.success:
            import sys
            for operation in self.f.app.ledger.list_operations():
                progress = operation.domain_progress
                for record in progress.recall_progress if progress else ():
                    print(json.dumps({'test': self.id(), 'request': operation.request_id,
                        'recall': {key: record[key] for key in ('status', 'stop_reason', 'elapsed_ms', 'retrieved_count')}}), file=sys.stderr)
        self.temp.cleanup()

    def begin(self):
        result = self.f.submit('周六选河边店还是山坡店？')
        self.assertEqual(result.status, 'completed')
        request = self.f.last_request
        item = self.f.entries.adopt_matter(request['requestId'])
        return request, item

    def chain(self, ui=False):
        self.f.api_available = not ui
        first, item = self.begin()
        follow_id = self.f.continue_native()
        follow = {'requestId': follow_id}
        self.assertIsNone(self.f.app.ledger.load_operation(follow_id))
        self.assertEqual(self.f.provider.inputs[-1].external_facts, ())
        self.assertEqual(self.f.ports['entry:B'].store.load()['view']['sent'], item.title)
        view = self.f.entries.inspect(follow['requestId'])
        delivery = view['deliveries'][0]
        self.assertEqual((delivery['status'], delivery['reply'], delivery['delivered'], delivery['read']),
                         ('SENT', 'UNANSWERED', 'NO_EVIDENCE', 'NO_EVIDENCE'))
        sealed = self.f.app.ledger.load_capability_request(delivery['request_id'])
        self.assertIn('.ui:' if ui else '.api:', sealed.capability_type)
        self.f.advance()
        self.f.native_mode = False
        self.f.reopen()
        response = self.f.submit('选河边店，窗边那张桌。', entry='entry:B', item_id=item.item_id,
                                reply_to=delivery['request_id'])
        self.assertIn(item.title, response.response.content)
        self.assertIn('河边店', response.response.content)
        self.assertEqual(self.f.entries.inspect(follow['requestId'])['deliveries'][0]['reply'], 'ANSWER_RECORDED')
        self.assertEqual(self.f.state.subject_id, item.subject_id)
        self.assertEqual([r['item_id'] for r in self.f.state.continuity.item_records], [item.item_id])
        self.assertEqual((self.f.ports['entry:A'].effect_count, self.f.ports['entry:B'].effect_count), (1, 2))
        return first, follow, item

    def test_api_question_followup_reply_same_engine_and_matter(self):
        self.chain()

    def test_simulated_ui_question_followup_reply_same_engine_and_matter(self):
        self.chain(ui=True)

    def test_wrong_sender_and_same_display_name_do_not_grant_identity(self):
        request, message = self.f.message('你好')
        before = self.f.state.revision
        with self.assertRaises(IntegrationExecutionError):
            self.f.entries.receive(request, replace(message, sender_account='user-account:unbound'))
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual(self.f.state.revision, before)
        self.assertEqual(self.f.provider.inputs, [])

    def test_binding_change_after_thinking_prevents_delivery(self):
        self.f.provider.before_return = lambda: self.f.configure('entry:A', can_initiate=False)
        with self.assertRaises(IntegrationExecutionError):
            self.f.submit('周六去哪家店？')
        self.assertEqual(self.f.ports['entry:A'].effect_count, 0)
        self.assertEqual(self.f.ports['entry:A'].credits, 0)

    def test_pause_at_a_blocks_b_without_disabling_internal_state(self):
        _, item = self.begin()
        self.f.entries.pause_contact('entry:A', True, expected_revision=self.f.repo.load()['revision'])
        before = self.f.state.revision
        self.f.continue_native()
        self.assertEqual(self.f.ports['entry:B'].effect_count, 0)
        self.assertEqual(len(self.f.state.continuity.item_records), 1)
        self.assertGreater(self.f.state.revision, before)

    def test_mirror_deduplicates_original_operation_and_effect(self):
        self.f.submit('同一条关于河边店的消息。')
        first = self.f.last_request
        before = self.f.state.revision
        count = len(self.f.provider.inputs)
        request, message = self.f.message('同一条关于河边店的消息。', entry='entry:B', mirror_of=first['requestId'])
        view = self.f.entries.receive(request, message)
        self.assertEqual(view['status'], 'DUPLICATE_SOURCE')
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual((self.f.state.revision, len(self.f.provider.inputs)), (before, count))

    def test_original_request_reopen_has_no_new_model_effect_or_revision(self):
        self.f.submit('周六去哪家店？')
        request, message = self.f.last_request, self.f.last_message
        before = (self.f.state.revision, self.f.ports['entry:A'].credits, self.f.ports['entry:A'].effect_count)
        self.f.reopen()
        self.f.entries.receive(request, message)
        self.assertEqual(len(self.f.provider.inputs), 0)
        self.assertEqual((self.f.state.revision, self.f.ports['entry:A'].credits, self.f.ports['entry:A'].effect_count), before)

    def test_no_transfer_permission_keeps_other_authorized_entry_material(self):
        self.f.submit('A入口的私密选店资料。')
        self.f.configure('entry:B', read_from=('entry:B',))
        self.f.advance()
        self.f.submit('B入口自己的选店信息。', entry='entry:B')
        strings = [f.content for f in self.f.provider.inputs[-1].continuity_context.composition.snapshot.fragments]
        self.assertNotIn('A入口的私密选店资料。', '\n'.join(strings))
        self.assertIn('B入口自己的选店信息。', '\n'.join(strings))

    def test_verified_environment_parse_returns_private_copy_and_rechecks_bytes(self):
        from continuity_engine.domain.environment_access import EnvironmentAccessError
        before = self.f.repo.load()
        local = self.f.repo.load()
        local['entry_bindings'][0]['can_receive'] = False
        self.assertEqual(self.f.repo.load(), before)
        raw = self.f.repo.path.read_bytes()
        self.f.repo.path.write_bytes(raw[:-1] + b'x')
        with self.assertRaises(EnvironmentAccessError):
            self.f.repo.load()
        self.f.repo.path.write_bytes(raw)  # Controlled TEST fixture only.
        self.assertEqual(self.f.repo.load(), before)

    def test_current_permission_is_not_cached_with_environment_parse(self):
        self.f.entries.binding('entry:A')
        self.f.read_allowed = False
        request, message = self.f.message('有权限才可接收。')
        with self.assertRaises(IntegrationExecutionError):
            self.f.entries.receive(request, message)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual(self.f.provider.inputs, [])

    def test_subject_echo_never_becomes_user_reply_or_new_thinking(self):
        self.f.submit('这是原始用户材料。')
        original = self.f.last_request['requestId']
        delivery = self.f.entries.inspect(original)['deliveries'][0]
        body = self.f.ports['entry:A'].store.load()['view']['sent']
        before = (len(self.f.provider.inputs), self.f.state.revision, self.f.ports['entry:A'].effect_count)
        request, message = self.f.message(body, role='SUBJECT_ECHO', reply_to=delivery['request_id'])
        result = self.f.entries.receive(request, message)
        self.assertEqual(result['status'], 'SUBJECT_ECHO')
        self.assertEqual((len(self.f.provider.inputs), self.f.state.revision, self.f.ports['entry:A'].effect_count), before)
        self.assertEqual(self.f.entries.inspect(original)['deliveries'][0]['reply'], 'UNANSWERED')

    def test_readonly_delivery_view_reopen_does_not_advance_work(self):
        from continuity_engine.testing.persistence import tree_inventory_hash
        self.f.submit('只读查看原有投递。')
        request = self.f.last_request['requestId']
        view = self.f.entries.inspect(request)
        self.f.reopen()
        before = tree_inventory_hash(self.f.runtime.data_root)
        self.assertEqual(self.f.entries.inspect(request), view)
        self.assertEqual(self.f.entries.inspect(request), view)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root), before)
        self.assertEqual(self.f.provider.inputs, [])

    def test_disconnected_and_expired_entries_reject_without_new_operation(self):
        request, message = self.f.message('检查入口。')
        self.f.base.online = False
        with self.assertRaises(IntegrationExecutionError):
            self.f.entries.receive(request, message)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.f.base.online = True
        self.f.runtime.clock.advance(timedelta(hours=2))
        with self.assertRaises(IntegrationExecutionError):
            self.f.entries.receive(request, message)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))


if __name__ == '__main__':
    unittest.main()
