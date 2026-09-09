"""Current authorization, isolation and all-material/diagnostic boundaries."""
from dataclasses import replace
from datetime import timedelta
import json
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch
from test_p17_execution import ExecutionCase
from continuity_engine.domain.execution import ExecutionError, Outcome, BlastRadius
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.testing.p16_provider_fixture import SECRET_MARKER
from continuity_engine.testing.p17_execution_fixture import P17Fixture, FakeWorldAdapter
from continuity_engine.testing.persistence import tree_inventory_hash


class BoundaryTests(ExecutionCase):
    def assert_no_dispatch(self,f,change):
        request,run=f.manual()
        before=f.fake.effect_count;credits=f.fake.credits
        change()
        with self.assertRaises(Exception):f.execution.execute(request)
        self.assertEqual(f.fake.effect_count,before);self.assertEqual(f.fake.credits,credits)

    def test_current_context_and_confirmation_rechecked_at_dispatch(self):
        for kind in ('context','confirmation','references'):
            with self.subTest(kind=kind):
                f=self.seeded()
                change={'context':lambda:setattr(f.constraints,'context_allowed',False),
                        'confirmation':lambda:setattr(f.constraints,'confirmation_allowed',False),
                        'references':lambda:setattr(f.base.permission,'references_allowed',False)}[kind]
                self.assert_no_dispatch(f,change)

    def test_current_broker_and_reality_rechecked_at_dispatch(self):
        for kind in ('broker','reality','expiry','recoverability'):
            with self.subTest(kind=kind):
                f=self.seeded()
                change={'broker':lambda:setattr(f.broker,'allowed',False),
                        'reality':lambda:setattr(f.boundary,'allowed',False),
                        'expiry':lambda:setattr(f,'expiry',f.runtime.clock.now()),
                        'recoverability':lambda:setattr(f.boundary,'recovery_ready',False)}[kind]
                self.assert_no_dispatch(f,change)

    def test_lifecycle_pause_archive_delete_reject_new_execution(self):
        for operation in ('SUSPEND','ARCHIVE','DELETE'):
            with self.subTest(operation=operation):
                f=self.seeded()
                def change():
                    if operation=='DELETE':f.lifecycle('ARCHIVE')
                    f.lifecycle(operation)
                self.assert_no_dispatch(f,change)

    def test_resource_exhaustion_does_not_consume_attempts_or_effects(self):
        f=self.seeded();request,_=f.manual();before=f.outbox.path.read_bytes()
        f.boundary.resource_ready=False
        with self.assertRaisesRegex(ExecutionError,'RESOURCE_EXHAUSTED'):f.execution.execute(request)
        self.assertEqual(f.outbox.path.read_bytes(),before);self.assertEqual(f.fake.effect_count,1)

    def test_blast_radius_each_bound_actually_limits_effects(self):
        for limits in (BlastRadius(requests=1),BlastRadius(credits=1),BlastRadius(messages=1),BlastRadius(storage_bytes=1)):
            with self.subTest(limits=limits):
                f=self.fixture(limits=limits)
                if limits.storage_bytes==1:
                    with self.assertRaises(IntegrationExecutionError):f.submit()
                    self.assertEqual(f.fake.effect_count,0)
                else:
                    f.submit();request,_=f.manual()
                    with self.assertRaisesRegex(ExecutionError,'RESOURCE_EXHAUSTED'):f.execution.execute(request)
                    self.assertEqual(f.fake.effect_count,1)

    def test_mid_gate_revocation_is_rechecked_before_effect(self):
        f=self.seeded();request,_=f.manual();f.boundary.hook=lambda:setattr(f.broker,'allowed',False)
        with self.assertRaises(ExecutionError):f.execution.execute(request)
        self.assertEqual(f.fake.effect_count,1)

    def test_mid_result_read_revocation_blocks_return_and_writes(self):
        f=self.seeded();before=tree_inventory_hash(f.runtime.data_root)
        def hook(value):f.broker.allowed=False;return value
        f.fake.result_hook=hook
        with self.assertRaisesRegex(ExecutionError,'PLATFORM_DENIAL'):f.execution.results_for_context()
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_result_hash_or_extra_authority_material_rejected(self):
        for kind in ('hash','authority','secret'):
            with self.subTest(kind=kind):
                f=self.seeded();before=f.state.to_dict()
                f.fake.result_hook=lambda value:{**value,**({'content':'changed'} if kind=='hash' else
                    {'mutations':[]} if kind=='authority' else {'content':SECRET_MARKER})}
                with self.assertRaises(ExecutionError):f.execution.results_for_context()
                self.assertEqual(f.state.to_dict(),before)
                for p in f.runtime.data_root.rglob('*.json'):
                    self.assertNotIn(SECRET_MARKER,p.read_text(encoding='utf-8'))

    def test_receipt_secret_full_material_never_enters_ledger(self):
        for field in ('receipt_id','adapter_id','subject_id','step_id'):
            with self.subTest(field=field):
                f=self.fixture();f.fake.receipt_hook=lambda r:replace(r,**{field:SECRET_MARKER})
                with self.assertRaises(IntegrationExecutionError):f.submit()
                for p in f.runtime.data_root.rglob('*.json'):
                    self.assertNotIn(SECRET_MARKER,p.read_text(encoding='utf-8'))
                self.assertEqual(f.fake.effect_count,1)
                f.fake.receipt_hook=None
                self.assertEqual(f.submit(f.last_request).status,'completed')
                self.assertEqual(f.fake.effect_count,1)

    def test_thinking_secret_rejected_before_first_persistence(self):
        f=self.fixture();f.thought=SECRET_MARKER
        with self.assertRaises(Exception):f.submit()
        self.assertEqual(f.fake.execute_calls,0)
        for p in f.runtime.data_root.rglob('*.json'):
            self.assertNotIn(SECRET_MARKER,p.read_text(encoding='utf-8'))

    def test_normal_psychological_content_and_silence_are_not_screened(self):
        f=self.fixture();f.thought='anger, despair, desire, conflicting values and private fantasy'
        self.assertEqual(f.submit().status,'completed')
        self.assertEqual(f.fake.effect_count,1)
        f.mode='silence';self.assertEqual(f.next_round().status,'completed')
        self.assertEqual(f.fake.effect_count,1)

    def test_broker_boundary_provider_exception_tracebacks_are_static(self):
        cases=[('broker','material_allowed'),('broker','authorize_reference'),('boundary','ready'),
               ('boundary','authorize'),('boundary','recoverable'),('boundary','capacity'),('fake','query')]
        for owner,method in cases:
            with self.subTest(port=(owner,method)):
                f=self.seeded();request,_=f.manual()
                with patch.object(getattr(f,owner),method,side_effect=RuntimeError(SECRET_MARKER)):
                    try:f.execution.execute(request)
                    except Exception:
                        diagnostic=traceback.format_exc();self.assertNotIn(SECRET_MARKER,diagnostic)
                    else:self.fail('port exception cannot authorize execution')
                self.assertEqual(f.fake.effect_count,1)

    def test_nonboolean_truthy_authorization_fails_closed(self):
        f=self.seeded();request,_=f.manual()
        with patch.object(f.broker,'authorize_reference',return_value='yes'):
            with self.assertRaisesRegex(ExecutionError,'PLATFORM_DENIAL'):f.execution.execute(request)
        self.assertEqual(f.fake.effect_count,1)

    def test_fixture_protected_paths_uppercase_children_zero_write(self):
        for name in ('.CONTINUITY-DATA','.Assistant-Data'):
            with self.subTest(name=name):
                temp=tempfile.TemporaryDirectory(prefix='p17-protect-');self.addCleanup(temp.cleanup)
                root=Path(temp.name);protected=root/name;protected.mkdir();before=tree_inventory_hash(root)
                for target in (protected,protected/'child'):
                    with self.assertRaises(Exception):P17Fixture(target)
                    with self.assertRaises(Exception):FakeWorldAdapter(target,subject='s',adapter_id='a',world='TEST',clock=lambda:None)
                    self.assertEqual(tree_inventory_hash(root),before)

    def test_capability_version_change_cannot_retarget_history(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        route=f.execution.routes[request.capability_type]
        f.execution.routes[request.capability_type]=replace(route,version='v2')
        with self.assertRaisesRegex(ExecutionError,'REQUEST_BINDING'):f.execution.query(request)
        self.assertEqual(f.fake.effect_count,1)

    def test_platform_reality_resource_outcomes_remain_distinct_in_e5a(self):
        for reason in ('PLATFORM_DENIAL','REALITY_DENIAL','RESOURCE_EXHAUSTED','RECOVERABILITY_NOT_READY'):
            with self.subTest(reason=reason):
                f=self.fixture()
                if reason=='PLATFORM_DENIAL':f.broker.allowed=False
                elif reason=='REALITY_DENIAL':f.boundary.allowed=False
                elif reason=='RESOURCE_EXHAUSTED':f.boundary.resource_ready=False
                else:f.boundary.recovery_ready=False
                with self.assertRaises(IntegrationExecutionError):f.submit()
                self.assertEqual(f.core.last_action.results[0].reason,reason)
                self.assertEqual(f.fake.effect_count,0)

    def test_static_failure_receipts_preserve_generation_and_network_outcomes(self):
        for mode,reason in (('generation_failed',Outcome.GENERATION_FAILED),('network_failed',Outcome.NETWORK_FAILED),('terminal',Outcome.REALITY_DENIAL)):
            with self.subTest(mode=mode):
                f=self.fixture();f.fake.mode=mode
                with self.assertRaises(IntegrationExecutionError):f.submit()
                request=f.core.last_action.requests[0]
                self.assertEqual(f.execution.outcome(request.capability_request_id),reason)
                self.assertEqual(f.fake.effect_count,0)

    def test_material_rejected_before_any_new_e5a_request_write(self):
        f=self.seeded();request,run=f.manual(decision=SECRET_MARKER,reserve=False)
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaisesRegex(ExecutionError,'MATERIAL_REJECTED'):run()
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        for path in f.runtime.data_root.rglob('*.json'):
            self.assertNotIn(SECRET_MARKER,path.read_text(encoding='utf-8'))

    def test_cross_subject_request_rejected_without_world_or_outbox_write(self):
        f=self.seeded();request=f.core.last_action.requests[0]
        changed=replace(request,choice=replace(request.choice,subject_id='another-subject'))
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(ExecutionError):f.execution.execute(changed)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_feature_off_does_not_read_execution_ports(self):
        from continuity_engine.services.continuity_core_service import ContinuityCoreGates
        from continuity_engine.services.continuity_core_runtime import build_continuity_core
        from continuity_engine.testing.p09_core_fixture import CoreClaims
        from continuity_engine.testing.interaction import SandboxContractValidator,SandboxFirstRoundResultFactory
        from continuity_engine.interfaces.local_integration_app import build_local_integration_app
        f=self.fixture()
        def factory(**kwargs):
            return build_continuity_core(**kwargs,environment='TEST',constraints=f.constraints,capabilities=(),
                    claim_resolver=CoreClaims(),gates=ContinuityCoreGates(enabled=False),execution=f.execution)
        with patch.object(f.execution,'bindings',side_effect=AssertionError('disabled port read')):
            app=build_local_integration_app(f.runtime.data_root,clock=f.runtime.clock.now,thinking_provider=f.base.provider,
                    continuity_core_factory=factory,contract_validator=SandboxContractValidator(),result_factory=SandboxFirstRoundResultFactory())
            self.assertEqual(app.adapter.submit(f.request()).status,'completed')
        self.assertEqual(f.fake.execute_calls,0);self.assertFalse(f.outbox.path.exists())

    def test_new_context_cannot_reauthorize_old_request_identity(self):
        f=self.seeded();request,_=f.manual(decision='pending-old-context')
        f.mode='absorb';f.next_round()
        f.mode='silence';f.next_round()
        self.assertGreater(f.last_context.composition.snapshot.source_revision,request.choice.source_revision)
        f.restore_dispatch(request)
        before=f.fake.effect_count
        with self.assertRaises(Exception):f.execution.execute(request)
        self.assertEqual(f.fake.effect_count,before)

    def test_storage_growth_bound_rejects_before_oversized_effect(self):
        f=self.seeded();limit=len(json.dumps(f.fake.store.load()).encode())+1024
        f.execution.limits=BlastRadius(storage_bytes=limit)
        request,run=f.manual(decision='storage-boundary')
        self.assertNotEqual(run().status,'COMPLETED')
        self.assertEqual(f.fake.effect_count,1)
        self.assertLessEqual(f.fake.store.path.stat().st_size,limit)

    def test_storage_exact_limit_accepts_one_then_refuses_next(self):
        f=self.seeded();request,run=f.manual(decision='exact-storage')
        limit=f.fake.projected_size(request)
        f.execution.limits=BlastRadius(storage_bytes=limit)
        self.assertEqual(run().status,'COMPLETED')
        self.assertEqual(f.fake.store.path.stat().st_size,limit)
        later,later_run=f.manual(decision='past-storage')
        self.assertNotEqual(later_run().status,'COMPLETED')
        self.assertEqual(f.fake.effect_count,2)

    def test_registered_other_subject_adapter_rejected_zero_calls_and_writes(self):
        f=self.seeded();other=self.fixture();request,run=f.manual(decision='other-world')
        f.execution.adapters[f.fake.adapter_id]=other.fake
        before=tree_inventory_hash(other.runtime.data_root)
        with self.assertRaises(ExecutionError):f.execution.execute(request)
        self.assertEqual(tree_inventory_hash(other.runtime.data_root),before)
        self.assertEqual(other.fake.query_calls,0);self.assertEqual(other.fake.execute_calls,0)

    def test_registered_world_environment_version_mismatch_refuses_before_call(self):
        for name,value in (('world','RESEARCH'),('environment','RESEARCH'),('version','v2')):
            with self.subTest(field=name):
                f=self.seeded();request,_=f.manual();before=tree_inventory_hash(f.runtime.data_root)
                setattr(f.fake,name,value);calls=f.fake.query_calls
                with self.assertRaises(ExecutionError):f.execution.execute(request)
                self.assertEqual(f.fake.query_calls,calls)
                self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
