"""P16 isolated external candidate/registry/Broker regressions."""
import tempfile
import unittest
from pathlib import Path


class ProviderTests(unittest.TestCase):
    def setUp(self):
        from continuity_engine.testing.p16_provider_fixture import P16Fixture
        self.temp=tempfile.TemporaryDirectory(prefix='p16-test-');self.addCleanup(self.temp.cleanup)
        self.f=P16Fixture(Path(self.temp.name))

    def test_memory_information_need_calls_fake_then_normal_context_consumes_candidate(self):
        f=self.f;before=f.state.to_dict();request=f.request();f.submit(request)
        self.assertEqual(f.external_calls,1)
        self.assertIsNone(f.core.last_action.plan)
        f.next_round();fragments=f.last_context.composition.snapshot.fragments
        external=[x for x in fragments if x.source_type=='external_candidate']
        self.assertTrue(external)
        self.assertTrue(all(x.authority.value=='retrieved_candidate' for x in external))
        self.assertEqual(before,f.state.to_dict())
        self.assertTrue(any(x.continuity_context and any(y.source_type=='external_candidate' for y in x.continuity_context.composition.snapshot.fragments) for x in f.provider.inputs))

    def test_all_four_local_provider_kinds_really_execute(self):
        for kind in ('memory','knowledge','mcp','skill'):
            with self.subTest(kind=kind):
                f=self.f;f.query=kind+':continuity';f.next_round()
                self.assertEqual(f.core.last_action.requests[0].step.input_payload['kind'],kind)
                self.assertTrue(f.external.cached())
        self.assertEqual(self.f.external_calls,4)

    def test_revoke_before_query_has_no_external_call_or_subject_write(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        from continuity_engine.domain.external_capabilities import ExternalCapabilityError
        f=self.f;before=f.state.to_dict();f.revoke()
        with self.assertRaises(IntegrationExecutionError) as caught:f.submit()
        self.assertIsInstance(caught.exception.__cause__,ExternalCapabilityError)
        self.assertEqual(str(caught.exception.__cause__),'EXTERNAL_PERMISSION_DENIED')
        self.assertEqual(f.external_calls,0);self.assertEqual(before,f.state.to_dict())

    def test_registry_same_version_changed_content_is_conflict(self):
        from dataclasses import replace
        from continuity_engine.domain.external_capabilities import ExternalCapabilityError
        f=self.f;d=f.descriptors[0];before=f.registry_bytes()
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_REGISTRY_IDENTITY_CONFLICT'):f.registry.register(replace(d,description='changed'),expected_revision=f.registry.revision)
        self.assertEqual(before,f.registry_bytes())

    def test_feature_gate_off_does_not_call_or_read_external_components(self):
        f=self.f;f.disable_feature();before=f.external.calls.copy();f.submit()
        self.assertEqual(before,f.external.calls);self.assertEqual(f.external_calls,0)

    def test_existing_768_token_budget_explicitly_excludes_external_material(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.f;f.core.context_budget=ContextBudget(token_limit=768);f.submit();f.next_round()
        decisions=[d for d in f.last_context.composition.trace.decisions if d.source_id=='engine.external-candidates']
        self.assertEqual(len(decisions),1)
        self.assertEqual(decisions[0].reason_code,'CONTEXT_TOKEN_BUDGET_EXHAUSTED')
        self.assertFalse(any(x.source_type=='external_candidate' for x in f.last_context.composition.snapshot.fragments))

    def test_credential_reference_cannot_be_reused_by_other_connector(self):
        from dataclasses import replace
        from continuity_engine.domain.external_capabilities import ExternalCapabilityError
        f=self.f;before=f.registry_bytes();d=replace(f.descriptors[0],version='v2',capability_ref='external.memory.v2',credential_ref='credential:knowledge')
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_REGISTRATION_DENIED'):
            f.external.register(d,expected_revision=f.registry.revision)
        self.assertEqual(before,f.registry_bytes());self.assertEqual(f.external_calls,0)

    def test_missing_expired_and_cross_subject_credentials_refuse_before_call(self):
        from continuity_engine.domain.errors import IntegrationExecutionError
        from continuity_engine.domain.integration_results import format_contract_datetime
        f=self.f;original=__import__('json').loads(f.control.read_text(encoding='utf-8'))
        for change in ({'credential_refs':[]},{'expires_at':format_contract_datetime(f.runtime.clock.now())},{'subject_id':'other-subject'}):
            with self.subTest(change=change):
                f.control_change(**original);f.control_change(**change);before=f.state.to_dict()
                with self.assertRaises(IntegrationExecutionError):f.next_round()
                self.assertEqual(f.external_calls,0);self.assertEqual(before,f.state.to_dict());self.assertEqual(f.registry.cached(),())

    def test_registry_concurrent_revision_allows_only_one_write(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from continuity_engine.domain.external_capabilities import ExternalCapabilityError
        f=self.f;revision=f.registry.revision;barrier=Barrier(2)
        def disable(d):
            barrier.wait()
            try:f.registry.disable(d.key,expected_revision=revision);return 'ok'
            except ExternalCapabilityError as exc:return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(disable,f.descriptors[:2]))
        self.assertCountEqual(results,['ok','EXTERNAL_REGISTRY_REVISION'])
        self.assertEqual(f.registry.revision,revision+1)
        self.assertEqual(sum(not enabled for _,enabled in f.registry.descriptors()),1)

    def test_disable_replay_is_idempotent_and_cannot_reregister_same_version(self):
        from continuity_engine.domain.external_capabilities import ExternalCapabilityError
        f=self.f;d=f.descriptors[0];f.registry.disable(d.key,expected_revision=f.registry.revision);before=f.registry_bytes()
        f.registry.disable(d.key,expected_revision=f.registry.revision);self.assertEqual(before,f.registry_bytes())
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_REGISTRY_IDENTITY_CONFLICT'):
            f.external.register(d,expected_revision=f.registry.revision)
        self.assertEqual(before,f.registry_bytes())

    def test_upper_mixed_protected_roots_and_children_are_zero_write(self):
        from continuity_engine.testing.p16_provider_fixture import P16Fixture,FakeQueryProvider
        from continuity_engine.testing.models import SandboxOperationError
        from continuity_engine.testing.persistence import tree_inventory_hash
        for name in ('.CONTINUITY-DATA','.Continuity-Data','.ASSISTANT-DATA','.Assistant-Data'):
            for suffix in ('','child'):
                with self.subTest(name=name,suffix=suffix):
                    path=Path(self.temp.name)/name/suffix;before=tree_inventory_hash(Path(self.temp.name))
                    with self.assertRaisesRegex(SandboxOperationError,'SANDBOX_PATH_FORBIDDEN'):P16Fixture(path)
                    with self.assertRaisesRegex(SandboxOperationError,'SANDBOX_PATH_FORBIDDEN'):FakeQueryProvider(path/'facts.json',self.f.control,self.f.runtime.clock.now)
                    self.assertEqual(before,tree_inventory_hash(Path(self.temp.name)))

    def test_disabled_c1_gate_does_not_touch_installed_external_ports(self):
        from unittest.mock import patch
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        f=self.f;f.core_options['gates']=ContinuityCoreGates(enabled=False)
        with patch.object(f.external,'bindings',side_effect=AssertionError('unexpected binding read')),patch.object(f.external,'cached',side_effect=AssertionError('unexpected cache read')):
            f.reopen();f.submit()
        self.assertEqual(f.external_calls,0);self.assertIsNone(f.core.external_capabilities)

    def test_normal_local_queries_use_no_socket(self):
        from unittest.mock import patch
        with patch('socket.socket',side_effect=AssertionError('P16 transport forbidden')):
            self.f.submit();self.f.next_round()
        self.assertEqual(self.f.external_calls,2);self.assertEqual(self.f.manager.formal_access_count,0)


if __name__=='__main__':unittest.main()
