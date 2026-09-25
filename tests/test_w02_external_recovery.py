"""N11/T18: source binding and E5-A fact recovery across original requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.testing.w02_c_fixture import W02CFixture
from continuity_engine.testing.p16_provider_fixture import P16Fixture


class ExternalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wc-')
        self.addCleanup(self.temp.cleanup)
        self.f=W02CFixture(Path(self.temp.name))

    def test_original_completed_request_replays_without_new_execution_or_cache_row(self):
        f=self.f
        request=f.base.request()
        result=f.submit(request)
        before=f.base.registry.cache_path.read_bytes()
        facts=f.base.fake.facts()
        state=f.state.to_dict()
        f.reopen()
        replay=f.submit(request)
        self.assertEqual(result.to_dict(),replay.to_dict())
        self.assertEqual(f.external_calls,1)
        self.assertEqual(f.base.fake.facts(),facts)
        self.assertEqual(f.base.registry.cache_path.read_bytes(),before)
        self.assertEqual(f.state.to_dict(),state)

    def test_after_adapter_result_loss_recovers_exact_fact_not_second_query(self):
        f=self.f
        request=f.base.request()
        def fail(point):
            if point=='after_adapter_before_result':raise RuntimeError('W02C_TEST_STOP')
        f.core.fault=fail
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.external_calls,1)
        self.assertEqual(len(f.base.fake.facts()),1)
        f.reopen()
        f.submit(request)
        self.assertEqual(f.external_calls,1)
        self.assertEqual(len(f.base.fake.facts()),1)
        self.assertEqual(len(f.base.external.absorbed()),1)

    def test_unknown_result_never_means_not_executed(self):
        f=self.f
        f.base.mode('unknown')
        request=f.base.request()
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        f.reopen()
        with self.assertRaises(IntegrationExecutionError):f.submit(request)
        self.assertEqual(f.external_calls,0)
        self.assertEqual(f.base.registry.cached(),())
        self.assertEqual(f.base.fake.facts(),[])

    def test_old_p16_cache_without_root_proof_is_not_trusted_w02c_material(self):
        root=Path(self.temp.name)/'legacy'
        p16=P16Fixture(root)
        p16.submit()
        self.assertEqual(len(p16.registry.cached()),1)
        upgraded=W02CFixture(root,runtime=p16.runtime,manager=p16.manager)
        self.assertEqual(upgraded.base.external.absorbed(),())
        upgraded.next_round()
        old=[x for x in upgraded.last_context.composition.snapshot.fragments
             if x.source_type=='external_candidate']
        self.assertFalse(old)

    def test_real_child_reopens_original_request_and_root_without_effect_replay(self):
        f=self.f
        request=f.base.request()
        f.submit(request)
        request_path=Path(self.temp.name)/'request.json'
        request_path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
        env=os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE']='1'
        env['PYTHONUTF8']='1'
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        command=[sys.executable,'-m','continuity_engine.testing.w02_c_child',
                 self.temp.name,f.base.runtime.descriptor.sandbox_id,str(request_path)]
        child=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',
                             timeout=60,env=env,check=False)
        self.assertEqual(child.returncode,0,child.stderr)
        outcome=json.loads(child.stdout)
        self.assertEqual(outcome['external_calls'],0)
        self.assertEqual(outcome['cache_entries'],1)
        self.assertEqual(outcome['absorbed_entries'],1)
        self.assertEqual(outcome['revision'],f.state.revision)

    def test_revoked_source_never_becomes_new_material_on_replay(self):
        f=self.f
        request=f.base.request()
        f.submit(request)
        f.roots.change('external:shared-source:continuity',status='REVOKED')
        f.reopen()
        f.submit(request)
        self.assertEqual(f.external_calls,1)
        f.next_round()
        self.assertFalse(any(x.source_type=='external_candidate' for x in
                             f.last_context.composition.snapshot.fragments))

    def test_corrupt_absorption_binding_fails_closed_before_context(self):
        f=self.f
        f.submit()
        path=f.base.registry.cache_path
        original=path.read_bytes()
        payload=json.loads(original)
        payload['document']['entries'][0]['absorption']['request_hash']='sha256:'+'0'*64
        payload['hash']=__import__('continuity_engine.domain.action_planning',fromlist=['digest']).digest(payload['document'])
        path.write_text(json.dumps(payload),encoding='utf-8')
        with self.assertRaises(ExternalCapabilityError):f.base.external.absorbed()
        self.assertEqual(len(f.base.fake.facts()),1)


if __name__=='__main__':unittest.main()
