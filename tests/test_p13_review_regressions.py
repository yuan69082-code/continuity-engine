"""Additional P13 invariants; writes are confined to disposable TEST fixtures."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.expression import ExpressionValidationError
from continuity_engine.domain.events import StateMutation, ChangeOperation, EventClassification
from continuity_engine.services.context_router_service import ContextPermissionDecision
from continuity_engine.testing.p13_expression_fixture import P13Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class P13ReviewProbes(unittest.TestCase):
    def fixture(self, **options):
        temp = tempfile.TemporaryDirectory(prefix='p13-rv-')
        self.addCleanup(temp.cleanup)
        return P13Fixture(Path(temp.name), **options)

    @staticmethod
    def revoke_expression(f):
        permissions = f.core.action_gate._permissions
        permissions._grants = [replace(g, revoked=True) if g.permission == 'expression:emit' else g
                               for g in permissions._grants]
        assert any(g.permission == 'expression:emit' and g.revoked for g in permissions._grants)

    def test_revoked_expression_grant_during_presentation_blocks_new_artifact(self):
        f = self.fixture()
        request = f.request()
        f.presentation.on_present = lambda: self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertIsNone(f.app.ledger.load_completed(request['requestId']))

    def test_revoked_expression_grant_after_action_blocks_first_presentation(self):
        f = self.fixture()
        request = f.request()
        def change_permission(point, operation):
            if point == 'after_c1_action_completed':
                self.revoke_expression(f)
        f.app.adapter.service._fault_injector = change_permission
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)
        self.assertEqual(f.presentation.calls, 0)

    def test_historical_receipts_do_not_authorize_new_consumption_after_grant_revocation(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        f.reopen()
        self.revoke_expression(f)
        before = tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises((ExpressionValidationError, IntegrationExecutionError)):
            f.submit(request)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root), before)

    def test_omitted_relationship_source_does_not_influence_expression(self):
        f = self.fixture()
        f.event('review-formal', classification=EventClassification.STATE_CHANGE, mutations=[
            StateMutation('relationship.interaction_preferences', ChangeOperation.SET,
                          ['formal'], 'Explicit isolated review fixture preference.')])
        # A valid bounded source may omit a section. The omitted section is also
        # explicitly denied by exact-reference policy; all selected sources stay valid.
        source = next(b.source for b in f.core.router._bindings if b.source.source_id == 'engine.subject-state')
        original_retrieve = source.retrieve
        def omit_relationship(query):
            batch = original_retrieve(query)
            return replace(batch, candidates=tuple(c for c in batch.candidates
                           if not c.stable_id.endswith(':relationship')))
        source.retrieve = omit_relationship
        original_authorize = f.permission.authorize_reference
        f.permission.authorize_reference = lambda request, reference: (
            ContextPermissionDecision(False, 'REFERENCE_REVOKED', 'review-v1')
            if reference.stable_id.endswith(':relationship') else original_authorize(request, reference))
        request = f.request()
        try:
            result = f.submit(request)
        except IntegrationExecutionError:
            return  # Missing required expression basis may fail closed.
        context = f.context(request)
        self.assertFalse(any(c.stable_id.endswith(':relationship') for c in context.route.manifest.candidates))
        self.assertEqual(f.artifact(request).decision.layout, 'plain',
                         'Expression used a relationship source absent from and unauthorized for this Context')

    def test_revoked_expression_grant_before_action_control_blocks(self):
        f = self.fixture()
        self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):
            f.submit()
        self.assertEqual(f.presentation.calls, 0)
        self.assertEqual(f.adapter.effect_count, 0)

    def test_old_context_revocation_control_still_blocks(self):
        f = self.fixture()
        request = f.request()
        f.submit(request)
        f.permission.references_allowed = False
        with self.assertRaises(IntegrationExecutionError):
            f.submit(request)

    def test_unchanged_restart_control_preserves_body_and_zero_new_effect(self):
        f = self.fixture(expression_mode='REFUSE')
        request = f.request()
        first = f.submit(request)
        effects, credits = f.adapter.effect_count, f.adapter.credits
        f.reopen()
        self.assertEqual(f.submit(request).to_dict(), first.to_dict())
        self.assertEqual((f.adapter.effect_count, f.adapter.credits), (effects, credits))
        self.assertEqual(f.provider.calls, 0)


class P13AdjacentBoundaries(unittest.TestCase):
    fixture = P13ReviewProbes.fixture
    revoke_expression = staticmethod(P13ReviewProbes.revoke_expression)

    def change_grant(self, f, **changes):
        provider=f.core.action_gate._permissions
        provider._grants=[replace(g,**changes) if g.permission=='expression:emit' else g for g in provider._grants]

    def seed_styles(self,f):
        values={'identity.expression_preferences':['concise','emphasis'],
                'relationship.interaction_preferences':['formal'],
                'emotion_state.current_state':'alert','emotion_state.intensity':0.8,
                'emotion_state.updated_at':f.runtime.clock.now().isoformat(),
                'emotion_state.confidence':0.9,'emotion_state.baseline':0.2}
        f.event('style-seed',classification=EventClassification.STATE_CHANGE,mutations=[
            StateMutation(k,ChangeOperation.SET,v,'Explicit isolated review preference.') for k,v in values.items()])

    def deny_section(self,f,section):
        old=f.permission.authorize_reference
        f.permission.authorize_reference=lambda request,ref: (
            ContextPermissionDecision(False,'REFERENCE_REVOKED','review-v1')
            if ref.stable_id.endswith(':'+section) else old(request,ref))

    def omit_section(self,f,section):
        source=next(b.source for b in f.core.router._bindings if b.source.source_id=='engine.subject-state')
        old=source.retrieve
        source.retrieve=lambda query:replace((batch:=old(query)),candidates=tuple(
            c for c in batch.candidates if not c.stable_id.endswith(':'+section)))

    def test_expiry_at_boundary_before_presentation(self):
        f=self.fixture();r=f.request()
        def expire(point,operation):
            if point=='after_c1_action_completed':self.change_grant(f,expires_at=f.runtime.clock.now())
        f.app.adapter.service._fault_injector=expire
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.presentation.calls,0)
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))
        self.assertEqual((f.adapter.effect_count,f.adapter.credits),(1,1))

    def test_expiry_during_presentation_blocks_artifact(self):
        f=self.fixture();r=f.request()
        f.presentation.on_present=lambda:self.change_grant(f,expires_at=f.runtime.clock.now())
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.presentation.calls,1)
        self.assertIsNone(f.app.ledger.load_operation(r['requestId']).domain)

    def test_current_confirmation_withdrawal_after_action(self):
        f=self.fixture();r=f.request()
        def withdraw(point,operation):
            if point=='after_c1_action_completed':f.constraints.confirmation_allowed=False
        f.app.adapter.service._fault_injector=withdraw
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.presentation.calls,0)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits),(1,1))

    def test_confirmation_withdrawn_inside_port(self):
        f=self.fixture();r=f.request()
        f.presentation.on_present=lambda:setattr(f.constraints,'confirmation_allowed',False)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_current_all_consumption_entries_deny_and_keep_facts(self):
        for change in ('revoke','expire','confirmation','scope','subject'):
            with self.subTest(change=change):
                f=self.fixture();r=f.request();original=f.submit(r);f.reopen()
                if change=='revoke':self.revoke_expression(f)
                if change=='expire':self.change_grant(f,expires_at=f.runtime.clock.now())
                if change=='confirmation':f.constraints.confirmation_allowed=False
                if change=='scope':self.change_grant(f,scopes=['somewhere.else'])
                if change=='subject':self.change_grant(f,subject_id='another-subject')
                before=tree_inventory_hash(f.runtime.data_root)
                with self.assertRaises((ExpressionValidationError,IntegrationExecutionError)):f.submit(r)
                with self.assertRaises((ExpressionValidationError,IntegrationExecutionError)):
                    f.app.adapter.service.query_request(r['requestId'])
                view=f.app.adapter.service.expression_outcome(r['requestId'])
                self.assertEqual(view['status'],'CURRENTLY_UNAVAILABLE');self.assertIsNone(view['artifact'])
                self.assertEqual(view['verified_facts']['request_id'],r['requestId'])
                self.assertEqual(f.app.ledger.load_completed(r['requestId']),original)
                self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
                self.assertEqual((f.provider.calls,f.adapter.execute_calls),(0,0))
                self.assertEqual((f.adapter.effect_count,f.adapter.credits),(1,1))

    def test_confirmation_identity_removal_not_recreated_by_replay(self):
        f=self.fixture();r=f.request();f.submit(r)
        f.constraints.confirmed_ids.clear()
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises((ExpressionValidationError,IntegrationExecutionError)):f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_resources_can_deny_current_consumption_without_new_charge(self):
        from continuity_engine.domain.action import ResourceLimits,ActionType
        f=self.fixture();r=f.request();f.submit(r)
        f.core.limits=ResourceLimits(allowed_action_types=[ActionType.NO_ACTION])
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises((ExpressionValidationError,IntegrationExecutionError)):f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits),(1,1))

    def test_authority_can_restore_access_without_repeat_effects(self):
        f=self.fixture();r=f.request();first=f.submit(r);f.reopen();self.revoke_expression(f)
        with self.assertRaises((ExpressionValidationError,IntegrationExecutionError)):f.submit(r)
        self.change_grant(f,revoked=False)
        before=tree_inventory_hash(f.runtime.data_root)
        self.assertEqual(f.submit(r),first)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual((f.provider.calls,f.adapter.execute_calls),(0,0))

    def test_revocation_does_not_hide_unknown_receipt(self):
        from continuity_engine.domain.action_capability import ReceiptQuery
        f=self.fixture();r=f.request();f.submit(r);f.reopen();self.revoke_expression(f)
        f.adapter.query=lambda request:ReceiptQuery.UNKNOWN
        before=tree_inventory_hash(f.runtime.data_root)
        from continuity_engine.domain.errors import CapabilityValidationError
        with self.assertRaises(CapabilityValidationError):f.app.adapter.service.expression_outcome(r['requestId'])
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)

    def test_omitted_or_denied_sections_use_only_authorized_defaults(self):
        for section in ('identity','relationship','emotion_state'):
            for condition in ('missing','denied','missing_and_denied'):
                with self.subTest(section=section,condition=condition):
                    f=self.fixture(body='A formed judgment.\n\nStill the same.');self.seed_styles(f)
                    if condition!='denied':self.omit_section(f,section)
                    if condition!='missing':self.deny_section(f,section)
                    r=f.request()
                    try:f.submit(r)
                    except IntegrationExecutionError:
                        self.assertIsNone(f.app.ledger.load_completed(r['requestId']));continue
                    d=f.artifact(r).decision
                    self.assertFalse(any(x.stable_source_id.endswith(':'+section) for x in f.context(r).composition.snapshot.fragments))
                    if section=='identity':self.assertFalse(d.compact);self.assertFalse(d.emphasis)
                    if section=='relationship':self.assertEqual(d.layout,'plain')
                    if section=='emotion_state':self.assertFalse(d.emphasis)

    def test_each_style_source_invalidated_during_port_blocks_completion(self):
        for section in ('identity','relationship','emotion_state'):
            with self.subTest(section=section):
                f=self.fixture();self.seed_styles(f);r=f.request()
                f.presentation.on_present=lambda:self.deny_section(f,section)
                with self.assertRaises(IntegrationExecutionError):f.submit(r)
                self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_authorized_three_style_sources_preserve_body_and_authority(self):
        f=self.fixture(body='No agreement.\n\nNo change of stance.');self.seed_styles(f)
        state=f.state.to_dict();r=f.request();f.submit(r)
        self.assertEqual(f.artifact(r).content,'**> No agreement.\n> No change of stance.**')
        self.assertEqual(f.state.to_dict(),state)
        self.assertNotIn('No agreement',str(f.core.expression_policy.last_trace))

    def test_domain_crash_then_revoke_keeps_completed_fact_without_text(self):
        f=self.fixture();r=f.request()
        def stop(point,operation):
            if point=='after_domain_completed':raise RuntimeError('Controlled R1 domain crash')
        f.app.adapter.service._fault_injector=stop
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertIsNotNone(f.app.ledger.load_operation(r['requestId']).domain)
        f.reopen();self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertIsNotNone(f.app.ledger.load_completed(r['requestId']))
        self.assertEqual(f.app.adapter.service.expression_outcome(r['requestId'])['status'],'CURRENTLY_UNAVAILABLE')
        before=tree_inventory_hash(f.runtime.data_root)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(tree_inventory_hash(f.runtime.data_root),before)
        self.assertEqual((f.adapter.effect_count,f.adapter.credits,f.adapter.execute_calls),(1,1,0))

    def test_committed_evolution_recovers_after_expression_revocation(self):
        f=self.fixture();r=f.request();original=f.provider.think
        f.provider.think=lambda perception,budget:replace(original(perception,budget),
            update_subject_state=True,proposed_mutations=[StateMutation('continuity.current_focus',
                ChangeOperation.SET,['review-approved-focus'],'Explicit TEST proposal.')])
        def stop(point,operation):
            if point=='after_evolution_committed':raise RuntimeError('Controlled R1 Evolution crash')
        f.app.adapter.service._fault_injector=stop
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertEqual(f.state.revision,2);state=f.state.to_dict()
        f.reopen();self.revoke_expression(f)
        with self.assertRaises(IntegrationExecutionError):f.submit(r)
        self.assertIsNotNone(f.app.ledger.load_completed(r['requestId']))
        self.assertEqual(f.state.to_dict(),state)
        view=f.app.adapter.service.expression_outcome(r['requestId'])
        self.assertEqual(view['status'],'CURRENTLY_UNAVAILABLE')
        self.assertEqual(view['verified_facts']['state_revision'],2)
        self.assertIsNotNone(view['verified_facts']['update_id'])
        self.assertEqual((f.provider.calls,f.adapter.execute_calls),(0,0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
