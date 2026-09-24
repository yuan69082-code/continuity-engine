from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.errors import ContextCompositionSourceError, IntegrationExecutionError
from continuity_engine.domain.events import EventClassification, EventReference, EventRelationType
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture
from continuity_engine.testing.w02_input_fixture import capture_failure


class RecallReadConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def tearDown(self):capture_failure(self,self.root)

    def history(self,f):
        return next(b.source for b in f.core.router._bindings if b.source.source_id=='engine.input-history')

    def test_scoped_journal_reads_do_not_share_mutation_or_hide_corruption(self):
        from continuity_engine.domain.errors import IntegrationPersistenceError
        f=W02RecallFixture(self.root);request=f.message('你好');f.submit(request)
        ledger=f.app.ledger;request_id=request['requestId']
        before=ledger.operation_path.read_bytes()
        with ledger._verified_operation_reads():
            first=ledger.load_operation(request_id)
            first.domain_progress.recall_progress[-1]['status']='NOT_A_REAL_STATUS'
            self.assertEqual(ledger.load_operation(request_id).domain_progress.recall_progress[-1]['status'],'READY')
            self.assertEqual(ledger.operation_path.read_bytes(),before)
            data=json.loads(before);data['operationJournalFormatVersion']=999
            ledger.operation_path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaisesRegex(IntegrationPersistenceError,'unsupported'):
                ledger.load_operation(request_id)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(1,1,1))

    def test_parse_reuse_ends_with_scope_and_keeps_legacy_validation(self):
        f=W02RecallFixture(self.root);request=f.message('你好');f.submit(request)
        ledger=f.app.ledger;check=ledger._validate_operation_set
        with patch.object(ledger,'_validate_operation_set',wraps=check) as validation:
            with ledger._verified_operation_reads():
                one=ledger.load_operation(request['requestId'])
                self.assertEqual(one,ledger.load_operation(request['requestId']))
                self.assertEqual(validation.call_count,1)
            self.assertEqual(one,ledger.load_operation(request['requestId']))
            self.assertEqual(one,ledger.load_operation(request['requestId']))
            self.assertEqual(validation.call_count,3)

    def test_scoped_input_projection_matches_original_without_persisting_changes(self):
        f=W02RecallFixture(self.root);request=f.message('我喜欢音乐');f.submit(request)
        source=f.core.input_processing.source;ledger=f.app.ledger
        expected=source._material(request['requestId']);before=ledger.operation_path.read_bytes()
        with ledger._verified_operation_reads():
            self.assertEqual(source._material(request['requestId']),expected)
            projection=ledger._load_operation_input(request['requestId'])
            projection.domain_progress.input_processing.manifest['subject_id']='changed'
            self.assertEqual(source._material(request['requestId']),expected)
        self.assertEqual(ledger.operation_path.read_bytes(),before)
        self.assertIsNotNone(ledger.load_operation(request['requestId']).domain_progress.perception.continuity_context)

    def test_input_projection_cannot_hide_corruption_in_another_original_record(self):
        from continuity_engine.domain.errors import IntegrationPersistenceError
        f=W02RecallFixture(self.root)
        first=f.message('你好');f.submit(first)
        second=f.message('谢谢');f.submit(second)
        source=f.core.input_processing.source;ledger=f.app.ledger
        with ledger._verified_operation_reads():
            source._material(second['requestId'])
            data=json.loads(ledger.operation_path.read_text(encoding='utf-8'))
            other=next(x for x in data['operations'] if x['requestId']==first['requestId'])
            del other['requestHash']
            ledger.operation_path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(IntegrationPersistenceError):source._material(second['requestId'])
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(2,2,2))

    def test_historical_root_revoked_during_permission_cannot_be_returned(self):
        f=W02RecallFixture(self.root);f.event('meal',content='我吃了螺蛳粉')
        old=f.message('我吃了螺蛳粉',source_event_id='meal');f.submit(old)
        new=f.message('我又在吃螺蛳粉');f.submit(new)
        ref=next(r for r in f.context(new).route.manifest.candidates if r.source_id=='engine.input-history')
        source=self.history(f);original=source._authorize_material
        def revoke(*args):
            original(*args)
            f.event('withdraw',classification=EventClassification.REVOCATION,
                references=(EventReference('meal',f.core.subject_id,EventRelationType.REVOKES),))
        calls,effects,credits=f.provider.calls,f.adapter.effect_count,f.adapter.credits
        with patch.object(source,'_authorize_material',side_effect=revoke):
            with self.assertRaisesRegex(ContextCompositionSourceError,'INPUT_HISTORY_SOURCE_INELIGIBLE'):
                source.resolve(ref)
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(calls,effects,credits))

    def test_candidate_record_changed_during_permission_blocks_before_model(self):
        f=W02RecallFixture(self.root)
        for i,text in enumerate(('我吃了螺蛳粉','我又在吃螺蛳粉')):
            f.event('meal'+str(i),content=text);f.submit(f.message(text,source_event_id='meal'+str(i)))
        text='我喜欢螺蛳粉';f.event('meal2',content=text);request=f.message(text,source_event_id='meal2')
        source=self.history(f);original_prepare=f.core.recall._preference_candidates
        original_authorize=source._authorize_material
        changed=[]
        def authorize(request_id,material):
            original_authorize(request_id,material)
            if changed:return
            prior=f.app.ledger.load_operation(request_id)
            data=json.loads(f.app.ledger.operation_path.read_text(encoding='utf-8'))
            at=datetime.fromisoformat(prior.updated_at.replace('Z','+00:00'))
            next(x for x in data['operations'] if x['requestId']==request_id)['updatedAt']=format_contract_datetime(at+timedelta(seconds=1))
            f.app.ledger.operation_path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            changed.append(request_id)
        def candidate(*args):
            with patch.object(source,'_authorize_material',side_effect=authorize):
                return original_prepare(*args)
        calls,effects,credits=f.provider.calls,f.adapter.effect_count,f.adapter.credits
        with patch.object(f.core.recall,'_preference_candidates',side_effect=candidate):
            with self.assertRaises(IntegrationExecutionError) as caught:f.submit(request)
        self.assertTrue(changed,str(caught.exception.__cause__))
        self.assertIn('RECALL_CANDIDATE_SOURCE_CHANGED',str(caught.exception.__cause__))
        self.assertEqual((f.provider.calls,f.adapter.effect_count,f.adapter.credits),(calls,effects,credits))
        self.assertEqual(f.app.adapter.service.recall_outcome(request['requestId'])['status'],'BLOCKED')
