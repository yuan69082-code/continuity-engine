"""W02's accepted pre-answer boundary under the previously blocked load."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.errors import IntegrationExecutionError, IntegrationPersistenceError
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from continuity_engine.domain.integration_hashing import calculate_content_hash
from continuity_engine.testing.w02_c_fixture import W02CFixture


class W02RecallTimeoutTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='w02-rt-')
        self.addCleanup(temp.cleanup)
        self.f = W02CFixture(Path(temp.name))
        self.f.base.core_options['gates'] = ContinuityCoreGates(
            input_processing=True, automatic_recall=True)
        self.f.base.core_options['context_budget'] = ContextBudget(token_limit=8192)
        self.f.reopen()

    def request(self, content='我又在吃螺蛳粉。'):
        f = self.f
        f.base.runtime.clock.advance(timedelta(seconds=1))
        request = f.base.request()
        fact = request['platformFactPackage']['facts'][0]
        fact['content'] = content
        fact['contentHash'] = calculate_content_hash(content)
        request['requestHash'] = calculate_request_hash(request)
        return request

    def send(self, content='我又在吃螺蛳粉。'):
        request = self.request(content)
        self.f.submit(request)
        return request

    def hook(self, index, content, roots=('external:root-one', 'external:root-two')):
        self.f.base.fake.candidate_hook = lambda item: replace(
            item, source_id=f'item:meal-material-{index}', roots=roots,
            content=content, content_hash=digest(content))

    def test_four_materials_preanswer_with_original_1000ms_policy(self):
        f = self.f
        f.base.base.event('old-meal', content='我去年吃过螺蛳粉。')
        contents = ('螺蛳粉原文：仍可读取。', '螺蛳粉派生材料：之后撤回。',
                    '螺蛳粉的转述资料：保留来源。', '螺蛳粉的摘要材料：不构成独立根。')
        requests = []
        for index, content in enumerate(contents):
            self.hook(index, content)
            requests.append(self.send())
        self.assertEqual(len(f.base.fake.facts()), 4)
        self.assertEqual(len(f.base.provider.inputs), 4)
        last = f.base.app.ledger.load_operation(requests[-1]['requestId'])
        recall = last.domain_progress.recall_progress[-1]
        self.assertEqual((recall['status'], recall['model_calls'], recall['external_calls']),
                         ('READY', 0, 0))
        self.assertEqual(recall['policy']['latency_ms'], 1000)
        self.assertLess(recall['elapsed_ms'], 1000)
        self.assertEqual(f.base.provider.inputs[-1].continuity_context, f.last_context)
        sources = {fragment.source_id for fragment in f.last_context.composition.snapshot.fragments}
        self.assertIn('engine.current-input', sources)
        self.assertIn('engine.memory', sources)
        # The four renderings share the same roots. Original W02-C rules may
        # withhold conflicting external candidates; receipt != reply fact.
        self.assertGreaterEqual(f.base.external.projection_audit['candidate_count'], 1)

    def test_third_message_sixteen_candidates_and_current_derived_sources(self):
        f = self.f
        original, derived = '螺蛳粉原文：仍可读取。', '螺蛳粉派生材料：之后撤回。'
        roots = ('external:root-one', 'external:root-two')
        for index, content in enumerate((original, derived)):
            self.hook(index, content, roots)
            self.send()
        candidate = next(item for _, result, _ in f.base.external.absorbed()
                         for item in result.candidates if item.content_hash == digest(derived))
        memory = f.absorption.adopt_corroborated(candidate.source_id, digest(derived),
                                                  reason='Two current independent TEST roots').memory
        summary = f.core.consolidation.generate_summary(
            f.state.subject_id, summary_id='w02-timeout-derived-summary',
            summary_type='external-observation', scope='external-observation',
            confidence=0.7, source_memory_ids=[memory.memory_id])
        request = self.send()
        recall = f.base.app.ledger.load_operation(request['requestId']).domain_progress.recall_progress[-1]
        self.assertEqual((recall['status'], recall['retrieved_count'], recall['policy']['latency_ms']),
                         ('READY', 16, 1000))
        self.assertTrue(any(fragment.stable_source_id in (memory.memory_id, summary.summary_id)
                            for fragment in f.last_context.composition.snapshot.fragments))
        old_context = f.last_context
        for root in roots:
            f.roots.change(root, material_hashes=(digest(original),))
        self.assertFalse(f.core.current(old_context))
        self.assertFalse(f.absorption.memory_current(memory))
        self.assertFalse(f.absorption.summary_current(summary, f.core.memory))
        effects = f.base.fake.facts()
        f.base.fake.root_sink = None
        f.reopen()
        self.send()
        self.assertFalse(any(fragment.stable_source_id in (memory.memory_id, summary.summary_id)
                             or fragment.source_type == 'external_candidate' and derived in fragment.content
                             for fragment in f.last_context.composition.snapshot.fragments))
        self.assertEqual(len(f.base.fake.facts()), len(effects) + 1)

    def test_scoped_capability_parse_rechecks_bytes_and_returns_private_copies(self):
        self.hook(0, '螺蛳粉原文：仍可读取。')
        self.send()
        ledger = self.f.base.app.ledger
        path = ledger.capability_path
        original = path.read_bytes()
        with ledger._verified_capability_reads():
            requests, attempts = ledger._load_capability_document()
            self.assertTrue(requests)
            requests.clear()
            attempts.clear()
            self.assertTrue(ledger._load_capability_document()[0])
            try:
                path.write_bytes(original + b'\n')
                self.assertTrue(ledger._load_capability_document()[0])
                path.write_bytes(b'{')
                with self.assertRaises(IntegrationPersistenceError):
                    ledger._load_capability_document()
            finally:
                path.write_bytes(original)
            self.assertTrue(ledger._load_capability_document()[0])
        self.assertEqual(path.read_bytes(), original)

    def test_permission_revoked_between_external_retrieval_and_revalidation(self):
        self.hook(0, '螺蛳粉原文：仍可读取。')
        self.send()
        f = self.f
        source = next(b.source for b in f.core.router._bindings
                      if b.source.source_id == 'engine.external-candidates')
        original = source.revalidate
        request = self.request()
        effects = f.base.fake.facts()
        invoked = []
        def revoke(*args):
            invoked.append(True)
            f.base.revoke()
            return original(*args)
        with patch.object(source, 'revalidate', side_effect=revoke):
            with self.assertRaises(IntegrationExecutionError):
                f.submit(request)
        self.assertTrue(invoked)
        self.assertEqual(f.base.fake.facts(), effects)
        operation = f.base.app.ledger.load_operation(request['requestId'])
        context = operation.domain_progress.perception.continuity_context
        self.assertFalse(any(fragment.source_id == 'engine.external-candidates'
                             for fragment in context.composition.snapshot.fragments))

    def test_capability_bytes_change_during_revalidation_blocks_old_candidate(self):
        self.hook(0, '螺蛳粉原文：仍可读取。')
        self.send()
        f = self.f
        source = next(b.source for b in f.core.router._bindings
                      if b.source.source_id == 'engine.external-candidates')
        original = source.revalidate
        ledger = f.base.app.ledger
        path = ledger.capability_path
        original_bytes = path.read_bytes()
        request = self.request()
        effects = f.base.fake.facts()
        invoked = []
        restored = []
        def corrupt(*args):
            invoked.append(True)
            path.write_bytes(b'{')
            try:
                return original(*args)
            finally:
                path.write_bytes(original_bytes)
                restored.append(path.read_bytes() == original_bytes)
        with patch.object(source, 'revalidate', side_effect=corrupt):
            f.submit(request)
        self.assertTrue(invoked)
        self.assertEqual(restored, [True])
        self.assertTrue(ledger._load_capability_document()[0])
        self.assertEqual(len(f.base.fake.facts()), len(effects) + 1)
        operation = f.base.app.ledger.load_operation(request['requestId'])
        context = operation.domain_progress.perception.continuity_context
        self.assertFalse(any(fragment.source_id == 'engine.external-candidates'
                             for fragment in context.composition.snapshot.fragments))


if __name__ == '__main__':
    unittest.main()
