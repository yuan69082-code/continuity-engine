"""W03 N04: necessary SubjectState core must reach normal Thinking."""
from pathlib import Path
import json
import tempfile
import unittest

from continuity_engine.domain.context_composition import ContextBudget
from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.events import ChangeOperation, EventClassification, StateMutation
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class W03CoreContextTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="w03-core-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_everyday_response_contains_identity_and_relationship_before_thinking(self):
        fixture = P09Fixture(self.root, gates=ContinuityCoreGates(essential_core=True))
        fixture.submit()
        context = fixture.provider.inputs[0].continuity_context
        sources = {f.stable_source_id for f in context.composition.snapshot.fragments}
        subject = fixture.runtime.descriptor.subject_id
        self.assertIn(f"{subject}:identity", sources)
        self.assertIn(f"{subject}:relationship", sources)
        before=tree_inventory_hash(fixture.runtime.data_root)
        status=fixture.core.core_status(context)
        self.assertEqual(status["status"], "CORE_PROVIDED")
        self.assertEqual(status['layers']['core'],2)
        self.assertIn('long_term_memory',status['layers'])
        self.assertIn('temporary_material',status['layers'])
        self.assertEqual(tree_inventory_hash(fixture.runtime.data_root),before)

    def test_missing_core_fails_before_thinking_or_action(self):
        fixture = P09Fixture(self.root, gates=ContinuityCoreGates(essential_core=True))
        fixture.event('remove-core', classification=EventClassification.STATE_CHANGE,
                      mutations=(StateMutation('identity.stable_traits', ChangeOperation.SET,
                                               [], 'Synthetic absence test'),))
        with self.assertRaises(IntegrationExecutionError):
            fixture.submit()
        self.assertEqual(fixture.provider.calls, 0)
        self.assertEqual(fixture.adapter.execute_calls, 0)

    def test_insufficient_budget_does_not_silently_omit_core(self):
        fixture = P09Fixture(self.root, gates=ContinuityCoreGates(essential_core=True),
                             context_budget=ContextBudget(token_limit=1))
        with self.assertRaises(IntegrationExecutionError):
            fixture.submit()
        self.assertEqual(fixture.provider.calls, 0)

    def test_legacy_gate_remains_compatible(self):
        fixture = P09Fixture(self.root, gates=ContinuityCoreGates())
        fixture.submit()
        self.assertEqual(fixture.provider.calls, 1)

    def test_capability_model_replacement_receives_the_same_core_contract(self):
        fixture=P09Fixture(self.root,gates=ContinuityCoreGates(essential_core=True),
                           thinking_mode=IntegrationThinkingMode.CAPABILITY)
        result=fixture.submit()
        summary=json.loads(result.capability_request.input.perception_summary)
        core={row['source'].rsplit(':',1)[-1]:row for row in summary['context']
              if row['authority']=='confirmed_state'}
        self.assertIn('identity',core)
        self.assertIn('relationship',core)
        self.assertIn('stable_traits',core['identity']['content'])
        self.assertIn('current_status',core['relationship']['content'])


if __name__ == "__main__":
    unittest.main()
