import json,tempfile,unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from continuity_engine.domain.errors import IntegrationExecutionError,CapabilityValidationError
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.domain.action_planning import digest
from continuity_engine.testing.p16_provider_fixture import P16Fixture,SECRET_MARKER


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p16-context-');self.addCleanup(self.temp.cleanup)
        self.f=P16Fixture(Path(self.temp.name))
    def test_revoke_during_result_read_blocks_consumption_and_cache_write(self):
        f=self.f;f.submit();before=f.registry.cache_path.read_bytes()
        def hook(value):f.revoke();return value
        f.fake.result_hook=hook
        self.assertEqual(f.external.cached(),())
        self.assertEqual(before,f.registry.cache_path.read_bytes())
    def test_revocation_invalidates_already_composed_context(self):
        f=self.f;f.submit();f.next_round();context=f.last_context
        self.assertTrue(any(x.source_type=='external_candidate' for x in context.composition.snapshot.fragments))
        f.revoke();self.assertFalse(f.core.current(context))
    def test_cache_expiry_excludes_candidate_without_refresh_call(self):
        f=self.f;f.submit();calls=f.external_calls;f.runtime.clock.advance(timedelta(seconds=301))
        self.assertEqual(f.external.cached(),());self.assertEqual(f.external_calls,calls)
    def test_credential_revocation_excludes_current_cache(self):
        f=self.f;f.submit();f.control_change(broker_allowed=False)
        self.assertEqual(f.external.cached(),());self.assertEqual(f.external_calls,1)
    def test_same_request_payload_hash_conflict_is_rejected(self):
        f=self.f;f.submit();r=f.core.last_action.requests[0]
        with self.assertRaises(CapabilityValidationError):replace(r.step,input_payload={'kind':'memory','query':'changed','limit':4})
    def test_malicious_mutation_field_rejected_before_cache(self):
        f=self.f
        def hook(value):value['mutations']=[{'field_path':'identity.values','value':'forged'}];return value
        f.fake.result_hook=hook;before=f.state.to_dict()
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(before,f.state.to_dict());self.assertEqual(f.registry.cached(),())
    def test_external_event_identity_cannot_be_internal_root(self):
        f=self.f
        def hook(value):value['candidates'][0]['roots']=['event:internal-imposter'];return value
        f.fake.result_hook=hook
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(f.registry.cached(),())
    def test_cross_subject_result_rejected_even_from_local_provider(self):
        f=self.f
        def hook(value):value['subject_id']='other-subject';return value
        f.fake.result_hook=hook
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertEqual(f.registry.cached(),())
    def test_cache_rehashed_payload_tamper_still_checks_original_fact(self):
        f=self.f;f.submit();document=json.loads(f.registry.cache_path.read_text(encoding='utf-8'))
        c=document['document']['entries'][0]['result']['candidates'][0];c['content']='forged';c['content_hash']=digest('forged')
        document['hash']=digest(document['document']);f.registry.cache_path.write_text(json.dumps(document),encoding='utf-8')
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_CACHE_RESULT_CONFLICT'):f.external.cached()
    def test_offline_timeout_cancel_and_empty_are_explicit_results(self):
        f=self.f
        for mode in ('offline','timeout','cancelled','empty'):
            with self.subTest(mode=mode):
                f.mode(mode);f.next_round()
                self.assertEqual(f.external.last_outcome,mode.upper())
                self.assertEqual(f.core.last_trace['external_result']['candidate_count'],0)
        self.assertEqual(f.external_calls,4)
    def test_registry_wrong_environment_rejected_without_write(self):
        f=self.f;before=f.registry_bytes()
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_REGISTRY_BINDING'):
            f.registry.register(replace(f.descriptors[0],environment='RESEARCH'),expected_revision=f.registry.revision)
        self.assertEqual(before,f.registry_bytes())

    def test_replacement_descriptor_cannot_reuse_old_exact_reference(self):
        from unittest.mock import patch
        from continuity_engine.services.external_context_source import ExternalContextSource
        f=self.f;f.submit();source=ExternalContextSource(f.external)
        original=source._items(f.state.subject_id,'TEST')
        request,value=f.external.cached()[0]
        replacement=replace(f.descriptors[0],version='v2',capability_ref='external.memory.v2')
        changed=replace(value,descriptor_hash=digest(replacement.to_dict()))
        # Same external fact and timestamp, different authorized connector wrapper.
        with patch.object(f.external,'cached',return_value=((request,changed),)),patch.object(f.external,'descriptor_for',return_value=replacement):
            current=source._items(f.state.subject_id,'TEST')
        self.assertNotEqual(original,current)
        self.assertEqual(next(iter(original.values()))[0].roots,next(iter(current.values()))[0].roots)

    def test_invalid_cache_timestamp_is_corruption_not_freshness(self):
        f=self.f;f.submit();path=f.registry.cache_path;document=json.loads(path.read_text(encoding='utf-8'))
        document['document']['entries'][0]['cached_at']='not-a-time';document['hash']=digest(document['document'])
        path.write_text(json.dumps(document),encoding='utf-8');before=path.read_bytes()
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_STORE_CORRUPT'):f.external.cached()
        self.assertEqual(before,path.read_bytes())

    def test_same_root_candidates_deduplicate_without_promoting_authority(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.f;f.core.context_budget=ContextBudget(token_limit=4096)
        f.fake.candidate_hook=lambda c:replace(c,content='continuity shared fact',content_hash=digest('continuity shared fact'))
        f.query='memory:continuity';f.next_round();f.query='knowledge:continuity';f.next_round();f.query='skill:continuity';f.next_round()
        fragments=[x for x in f.last_context.composition.snapshot.fragments if x.source_type=='external_candidate']
        self.assertEqual(len(fragments),1)
        self.assertEqual(fragments[0].authority.value,'retrieved_candidate')
        self.assertIn('EXTERNAL_UNVERIFIED',fragments[0].conflict_markers)
        self.assertGreater(f.external.projection_audit['duplicate_wrappers'],0)

    def test_distinct_roots_survive_and_same_root_conflict_never_selects_authority(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.f;f.core.context_budget=ContextBudget(token_limit=4096)
        f.fake.candidate_hook=lambda c:replace(c,roots=('external:'+f.query.split(':')[0],),uncertainty='DISPUTED_EXTERNAL')
        f.query='memory:continuity';f.next_round();f.query='knowledge:continuity';f.next_round();f.query='skill:continuity';f.next_round()
        fragments=[x for x in f.last_context.composition.snapshot.fragments if x.source_type=='external_candidate']
        self.assertEqual(len(fragments),2)
        self.assertEqual(len({r for x in fragments for r in x.provenance_roots}),2)
        self.assertTrue(all('EXTERNAL_DISPUTED' in x.conflict_markers and x.authority.value=='retrieved_candidate' for x in fragments))

    def test_same_root_conflicting_content_is_preserved_as_non_independent_candidates(self):
        from continuity_engine.domain.context_composition import ContextBudget
        f=self.f;f.core.context_budget=ContextBudget(token_limit=4096)
        f.query='memory:continuity';f.next_round();f.query='knowledge:continuity';f.next_round();f.query='skill:continuity';f.next_round()
        fragments=[x for x in f.last_context.composition.snapshot.fragments if x.source_type=='external_candidate']
        self.assertEqual(len(fragments),2)
        self.assertEqual(len({r for x in fragments for r in x.provenance_roots}),1)
        self.assertTrue(all(x.authority.value=='retrieved_candidate' for x in fragments))

    def test_strict_result_shape_version_hash_environment_and_bounds(self):
        f=self.f
        changes=(lambda v:v.update(api_key='synthetic-forbidden-field'),
                 lambda v:v.update(environment='RESEARCH'),lambda v:v.update(connector_id='other.connector'),
                 lambda v:v.update(descriptor_hash=digest('other')),
                 lambda v:v['candidates'][0].update(content_hash=digest('wrong')),
                 lambda v:v['candidates'][0].update(confidence=float('nan')),
                 lambda v:v['candidates'][0].update(content='x'*2049))
        for index,change in enumerate(changes):
            with self.subTest(case=index):
                def hook(value):change(value);return value
                f.fake.result_hook=hook;before=f.state.to_dict()
                with self.assertRaises(IntegrationExecutionError):f.next_round()
                self.assertEqual(before,f.state.to_dict());self.assertEqual(f.registry.cached(),())

    def test_exact_ttl_boundary_is_excluded_just_before_is_valid(self):
        f=self.f;f.submit();f.runtime.clock.advance(timedelta(seconds=299));self.assertTrue(f.external.cached())
        f.runtime.clock.advance(timedelta(seconds=1));self.assertEqual(f.external.cached(),());self.assertEqual(f.external_calls,1)

    def test_replacement_preserves_old_fact_but_invalidates_old_material(self):
        f=self.f;r=f.request();f.submit(r);f.next_round();old=f.last_context
        replacement=f.replace_memory_connector();self.assertFalse(f.core.current(old))
        calls=f.external_calls;f.submit(r);self.assertEqual(f.external_calls,calls)
        f.next_round();self.assertEqual(f.core.last_action.requests[0].step.target,replacement.key)
        self.assertTrue(all(request.step.target==replacement.key for request,_ in f.external.cached()))

    def test_router_source_limit_is_separate_from_composer_budget(self):
        from continuity_engine.domain.context_composition import ContextBudget
        from continuity_engine.domain.context_routing import RetrievalBudget
        f=self.f;f.core.context_budget=ContextBudget(token_limit=4096)
        f.fake.candidate_hook=lambda c:replace(c,roots=('external:'+f.query.split(':')[0],))
        f.query='memory:continuity';f.next_round();f.query='knowledge:continuity';f.next_round()
        f.core.retrieval_budget=RetrievalBudget(per_source_limits=(('engine.external-candidates',1),))
        f.next_round()
        self.assertEqual(len([x for x in f.last_context.route.manifest.candidates if x.source_id=='engine.external-candidates']),1)
        self.assertLess(f.last_context.composition.trace.tokens_used,4096)

    def test_p15_growth_does_not_promote_external_candidates_to_experience(self):
        f=self.f;f.core_options['subject_growth']=True;f.reopen();state=f.state.to_dict()
        existing=[x.to_dict() for x in f.core.growth.learning.list_learning_events(f.state.subject_id)]
        f.submit();f.next_round()
        self.assertTrue(any(x.source_type=='external_candidate' for x in f.last_context.composition.snapshot.fragments))
        self.assertEqual(f.core.growth.capture(f.last_context),())
        self.assertEqual([x.to_dict() for x in f.core.growth.learning.list_learning_events(f.state.subject_id)],existing)
        self.assertEqual(state,f.state.to_dict())

    def test_p12_archived_internal_memory_stays_absent_with_external_queries_enabled(self):
        from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand,LifecycleAction
        from continuity_engine.services.permission_service import PermissionService
        from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
        f=self.f;f.base.event('p16-internal',content='continuity internal history');f.submit();context=f.last_context
        permission=PermissionService(JsonPermissionRepository(f.runtime.data_root),clock=f.runtime.clock.now)
        grant=permission.create_permission(f.state.subject_id,permission_id='p16-memory-maintenance',permission_type='TEST',name='TEST',description='TEST',
            scope=['*'],capabilities=['memory.lifecycle.archive'],source='TEST',reason='TEST').permission
        approved={};service=f.core.memory_lifecycle(permission,confirmation_verifier=lambda c:approved.get(c.confirmation_id)==c.canonical_hash())
        memory=f.core.memory.load_memory(f.state.subject_id,'memory:p16-internal');now=f.runtime.clock.now()
        command=MemoryLifecycleCommand('p16-archive',f.state.subject_id,'TEST',memory.memory_id,LifecycleAction.ARCHIVE,memory.revision,
            memory.canonical_hash(),grant.permission_id,0,memory.scope,'explicit TEST archive',now,now+timedelta(hours=1),
            'p16-archive-confirm',tuple(sorted(service.source_snapshot(memory).items())))
        approved[command.confirmation_id]=command.canonical_hash();state=f.state.to_dict();service.submit(command)
        self.assertFalse(f.core.current(context));f.next_round()
        ids={x.stable_id for x in f.last_context.route.manifest.candidates}
        self.assertNotIn(memory.memory_id,ids);self.assertNotIn('p16-internal',ids)
        self.assertEqual(state,f.state.to_dict());self.assertTrue(f.external.cached())

    def test_secret_in_result_and_material_denial_never_reach_cache_or_state(self):
        from unittest.mock import patch
        f=self.f;state=f.state.to_dict()
        def hook(value):value['candidates'][0].update(content=SECRET_MARKER,content_hash=digest(SECRET_MARKER));return value
        f.fake.result_hook=hook
        with self.assertRaises(IntegrationExecutionError):f.submit()
        self.assertFalse(any(SECRET_MARKER.encode() in p.read_bytes() for p in f.runtime.data_root.rglob('*') if p.is_file()))
        f.fake.result_hook=None
        with patch.object(f.broker,'material_allowed',side_effect=lambda d,v:'candidates' not in v):
            with self.assertRaises(IntegrationExecutionError):f.next_round()
        self.assertEqual(f.registry.cached(),());self.assertEqual(state,f.state.to_dict())


if __name__=='__main__':unittest.main()
