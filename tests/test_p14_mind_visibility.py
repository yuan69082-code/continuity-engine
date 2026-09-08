from datetime import timedelta
import hashlib
from pathlib import Path
import tempfile
import unittest


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class MindVisibilityTests(unittest.TestCase):
    def setUp(self):
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        self.temp = tempfile.TemporaryDirectory(prefix='p14-owner-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.f = P14Fixture(self.root)
        self.f.runtime.clock.advance(timedelta(hours=2))
        self.f.opportunity('owner-view-origin')
        self.view = self.f.owner_projection()

    def test_owner_detailed_projection_is_real_and_zero_write(self):
        before = inventory(self.root)
        result = self.view.read('test-owner-session')
        self.assertEqual(result['mind'], self.f.state.intentions.dynamic_mind)
        self.assertTrue(result['history'])
        self.assertEqual(result['source_revision'], self.f.state.revision)
        self.assertEqual(before, inventory(self.root))

    def test_self_claimed_owner_and_non_owner_are_rejected_without_write(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        before = inventory(self.root)
        for token in ('owner', 'test-other-session', '', 'forged-session'):
            with self.subTest(token=token), self.assertRaises(MindAccessError):
                self.view.read(token)
        self.assertEqual(before, inventory(self.root))

    def test_private_mode_does_not_delete_or_change_cognition(self):
        from continuity_engine.services.mind_projection_service import MindVisibilityPolicy, MindAccessError
        from continuity_engine.domain.dynamic_mind import MindState
        before = inventory(self.root)
        state = MindState.from_dict(self.f.state.intentions.dynamic_mind)
        at = state.updated_at + timedelta(minutes=1)
        expected = self.f.core.mind.dynamics.advance(state, at=at)
        private = self.view.with_policy(MindVisibilityPolicy(mode='PRIVATE'))
        with self.assertRaises(MindAccessError):
            private.read('test-owner-session')
        actual = self.f.core.mind.dynamics.advance(state, at=at)
        self.assertEqual(actual.state.to_dict(), expected.state.to_dict())
        self.assertEqual(actual.influence, expected.influence)
        self.assertEqual(before, inventory(self.root))

    def test_export_and_current_permission_are_separate(self):
        from continuity_engine.services.mind_projection_service import MindAccessError
        before = inventory(self.root)
        with self.assertRaises(MindAccessError):
            self.view.read('test-owner-session', export=True)
        self.assertEqual(before, inventory(self.root))
        self.f.revoke_owner_view()
        after_revoke = inventory(self.root)
        with self.assertRaises(MindAccessError):
            self.view.read('test-owner-session')
        self.assertEqual(after_revoke, inventory(self.root))

    def test_summary_hides_detail_and_denial_has_zero_state_reads(self):
        from unittest.mock import patch
        from continuity_engine.services.mind_projection_service import MindVisibilityPolicy, MindAccessError
        summary=self.view.with_policy(MindVisibilityPolicy(mode='SUMMARY'))
        before=inventory(self.root);value=summary.read('test-owner-session')
        self.assertNotIn('mind',value);self.assertNotIn('history',value)
        self.assertEqual(value['summary']['desire_count'],len(self.f.state.intentions.dynamic_mind['desires']))
        with patch.object(self.view.states,'load',side_effect=AssertionError('unauthorized state read')) as read:
            with self.assertRaises(MindAccessError):self.view.read('test-other-session')
            read.assert_not_called()
        self.assertEqual(before,inventory(self.root))

    def test_export_requires_current_grant_even_when_policy_allows(self):
        from continuity_engine.services.mind_projection_service import MindVisibilityPolicy,MindAccessError
        view=self.view.with_policy(MindVisibilityPolicy(export_allowed=True))
        with self.assertRaises(MindAccessError):view.read('test-owner-session',export=True)
        self.f.view_permissions.create_permission(self.f.state.subject_id,permission_id='p14-explicit-export',
            permission_type='TEST',name='TEST export',description='Explicit isolated export consent',
            scope=['mind:TEST:'+self.f.state.subject_id+':test-owner'],capabilities=['mind:export'],
            source='TEST',reason='Explicit TEST export control')
        before=inventory(self.root)
        self.assertEqual(view.read('test-owner-session',export=True)['mind'],self.f.state.intentions.dynamic_mind)
        self.assertEqual(before,inventory(self.root))

    def test_identity_change_during_read_denies_result(self):
        from unittest.mock import patch
        from continuity_engine.services.mind_projection_service import MindAccessError
        original=self.view.identity.resolve('test-owner-session')
        before=inventory(self.root)
        with patch.object(self.view.identity,'resolve',side_effect=[original,None]):
            with self.assertRaises(MindAccessError):self.view.read('test-owner-session')
        self.assertEqual(before,inventory(self.root))

    def test_privacy_switch_does_not_change_normal_native_cognition(self):
        from continuity_engine.services.mind_projection_service import MindVisibilityPolicy
        from continuity_engine.testing.p14_mind_fixture import P14Fixture
        f=self.f
        snapshot=f.manager.create_snapshot(f.runtime.descriptor.sandbox_id,expected_revision=f.state.revision)
        branches=[f.manager.create_branch(f.runtime.descriptor.sandbox_id,snapshot.snapshot_id) for _ in range(2)]
        results=[]
        for branch,mode in zip(branches,('DETAILED','PRIVATE')):
            runtime=f.manager.open_runtime(f.runtime.descriptor.sandbox_id,branch_id=branch)
            fork=P14Fixture(self.root,runtime=runtime,manager=f.manager)
            view=fork.owner_projection().with_policy(MindVisibilityPolicy(mode=mode))
            self.assertEqual(view.policy.mode,mode)
            fork.runtime.clock.advance(timedelta(minutes=1));value=fork.opportunity('privacy-comparison')
            results.append((fork.state.intentions.dynamic_mind,value.thinking.session.result.expression_mode))
        self.assertEqual(results[0],results[1])


if __name__ == '__main__':
    unittest.main()
