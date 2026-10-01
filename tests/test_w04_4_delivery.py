"""Current evidence of delivery; no arrival/read claims inferred from silence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.domain.environment_access import EnvironmentAccessError


class DeliveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='w44-delivery-')
        self.f = W04EntryFixture(Path(self.temp.name))

    def tearDown(self):
        capture_failure(self, Path(self.temp.name))
        self.temp.cleanup()

    def test_sent_delivery_read_evidence_and_readonly_reopen(self):
        f = self.f
        f.submit('只记录有证据的投递状态。')
        original = f.last_request['requestId']
        send = f.entries.inspect(original)['deliveries'][0]['request_id']
        self.assertEqual(f.entries.inspect(original)['deliveries'][0]['delivered'], 'NO_EVIDENCE')
        f.delivery_notice('entry:A', send, 'DELIVERED')
        query = f.query_delivery('entry:A', send, 'query:delivered')
        view = f.entries.inspect(original, evidence_requests=(query.capability_request_id,))['deliveries'][0]
        self.assertEqual((view['status'], view['delivered'], view['read'], view['reply']),
                         ('SENT', 'EVIDENCED', 'NO_EVIDENCE', 'UNANSWERED'))
        f.delivery_notice('entry:A', send, 'READ')
        second = f.query_delivery('entry:A', send, 'query:read')
        f.reopen()
        before = tree_inventory_hash(f.runtime.data_root)
        for _ in range(2):
            view = f.entries.inspect(original, evidence_requests=(second.capability_request_id, second.capability_request_id))['deliveries'][0]
            self.assertEqual((view['delivered'], view['read']), ('EVIDENCED', 'EVIDENCED'))
            self.assertEqual(len(view['observations']), 2)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)
        self.assertEqual((f.ports['entry:A'].credits, f.ports['entry:A'].effect_count), (1, 1))
        self.assertEqual(f.provider.inputs, [])

    def test_evidence_current_source_withdrawal_and_permission_rejection(self):
        f=self.f; f.submit('合法外部观察才可使用。'); original=f.last_request['requestId']
        send=f.entries.inspect(original)['deliveries'][0]['request_id']
        f.delivery_notice('entry:A', send, 'READ')
        query=f.query_delivery('entry:A', send, 'query:read')
        f.read_allowed=False
        with self.assertRaises(EnvironmentAccessError):
            f.entries.inspect(original, evidence_requests=(query.capability_request_id,))
        f.read_allowed=True; f.ports['entry:A'].change(history=[])
        from continuity_engine.domain.execution import ExecutionError
        with self.assertRaisesRegex(ExecutionError, 'DEVICE_SOURCE_NOT_CURRENT'):
            f.entries.inspect(original, evidence_requests=(query.capability_request_id,))
        self.assertEqual((f.ports['entry:A'].credits, f.ports['entry:A'].effect_count), (1,1))

    def test_send_receipt_cannot_substitute_for_read_observation(self):
        f=self.f; f.submit('发送不等于已读。'); original=f.last_request['requestId']
        send=f.entries.inspect(original)['deliveries'][0]['request_id']
        with self.assertRaisesRegex(EnvironmentAccessError, 'EVIDENCE_QUERY_REQUIRED'):
            f.entries.inspect(original, evidence_requests=(send,))

    def test_formed_matter_adoption_recovers_once_via_original_w03_without_rebinding_context(self):
        f=self.f; f.submit('周六选河边店还是山坡店？')
        original=f.last_request['requestId']; f.entries.adopt_matter(original); before=f.state.revision
        rows=f.state.continuity.item_records
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_roots'], ['input:'+original])
        f.reopen(); f.entries.adopt_matter(original)
        self.assertEqual(f.state.revision,before)
        self.assertEqual(f.ports['entry:A'].effect_count,1)
        self.assertEqual(f.provider.inputs,[])
        from continuity_engine.domain.errors import IntegrationExecutionError
        with self.assertRaises(IntegrationExecutionError):
            f.entries.receive(f.last_request, f.last_message)
        self.assertEqual((f.state.revision,f.ports['entry:A'].effect_count), (before,1))


if __name__ == '__main__':
    unittest.main()
