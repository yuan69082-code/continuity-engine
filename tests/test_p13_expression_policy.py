"""P13 normal Engine entry and expression-only invariants."""
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import tempfile
import unittest

from continuity_engine.domain.thinking import ThinkingResult, TokenBudget, ThinkingDepth
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.p13_expression_fixture import P13Fixture
from continuity_engine.domain.expression import ExpressionGenerationError, ExpressionValidationError, ExpressionArtifact
from continuity_engine.domain.errors import IntegrationExecutionError, ThinkingValidationError
from continuity_engine.testing.models import SandboxOperationError
from continuity_engine.testing.persistence import tree_inventory_hash


def formed_result(mode='RESPOND', body='I do not agree with this claim.'):
    return ThinkingResult.create(provider_id='p13-test-thinking', result_summary=body,
        rationale_summary='Explicit synthetic Engine decision; not hidden reasoning.',
        generated_new_thought=True, update_subject_state=False,
        request_more_memory=False, should_wait=mode=='SILENCE',
        suggest_future_user_contact=False,
        token_budget=TokenBudget(100,100,50,ThinkingDepth.LOW),
        expression_mode=mode)


class ExpressionInputTests(unittest.TestCase):
    def test_formed_seven_modes_roundtrip_without_mutating_judgment(self):
        for mode in ('RESPOND','SILENCE','REFUSE','QUESTION','CONFRONT','DEFER','PURSUE'):
            with self.subTest(mode=mode):
                original=formed_result(mode)
                restored=ThinkingResult.from_dict(original.to_dict())
                self.assertEqual(restored.expression_mode,mode)
                self.assertEqual(restored.result_summary,'I do not agree with this claim.')
                self.assertEqual(restored.proposed_mutations,[])

    def test_disabled_normal_core_accepts_explicit_expression_configuration(self):
        with tempfile.TemporaryDirectory(prefix='p13-disabled-') as tmp:
            fixture=P09Fixture(Path(tmp), expression_policy=None)
            result=fixture.submit()
            self.assertIsNotNone(result)
            self.assertIsNone(fixture.core.expression_policy)

    def test_old_thinking_serialization_omits_extension(self):
        value=formed_result().to_dict();del value['expression_mode']
        old=ThinkingResult.from_dict(value)
        self.assertIsNone(old.expression_mode)
        self.assertEqual(old.to_dict(),value)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ThinkingValidationError):
            formed_result('ALTER_PERSONALITY')


class ExpressionPolicyTests(unittest.TestCase):
    def fixture(self,**options):
        temp=tempfile.TemporaryDirectory(prefix='p13-policy-');self.addCleanup(temp.cleanup)
        return P13Fixture(Path(temp.name),**options)

    def test_seven_modes_normal_entry_persist_and_keep_authorities(self):
        for mode in ('RESPOND','SILENCE','REFUSE','QUESTION','CONFRONT','DEFER','PURSUE'):
            with self.subTest(mode=mode):
                f=self.fixture(expression_mode=mode)
                state=f.state.to_dict();request=f.request()
                result=f.submit(request);artifact=f.artifact(request)
                self.assertEqual(artifact.decision.mode,mode)
                self.assertEqual(artifact.content,'' if mode=='SILENCE' else f.body)
                self.assertEqual(artifact.decision.status,'SUBJECT_SILENCE' if mode=='SILENCE' else 'SUBJECT_EXPRESSION')
                self.assertEqual(result.response.content,artifact.content)
                self.assertEqual(f.state.to_dict(),state)
                self.assertEqual(ExpressionArtifact.from_dict(artifact.to_dict()),artifact)
                self.assertEqual(f.presentation.calls,0 if mode=='SILENCE' else 1)
                self.assertNotIn(f.body,str(f.core.expression_policy.last_trace))

    def test_reversing_provider_rejected_no_final_result(self):
        f=self.fixture(expression_mode='REFUSE');f.presentation.behavior='reverse';r=f.request()
        state=f.state.to_dict()
        with self.assertRaises(IntegrationExecutionError) as ctx:f.submit(r)
        self.assertIsInstance(ctx.exception.__cause__,ExpressionGenerationError)
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))
        self.assertIsNone(f.app.ledger.load_operation(r['requestId']).domain)
        self.assertEqual(f.state.to_dict(),state)

    def test_mode_and_binding_changes_rejected(self):
        for behavior in ('mode','binding'):
            with self.subTest(behavior=behavior):
                f=self.fixture();f.presentation.behavior=behavior;r=f.request()
                with self.assertRaises(IntegrationExecutionError) as ctx:f.submit(r)
                self.assertIsInstance(ctx.exception.__cause__,ExpressionGenerationError)
                self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_generation_failure_is_not_subject_silence_or_refusal(self):
        f=self.fixture();f.presentation.behavior='failure';r=f.request()
        with self.assertRaises(IntegrationExecutionError) as ctx:f.submit(r)
        self.assertIsInstance(ctx.exception.__cause__,ExpressionGenerationError)
        self.assertIn('GENERATION_FAILED',str(ctx.exception.__cause__))
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_invalidation_inside_presentation_cannot_complete(self):
        f=self.fixture();r=f.request()
        f.presentation.on_present=lambda:setattr(f.permission,'references_allowed',False)
        with self.assertRaises(IntegrationExecutionError) as ctx:f.submit(r)
        self.assertIsInstance(ctx.exception.__cause__,ExpressionValidationError)
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_expression_gate_off_no_port_call_no_extension(self):
        f=self.fixture(expression_enabled=False);r=f.request()
        with patch.object(f.presentation,'present',side_effect=AssertionError('disabled presentation touched')):
            f.submit(r)
        operation=f.app.ledger.load_operation(r['requestId'])
        self.assertNotIn('expression',operation.domain.to_dict())
        self.assertNotIn('expression_enabled',f.context(r).to_dict())
        self.assertIsNone(operation.domain.expression)

    def test_budget_rejection_keeps_whole_original_body(self):
        f=self.fixture(body='Do not discard the final negation. '*20)
        f.core.expression_policy.maximum_characters=30;r=f.request()
        with self.assertRaises(IntegrationExecutionError) as ctx:f.submit(r)
        self.assertIsInstance(ctx.exception.__cause__,ExpressionGenerationError)
        self.assertEqual(f.presentation.calls,0)
        self.assertIsNone(f.app.ledger.load_completed(r['requestId']))

    def test_silence_does_not_require_visible_output_budget_or_presentation(self):
        f=self.fixture(expression_mode='SILENCE',body='A formed private draft. '*20)
        f.core.expression_policy.maximum_characters=1
        r=f.request();f.submit(r)
        self.assertEqual(f.artifact(r).content,'')
        self.assertEqual(f.artifact(r).decision.status,'SUBJECT_SILENCE')
        self.assertEqual(f.presentation.calls,0)

    def test_protected_root_rejected_zero_writes(self):
        root=Path(__file__).resolve().parents[1]
        # Only inspect fixed source/data inventory; no full repository clone or mutation.
        names=['.continuity-data','.assistant-data']
        if Path('A')==Path('a'):  # Windows native semantics; no invented POSIX folding.
            names.extend(('.CONTINUITY-DATA','.AsSiStAnT-DaTa'))
        for name in names:
            with tempfile.TemporaryDirectory(prefix='p13-protected-') as temp:
                target=Path(temp)/name;target.mkdir();before=tree_inventory_hash(Path(temp))
                for path in (target,target/'child'):
                    with self.assertRaises(SandboxOperationError):P13Fixture(path)
                    self.assertEqual(tree_inventory_hash(Path(temp)),before)
        with self.assertRaises(SandboxOperationError):P13Fixture(root)


if __name__=='__main__':
    unittest.main()
