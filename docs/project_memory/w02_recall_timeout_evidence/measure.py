"""Isolated, bounded W02 timing probe; no production data or source changes."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.services import associative_recall_service as recall_module
from continuity_engine.services.associative_recall_service import AssociativeRecallService
from continuity_engine.services.context_router_service import ContextRouterService
from continuity_engine.services.context_composer_service import ContextComposerService
from continuity_engine.services.input_context_source import InputContextSource, HistoricalInputContextSource
from continuity_engine.storage import json_integration_repository as journal_module
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from continuity_engine.services.external_capability_service import ExternalCapabilityService
from continuity_engine.services.external_context_source import ExternalContextSource
from continuity_engine.services.external_absorption_service import ExternalAbsorptionService
from continuity_engine.testing.w02_c_fixture import W02CFixture
from tests.test_w02_integration import W02IntegratedChainTests


def main() -> int:
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ('third', 'four'):
        raise SystemExit('measure.py third|four [instrument]')
    scenario = sys.argv[1]
    instrument = len(sys.argv) == 3 and sys.argv[2] == 'instrument'
    case = W02IntegratedChainTests('test_partial_derived_withdrawal_invalidates_integrated_reply_and_support')
    case.setUp()
    f = case.f
    measures = defaultdict(lambda: [0, 0.0])
    active = [False]
    in_recall = [False]
    stack = __import__('contextlib').ExitStack()

    def wrap(obj, name, label):
        old = getattr(obj, name)
        def timed(*args, **kwargs):
            if not active[0]:
                return old(*args, **kwargs)
            if label == 'recall_prepare':
                in_recall[0] = True
                started = time.perf_counter()
                try:
                    return old(*args, **kwargs)
                finally:
                    in_recall[0] = False
                    item = measures[label]
                    item[0] += 1
                    item[1] += (time.perf_counter() - started) * 1000
            if not in_recall[0]:
                return old(*args, **kwargs)
            started = time.perf_counter()
            try:
                return old(*args, **kwargs)
            finally:
                item = measures[label]
                item[0] += 1
                item[1] += (time.perf_counter() - started) * 1000
        stack.enter_context(patch.object(obj, name, timed))

    if instrument:
        for obj, name, label in (
            (AssociativeRecallService, '_prepare', 'recall_prepare'),
            (ContextRouterService, 'route', 'router_route'),
            (ContextComposerService, 'compose', 'composer_compose'),
            (AssociativeRecallService, '_authorize', 'recall_authorize'),
            (AssociativeRecallService, '_preference_candidates', 'preference_candidates'),
            (InputContextSource, '_material', 'input_material'),
            (HistoricalInputContextSource, 'retrieve', 'history_retrieve'),
            (JsonIntegrationResultLedger, '_load_operations', 'journal_load_operations'),
            (JsonIntegrationResultLedger, '_load_capability_document', 'capability_load_document'),
            (journal_module, 'deepcopy', 'journal_deepcopy'),
            (recall_module, 'assess', 'candidate_assess'),
            (ExternalContextSource, '_items', 'external_items'),
            (ExternalCapabilityService, 'absorbed', 'external_absorbed'),
            (ExternalCapabilityService, 'cached', 'external_cached'),
            (ExternalCapabilityService, '_verified', 'external_verified'),
            (ExternalAbsorptionService, 'current', 'external_current'),
            (ExternalAbsorptionService, '_proof', 'external_proof'),
        ):
            wrap(obj, name, label)
        original_read = Path.read_bytes
        def read_bytes(path):
            if not active[0] or not in_recall[0] or path.name != 'operation-journal.first-round-v1.json':
                return original_read(path)
            started = time.perf_counter()
            try:
                return original_read(path)
            finally:
                item = measures['journal_byte_read']; item[0] += 1
                item[1] += (time.perf_counter() - started) * 1000
        stack.enter_context(patch.object(Path, 'read_bytes', read_bytes))
        original_validate = JsonIntegrationResultLedger._validate_operation_set
        def validate(operations):
            if not active[0] or not in_recall[0]: return original_validate(operations)
            started = time.perf_counter()
            try: return original_validate(operations)
            finally:
                item = measures['journal_full_validation']; item[0] += 1
                item[1] += (time.perf_counter() - started) * 1000
        stack.enter_context(patch.object(JsonIntegrationResultLedger, '_validate_operation_set', staticmethod(validate)))

    status = 'OK'
    error = None
    try:
        if scenario == 'third':
            roots = ('external:root-one', 'external:root-two')
            original, derived = '螺蛳粉原文：仍可读取。', '螺蛳粉派生材料：之后撤回。'
            for content in (original, derived):
                f.base.fake.candidate_hook = lambda item, content=content: replace(
                    item, source_id='item:meal-derived' if content == derived else 'item:meal-original',
                    roots=roots, content=content, content_hash=digest(content))
                case.send('我又在吃螺蛳粉。')
            candidate = next(item for _, result, _ in f.base.external.absorbed()
                             for item in result.candidates if item.content_hash == digest(derived))
            memory = f.absorption.adopt_corroborated(candidate.source_id, digest(derived),
                                                       reason='Two current independent TEST roots').memory
            f.core.consolidation.generate_summary(
                f.state.subject_id, summary_id='w02-integrated-derived-summary',
                summary_type='external-observation', scope='external-observation',
                confidence=0.7, source_memory_ids=[memory.memory_id])
        else:
            roots = ('external:root-one', 'external:root-two')
            contents = ('螺蛳粉原文：仍可读取。', '螺蛳粉派生材料：之后撤回。',
                        '螺蛳粉的转述资料：保留来源。', '螺蛳粉的摘要材料：不构成独立根。')
            for index, content in enumerate(contents[:3]):
                f.base.fake.candidate_hook = lambda item, content=content, index=index: replace(
                    item, source_id=f'item:meal-material-{index}', roots=roots,
                    content=content, content_hash=digest(content))
                case.send('我又在吃螺蛳粉。')
            content = contents[3]
            f.base.fake.candidate_hook = lambda item: replace(
                item, source_id='item:meal-material-3', roots=roots,
                content=content, content_hash=digest(content))
        if instrument:
            for binding in f.core.router._bindings:
                for method in ('retrieve', 'revalidate'):
                    if hasattr(binding.source, method):
                        wrap(binding.source, method, 'source_' + binding.source.source_id + '_' + method)
            for source_id, binding in f.core.composer._bindings.items():
                wrap(binding.resolver, 'resolve', 'resolve_' + source_id)
        active[0] = True
        started = time.perf_counter()
        try:
            request = case.send('我又在吃螺蛳粉。')
        except Exception as exc:
            status, error = 'ERROR', {'type': type(exc).__name__, 'code': str(exc)}
            request = None
        elapsed = (time.perf_counter() - started) * 1000
        active[0] = False
        operations = f.base.app.ledger.list_operations()
        last = operations[-1]
        history = getattr(getattr(last, 'domain_progress', None), 'recall_progress', ())
        print(json.dumps({'scenario': scenario, 'instrumented': instrument, 'status': status,
                          'error': error, 'final_request': None if request is None else request['requestId'],
                          'final_submit_ms': round(elapsed, 3),
                          'recall_history': [{'status': x['status'], 'reason': x['stop_reason'],
                                              'elapsed_ms': x['elapsed_ms'], 'retrieved': x['retrieved_count'],
                                              'rounds': len(x['rounds'])} for x in history],
                          'metrics': {key: {'count': n, 'ms': round(ms, 3)}
                                      for key, (n, ms) in sorted(measures.items())},
                          'final_sources': [] if request is None else [x.source_id for x in f.last_context.composition.snapshot.fragments],
                          'external_projection': f.base.external.projection_audit,
                          'model_calls': len(f.base.provider.inputs),
                          'external_effects': len(f.base.fake.facts())}, ensure_ascii=False))
        return 0 if status == 'OK' else 1
    finally:
        active[0] = False
        stack.close()
        case.doCleanups()


if __name__ == '__main__':
    raise SystemExit(main())
