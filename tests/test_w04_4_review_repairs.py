"""D-092 review counterexamples through real C1/native Thinking and dispatch.

The TEST provider interprets an explicit fixture input grammar and reads actual
composed state. It does not edit State or fabricate an external receipt.
"""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from continuity_engine.domain.events import ChangeOperation, StateMutation
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture


class EntryReviewRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='w44-review-')
        self.f = W04EntryFixture(Path(self.temp.name))
        self.observations = []

    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        print(json.dumps({'test': self.id(), 'review_observations': self.observations}, ensure_ascii=False))
        capture_failure(self, Path(self.temp.name))
        self.temp.cleanup()

    def state_provider(self, *, native_derive=False):
        original = self.f.provider.think
        def think(perception, budget):
            result = original(perception, budget)
            fragments = perception.continuity_context.composition.snapshot.fragments
            current = next((json.loads(row.content)['content'] for row in fragments
                            if row.source_id == 'engine.current-input'), None)
            sections = {row.stable_source_id.rsplit(':', 1)[-1]: json.loads(row.content)
                        for row in fragments if row.source_id == 'engine.subject-state'}
            focus = sections.get('continuity', {}).get('current_focus', [])
            proposed = []
            for prefix, field in (('记下关注：', 'continuity.current_focus'),
                                  ('记下判断：', 'intentions.judgments')):
                if current and current.startswith(prefix):
                    proposed = [StateMutation(field, ChangeOperation.APPEND, current[len(prefix):],
                                              'TEST proposal formed from the actual raw input')]
            if current and current.startswith('重存关注：'):
                proposed = [StateMutation('continuity.current_focus', ChangeOperation.SET,
                    focus + [current[len('重存关注：'):]], 'TEST retain current values through SET')]
            if (current == '根据当前关注形成判断。' or current is None and native_derive) and focus:
                field = 'continuity.current_focus' if current is None else 'intentions.judgments'
                proposed = [StateMutation(field, ChangeOperation.APPEND,
                                          '关联判断：' + focus[-1], 'TEST interpretation of actual composed focus')]
            if proposed:
                self.observations.append({'provider_proposal':[(m.field_path,m.value) for m in proposed],
                                          'native':current is None})
                return replace(result, result_summary='保存本次内部关注。', update_subject_state=True,
                               proposed_mutations=proposed, suggest_future_user_contact=False,
                               contact_intent=None, expression_mode='SILENCE', should_wait=True)
            if current in {'回顾本地关注。', '回顾本地判断。'}:
                values = focus if current == '回顾本地关注。' else sections.get('intentions', {}).get('judgments', [])
                return replace(result, result_summary='当前可用：' + '；'.join(values),
                               suggest_future_user_contact=False, expression_mode='RESPOND')
            return result
        self.f.provider.think = think

    def _append_chain(self, *, withdraw, reopen):
        f = self.f; self.state_provider()
        private, local = 'A_PRIVATE_FOCUS_812', 'B_LOCAL_FOCUS_937'
        f.submit('记下关注：' + private)
        self.assertIn(private, f.state.continuity.current_focus)
        first = f.app.ledger.load_operation(f.last_request['requestId'])
        self.assertIsNotNone(first.evolution)
        if withdraw:
            f.configure('entry:B', read_from=('entry:B',))
        f.advance(); f.submit('记下关注：' + local, entry='entry:B')
        self.assertIn(local, f.state.continuity.current_focus)
        if reopen:
            f.reopen(); self.state_provider()
        f.advance(); outcome = f.submit('回顾本地关注。', entry='entry:B')
        self.assertEqual(outcome.status, 'completed')
        context = '\n'.join(r.content for r in f.provider.inputs[-1].continuity_context.composition.snapshot.fragments)
        emitted = f.ports['entry:B'].store.load()['view']['sent']
        self.observations.append(dict(case='state-append', withdraw=withdraw, reopened=reopen,
            a_in_context=private in context, b_in_context=local in context,
            a_in_expression=private in emitted, b_in_expression=local in emitted,
            state_retains_both=all(v in f.state.continuity.current_focus for v in (private,local)),
            original_event=first.evolution.event_id, revision=f.state.revision))
        self.assertIn(local, context); self.assertIn(local, emitted)
        self.assertIn(private, f.state.continuity.current_focus)  # history/state is not erased
        if withdraw:
            self.assertNotIn(private, context); self.assertNotIn(private, emitted)
        else:
            self.assertIn(private, context); self.assertIn(private, emitted)

    def test_state_append_withdrawal_keeps_b_content_without_a_marker(self):
        self._append_chain(withdraw=True, reopen=False)

    def test_state_append_withdrawal_survives_reopen(self):
        self._append_chain(withdraw=True, reopen=True)

    def test_state_append_authorized_positive_control(self):
        self._append_chain(withdraw=False, reopen=False)

    def _derived_chain(self, *, native, withdraw, reopen):
        f = self.f; self.state_provider()
        private = 'A_DERIVED_PRIVATE_627'
        f.submit('记下关注：' + private)
        if native:
            f.start_native(); self.state_provider(native_derive=True)
            f.continue_native()
            f.native_mode = False
        else:
            f.advance(); f.submit('根据当前关注形成判断。', entry='entry:B')
        field_values = lambda: f.state.continuity.current_focus if native else f.state.intentions.judgments
        self.assertIn('关联判断：' + private, field_values())
        if withdraw: f.configure('entry:B', read_from=('entry:B',))
        f.reopen(); self.state_provider()
        prefix = '记下关注：' if native else '记下判断：'
        f.advance(); f.submit(prefix+'B_INDEPENDENT_JUDGMENT', entry='entry:B')
        if reopen: f.reopen(); self.state_provider()
        f.advance(); f.submit('回顾本地关注。' if native else '回顾本地判断。', entry='entry:B')
        context = '\n'.join(r.content for r in f.provider.inputs[-1].continuity_context.composition.snapshot.fragments)
        sent = f.ports['entry:B'].store.load()['view']['sent']
        self.observations.append(dict(case='derived-state', native=native, withdraw=withdraw,
                                      private_in_context=private in context, private_in_expression=private in sent))
        self.assertIn('B_INDEPENDENT_JUDGMENT', context); self.assertIn('B_INDEPENDENT_JUDGMENT', sent)
        self.assertIn('关联判断：'+private, field_values())
        if withdraw:
            self.assertNotIn(private, context); self.assertNotIn(private, sent)
        else:
            self.assertIn(private, context); self.assertIn(private, sent)

    def test_indirect_state_derivation_keeps_original_source_after_reopen(self):
        self._derived_chain(native=False, withdraw=True, reopen=True)

    def test_native_thinksession_state_derivation_keeps_original_source_after_reopen(self):
        self._derived_chain(native=True, withdraw=True, reopen=True)

    def test_native_state_derivation_authorized_positive_control(self):
        self._derived_chain(native=True, withdraw=False, reopen=False)

    def test_set_retained_values_does_not_relabel_original_source(self):
        f = self.f; self.state_provider()
        f.submit('记下关注：A_SET_PRIVATE')
        f.advance(); f.submit('重存关注：B_SET_LOCAL', entry='entry:B')
        f.configure('entry:B', read_from=('entry:B',))
        f.advance(); f.submit('回顾本地关注。', entry='entry:B')
        context='\n'.join(r.content for r in f.provider.inputs[-1].continuity_context.composition.snapshot.fragments)
        # B's SET was derived while A was readable, so the newly derived value
        # also carries A. A later independent raw input remains usable.
        self.assertNotIn('A_SET_PRIVATE', context)
        self.assertIn('A_SET_PRIVATE', f.state.continuity.current_focus)
        f.advance(); f.submit('记下关注：B_NEW_INDEPENDENT', entry='entry:B')
        f.advance(); f.submit('回顾本地关注。', entry='entry:B')
        self.assertIn('B_NEW_INDEPENDENT', f.ports['entry:B'].store.load()['view']['sent'])
        self.assertNotIn('A_SET_PRIVATE', f.ports['entry:B'].store.load()['view']['sent'])

    def test_state_query_and_same_request_reopen_do_not_repeat_submission(self):
        f=self.f; self.state_provider(); f.submit('记下关注：A_REPLAY_PRIVATE')
        f.configure('entry:B', read_from=('entry:B',))
        f.advance(); result=f.submit('记下关注：B_REPLAY_LOCAL', entry='entry:B')
        request,message=f.last_request,f.last_message
        f.reopen(); self.state_provider()
        before=(f.state.revision, len(f.provider.inputs), f.ports['entry:B'].effect_count, f.ports['entry:B'].credits)
        event_id=f.app.ledger.load_operation(request['requestId']).evolution.event_id
        for _ in range(2):
            _,view=f.entries.scoped_state(request['requestId'])
            self.assertNotIn('A_REPLAY_PRIVATE',view['continuity']['current_focus'])
            self.assertIn('B_REPLAY_LOCAL',view['continuity']['current_focus'])
            from continuity_engine.domain.errors import IntegrationExecutionError
            with self.assertRaises(IntegrationExecutionError) as raised:
                f.entries.receive(request,message)
            self.assertEqual(str(raised.exception.__cause__),'EXPRESSION_CONTEXT_STALE_OR_UNAUTHORIZED')
            self.assertEqual(f.app.ledger.load_operation(request['requestId']).evolution.event_id,event_id)
        self.assertEqual(before,(f.state.revision,len(f.provider.inputs),f.ports['entry:B'].effect_count,f.ports['entry:B'].credits))

    def test_state_read_binding_change_is_rejected_before_provider(self):
        f=self.f; self.state_provider(); f.submit('记下关注：A_CURRENT_SOURCE')
        fired=[]; armed=[]
        lineage=f.entries._state_lineage
        def prepared(*args,**kwargs):
            value=lineage(*args,**kwargs); armed.append(True); return value
        f.entries._state_lineage=prepared
        def read(binding):
            if binding.entry_id=='entry:B' and armed and not fired:
                fired.append(True); f.configure('entry:B',read_from=('entry:B',))
            return True
        f.entries.authorize_read=read
        before=(len(f.provider.inputs),f.state.revision,f.ports['entry:B'].effect_count,f.ports['entry:B'].credits)
        from continuity_engine.domain.errors import IntegrationExecutionError
        with self.assertRaises(IntegrationExecutionError) as raised:
            f.submit('回顾本地关注。',entry='entry:B')
        self.assertTrue(armed)
        self.assertEqual(fired,[True])
        self.assertEqual(before,(len(f.provider.inputs),f.state.revision,f.ports['entry:B'].effect_count,f.ports['entry:B'].credits))

    def test_redacted_matter_does_not_block_independent_b_expression(self):
        f=self.f
        f.submit('A_PRIVATE_MATTER 应该怎样处理？')
        f.entries.adopt_matter(f.last_request['requestId'])
        f.configure('entry:B',read_from=('entry:B',))
        f.advance(); outcome=f.submit('B_LOCAL_ALLOWED 普通材料。',entry='entry:B')
        self.assertEqual(outcome.status,'completed')
        context='\n'.join(r.content for r in f.provider.inputs[-1].continuity_context.composition.snapshot.fragments)
        self.assertNotIn('A_PRIVATE_MATTER',context)
        self.assertIn('B_LOCAL_ALLOWED',context)
        self.assertEqual((f.ports['entry:B'].effect_count,f.ports['entry:B'].credits),(1,1))
        self.assertIn('B_LOCAL_ALLOWED',f.ports['entry:B'].store.load()['view']['sent'])

    def _final_observation(self, change):
        f = self.f
        f.submit('周六选河边店还是山坡店？')
        f.entries.adopt_matter(f.last_request['requestId'])
        f.start_native()
        port = f.ports['entry:B']; original_execute, original_observe = port.execute, port.observe
        active = []; fired = []; guards = []; armed = []
        device=f.devices['entry:B']; prior_connection=device.connection_guard
        prior_contact=f.entries.authorize_contact
        def late_pause():
            if active and armed and not fired:
                before=port.store.load()
                f.entries.pause_contact('entry:A',True,expected_revision=f.repo.load()['revision'])
                fired.append(dict(change=change,native_state_unchanged=port.store.load()==before,
                                  guard_request=guards[-1],after_observation=True))
        class LateConnection:
            def observe(self,use): pass
            def __call__(self,request,*,purpose): late_pause()
        if change=='late-connection': device.connection_guard=LateConnection()
        if change=='late-permission':
            def contact(binding):
                allowed=prior_contact(binding); late_pause(); return allowed
            f.entries.authorize_contact=contact
        def execute(request, command, guard):
            def final_guard():
                guards.append(request.capability_request_id); active.append(True)
                try:
                    return guard()
                finally:
                    active.pop()
            return original_execute(request, command, final_guard)
        def observe(use):
            observed = original_observe(use)
            if active and not fired:
                if change.startswith('late-'):
                    armed.append(True)
                    return observed
                before = port.store.load()
                if change == 'transfer': f.configure('entry:B', read_from=('entry:B',))
                elif change == 'binding': f.configure('entry:B', user_account='user-account:B-new',
                                                     recipient_account='user-account:B-new')
                elif change == 'pause': f.entries.pause_contact('entry:A', True, expected_revision=f.repo.load()['revision'])
                fired.append(dict(change=change, native_state_unchanged=port.store.load()==before,
                                  guard_request=guards[-1], observed_hash=observed.state_hash))
            return observed
        port.execute, port.observe = execute, observe
        revision = f.state.revision
        try:
            f.continue_native()
        except AssertionError as exc:
            # A runtime wait is evidence, never a pass or a fabricated result.
            if not str(exc).startswith('TEST_NATIVE_CONTINUATION_NOT_COMPLETED:'): raise
            self.observations.append({'runtime_wait':f.host.query()['activity']})
        finally:
            port.execute, port.observe = original_execute, original_observe
            device.connection_guard=prior_connection; f.entries.authorize_contact=prior_contact
        self.assertEqual(len(fired),1); self.assertTrue(fired[0]['native_state_unchanged'])
        self.observations.append(dict(case='final-observation', fired=fired, guards=guards,
            effects=port.effect_count, credits=port.credits, before_revision=revision, after_revision=f.state.revision))
        expected = 1 if change == 'none' else 0
        self.assertEqual((port.effect_count, port.credits), (expected, expected))
        if change == 'transfer':
            # The old Context really lost read authority. Do not demand that
            # its revision advance: prove a fresh legal internal step instead.
            f.native_mode = False; f.reopen(); self.state_provider()
            f.advance(); f.submit('记下关注：B_AFTER_REFUSAL_INTERNAL', entry='entry:B')
            self.assertIn('B_AFTER_REFUSAL_INTERNAL', f.state.continuity.current_focus)
            self.assertEqual((port.effect_count, port.credits), (0,0))
        self.assertGreater(f.state.revision, revision, 'independent lawful internal cognition must survive')

    def test_final_observation_transfer_withdrawal_zero_effect_and_cost(self):
        self._final_observation('transfer')

    def test_final_observation_binding_change_zero_effect_and_cost(self):
        self._final_observation('binding')

    def test_final_observation_contact_pause_zero_effect_and_cost(self):
        self._final_observation('pause')

    def test_final_observation_unchanged_positive_control(self):
        self._final_observation('none')

    def test_remaining_connection_callback_pause_zero_effect_and_cost(self):
        self._final_observation('late-connection')

    def test_remaining_permission_callback_pause_zero_effect_and_cost(self):
        self._final_observation('late-permission')


if __name__ == '__main__':
    unittest.main()
