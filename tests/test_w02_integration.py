"""W02 A/B/C: one normal Engine chain, source withdrawal and original recovery."""

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.errors import IntegrationExecutionError, LearningValidationError
from continuity_engine.domain.input_processing import InputDisposition
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from continuity_engine.domain.integration_hashing import calculate_content_hash
from continuity_engine.testing.persistence import tree_inventory_hash
from continuity_engine.testing.w02_c_fixture import W02CFixture
from continuity_engine.testing.w02_input_fixture import capture_failure


class W02IntegratedChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='w02-integrated-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.f = W02CFixture(self.root)
        self.f.base.core_options['gates'] = ContinuityCoreGates(
            input_processing=True, automatic_recall=True)
        self.f.base.core_options['context_budget'] = ContextBudget(token_limit=8192)
        self.f.reopen()

    def tearDown(self):
        capture_failure(self, self.root)

    @staticmethod
    def message(fixture, content):
        """Raw platform fact uses the original contract/hash path."""
        request = fixture.base.request()
        fact = request['platformFactPackage']['facts'][0]
        fact['content'] = content
        fact['contentHash'] = calculate_content_hash(content)
        request['requestHash'] = calculate_request_hash(request)
        return request

    def send(self, content):
        self.f.base.runtime.clock.advance(timedelta(seconds=1))
        request = self.message(self.f, content)
        self.f.submit(request)
        return request

    def partial_memory_request(self):
        request = self.message(self.f, '我又在吃螺蛳粉。')
        with patch.object(self.f.core, '_consolidate_events',
                          side_effect=OSError('TEST_MEMORY_STAGE_FAILURE')):
            with self.assertRaises(IntegrationExecutionError):
                self.f.submit(request)
        self.assertEqual(self.f.base.app.adapter.service.input_outcome(request['requestId'])['resume_stations'],
                         ['memory'])
        self.assertEqual((len(self.f.base.provider.inputs), self.f.base.fake.facts()), (0, []))
        return request

    @staticmethod
    def external(context):
        return [item for item in context.composition.snapshot.fragments
                if item.source_type == 'external_candidate']

    def test_raw_message_stations_old_memory_receipt_and_final_preanswer_context(self):
        f = self.f
        f.base.base.event('old-meal', content='我去年吃过螺蛳粉。')
        content = '螺蛳粉资料：这是一份有来源的本地 TEST 记录。'
        f.base.fake.candidate_hook = lambda item: replace(
            item, source_id='item:meal-reference', content=content,
            content_hash=digest(content))
        first = self.send('我又在吃螺蛳粉。')
        first_operation = f.base.app.ledger.load_operation(first['requestId'])
        first_input = first_operation.domain_progress.input_processing
        self.assertEqual(first_input.manifest['request_id'], first['requestId'])
        self.assertEqual(first_input.latest('conversation').disposition, InputDisposition.TEMP_USE)
        self.assertEqual(first_input.latest('memory').disposition, InputDisposition.NEEDS_EVIDENCE)
        self.assertEqual(first_operation.domain_progress.perception.continuity_context.recall['status'], 'READY')
        first_action = f.core.last_action.requests[0]
        self.assertEqual(len(f.base.fake.facts()), 1)
        self.assertEqual(f.absorption.outcome(first_action.capability_request_id)['decisions'][0]['disposition'],
                         'CANDIDATE')

        second = self.send('我又在吃螺蛳粉。')
        context = f.last_context
        self.assertEqual(context.recall['status'], 'READY')
        self.assertFalse(context.recall['assessment']['frames'][0]['verified_fact'])
        self.assertTrue(any(fragment.source_id == 'engine.current-input'
                            for fragment in context.composition.snapshot.fragments))
        self.assertTrue(any('去年吃过螺蛳粉' in fragment.content
                            for fragment in context.composition.snapshot.fragments
                            if fragment.source_type == 'memory_record'))
        external = self.external(context)
        self.assertTrue(external)
        material = json.loads(external[0].content)
        self.assertEqual(material['request_id'], first_action.capability_request_id)
        self.assertEqual(material['candidate']['content'], content)
        self.assertEqual(f.base.provider.inputs[1].continuity_context, context)
        self.assertEqual(f.base.app.adapter.service.input_outcome(second['requestId'])['status'], 'COMPLETED')
        self.assertEqual(f.base.app.adapter.service.recall_outcome(second['requestId'])['status'], 'READY')
        print(json.dumps({
            'first_message': first['requestId'], 'second_message': second['requestId'],
            'first_input_stations': list(first_input.manifest['stations']),
            'first_memory_decision': first_input.latest('memory').reason,
            'recall_stop': context.recall['stop_reason'],
            'external_request': first_action.capability_request_id,
            'external_receipt': f.base.fake.facts()[0]['receipt']['receipt_id'],
            'final_sources': [fragment.source_id for fragment in context.composition.snapshot.fragments],
            'provider_received_final_context': True,
        }, ensure_ascii=False))

    def test_unrelated_history_and_external_candidate_do_not_fill_reply(self):
        f = self.f
        f.base.base.event('unrelated', content='量子光学项目的排期。')
        content = 'Distant astronomy report about galaxies'
        f.base.fake.candidate_hook = lambda item: replace(
            item, source_id='item:astronomy', content=content, content_hash=digest(content))
        self.send('我又在吃螺蛳粉。')
        self.send('我又在吃螺蛳粉。')
        context = f.last_context
        self.assertFalse(self.external(context))
        self.assertFalse(any(fragment.stable_source_id in ('unrelated', 'memory:unrelated')
                             for fragment in context.composition.snapshot.fragments))
        self.assertTrue(any(fragment.source_id == 'engine.current-input'
                            for fragment in context.composition.snapshot.fragments))
        self.assertEqual(context.recall['external_calls'], 0)
        self.assertGreaterEqual(f.base.external.projection_audit['candidate_count'], 1)

    def test_partial_derived_withdrawal_invalidates_integrated_reply_and_support(self):
        f = self.f
        roots = ('external:root-one', 'external:root-two')
        original = '螺蛳粉原文：仍可读取。'
        derived = '螺蛳粉派生材料：之后撤回。'
        original_hash, derived_hash = digest(original), digest(derived)
        # Keep the original as each root's immutable canonical hash. One TEST
        # result may carry two independently addressable root proofs; W02-C's
        # accepted tests separately cover two acquisition requests per root.
        for content in (original, derived):
            f.base.fake.candidate_hook = lambda item, content=content: replace(
                item, source_id='item:meal-derived' if content == derived else 'item:meal-original',
                roots=roots, content=content, content_hash=digest(content))
            self.send('我又在吃螺蛳粉。')
        candidate = next(item for _, result, _ in f.base.external.absorbed()
                         for item in result.candidates if item.content_hash == derived_hash)
        memory = f.absorption.adopt_corroborated(candidate.source_id, derived_hash,
                                                  reason='Two current independent TEST roots').memory
        summary = f.core.consolidation.generate_summary(
            f.state.subject_id, summary_id='w02-integrated-derived-summary',
            summary_type='external-observation', scope='external-observation', confidence=0.7,
            source_memory_ids=[memory.memory_id])
        self.send('我又在吃螺蛳粉。')
        before = f.last_context
        self.assertTrue(any(item.stable_source_id in (memory.memory_id, summary.summary_id)
                            for item in before.composition.snapshot.fragments))
        facts = f.base.fake.facts()
        state = f.state.to_dict()
        for root in roots:
            f.roots.change(root, material_hashes=(original_hash,))
        self.assertFalse(f.core.current(before))
        self.assertFalse(f.absorption.memory_current(memory))
        self.assertFalse(f.absorption.summary_current(summary, f.core.memory))
        with self.assertRaisesRegex(LearningValidationError, 'EXTERNAL_MEMORY_SUPPORT_WITHDRAWN'):
            f.core.growth.repository.memory_support_snapshot(
                f.state.subject_id, memory.memory_id, environment='TEST')
        self.assertEqual(f.base.fake.facts(), facts)
        self.assertEqual(f.state.to_dict(), state)
        f.base.fake.root_sink = None  # A new TEST result cannot grant its own root authority.
        f.reopen()
        self.send('我又在吃螺蛳粉。')
        self.assertFalse(any(item.stable_source_id in (memory.memory_id, summary.summary_id)
                             or item.source_type == 'external_candidate' and derived in item.content
                             for item in f.last_context.composition.snapshot.fragments))
        self.assertEqual(f.state.to_dict(), state)

    def test_partial_failure_reopen_read_original_progress_and_resume_once(self):
        f = self.f
        request = self.partial_memory_request()
        service = f.base.app.adapter.service
        before_view = tree_inventory_hash(f.base.runtime.data_root)
        first_view = service.input_outcome(request['requestId'])
        self.assertEqual(first_view['status'], 'PENDING')
        self.assertIn('memory', first_view['resume_stations'])
        self.assertEqual(service.input_outcome(request['requestId']), first_view)
        self.assertEqual(tree_inventory_hash(f.base.runtime.data_root), before_view)
        f.reopen()
        self.assertEqual(f.base.app.adapter.service.input_outcome(request['requestId']), first_view)
        completed = f.submit(request)
        self.assertEqual(f.base.app.adapter.service.input_outcome(request['requestId'])['status'], 'COMPLETED')
        facts = f.base.fake.facts()
        revision = f.state.revision
        self.assertEqual(len(f.base.provider.inputs), 1)
        self.assertEqual(len(facts), 1)
        self.assertEqual(f.submit(request).to_dict(), completed.to_dict())
        self.assertEqual((len(f.base.provider.inputs), f.base.fake.facts(), f.state.revision),
                         (1, facts, revision))

    def test_failed_station_stays_pending_when_failure_repeats_then_resumes(self):
        f = self.f
        request = self.partial_memory_request()
        original = f.base.app.ledger.load_operation(request['requestId']).domain_progress.input_processing
        f.reopen()
        with patch.object(f.core, '_consolidate_events',
                          side_effect=OSError('TEST_MEMORY_STAGE_STILL_UNAVAILABLE')):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        pending = f.base.app.adapter.service.input_outcome(request['requestId'])
        self.assertEqual(pending['status'], 'PENDING')
        self.assertEqual(pending['resume_stations'], ['memory'])
        after = f.base.app.ledger.load_operation(request['requestId']).domain_progress.input_processing
        self.assertEqual([r for r in original.receipts if r.station == 'conversation'],
                         [r for r in after.receipts if r.station == 'conversation'])
        self.assertEqual([r.attempt for r in after.receipts if r.station == 'memory'], [1, 2])
        self.assertEqual((len(f.base.provider.inputs), f.base.fake.facts(), f.state.revision),
                         (0, [], 1))
        f.reopen()
        f.submit(request)
        final = f.base.app.ledger.load_operation(request['requestId']).domain_progress.input_processing
        self.assertEqual([r.attempt for r in final.receipts if r.station == 'memory'], [1, 2, 3])
        self.assertEqual(len(f.base.provider.inputs), 1)
        self.assertEqual(len(f.base.fake.facts()), 1)

    def test_recovery_rechecks_current_input_permission_before_reusing_context(self):
        f = self.f
        request = self.partial_memory_request()
        before = f.base.app.ledger.load_operation(request['requestId']).domain_progress.input_processing
        f.reopen()
        f.base.base.permission.references_allowed = False
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        after = f.base.app.ledger.load_operation(request['requestId']).domain_progress.input_processing
        self.assertEqual(after, before)
        self.assertEqual((len(f.base.provider.inputs), f.base.fake.facts(), f.state.revision),
                         (0, [], 1))

    def test_recovered_station_preserves_verified_old_event_context(self):
        f = self.f
        f.base.base.event('prior-meal', content='我去年吃过螺蛳粉。')
        request = self.partial_memory_request()
        f.reopen()
        f.submit(request)
        self.assertTrue(any('去年吃过螺蛳粉' in fragment.content
                            for fragment in f.last_context.composition.snapshot.fragments
                            if fragment.source_type == 'event'))
        self.assertTrue(any('去年吃过螺蛳粉' in memory.content
                            for memory in f.core.memory.list_memories(f.state.subject_id)))
        self.assertEqual(f.base.provider.inputs[0].continuity_context, f.last_context)

    def test_public_read_only_views_do_not_retrieve_or_execute(self):
        f = self.f
        first = self.send('我又在吃螺蛳粉。')
        second = self.send('我又在吃螺蛳粉。')
        capability_request = f.base.external.absorbed()[0][0].capability_request_id
        before = tree_inventory_hash(f.base.runtime.data_root)
        call_count = len(f.base.provider.inputs)
        effects = f.base.fake.facts()
        with patch.object(f.core.recall, 'prepare', side_effect=AssertionError('no recall')), \
             patch.object(f.base.provider, 'think', side_effect=AssertionError('no model')), \
             patch.object(f.base.fake, 'execute_query', side_effect=AssertionError('no effect')):
            self.assertEqual(f.base.app.adapter.service.input_outcome(second['requestId'])['status'], 'COMPLETED')
            self.assertEqual(f.base.app.adapter.service.recall_outcome(second['requestId'])['status'], 'READY')
            self.assertEqual(f.absorption.outcome(capability_request)['decisions'][0]['disposition'],
                             'CANDIDATE')
            self.assertEqual(f.base.app.adapter.service.input_outcome(first['requestId'])['status'], 'COMPLETED')
        self.assertEqual(tree_inventory_hash(f.base.runtime.data_root), before)
        self.assertEqual((len(f.base.provider.inputs), f.base.fake.facts()), (call_count, effects))


if __name__ == '__main__':
    unittest.main()
