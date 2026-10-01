"""One bounded diagnosis of formed native intentions and original outbox."""
import json,unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
original=W04EntryFixture.continue_native
def run(self):
    try:return original(self)
    finally:
        sessions=self.entries.native_thinking._repository.list_think_sessions(self.state.subject_id)
        print(json.dumps(dict(stage='before-TEST-cleanup',sessions=[dict(think_id=s.think_id,
            status=s.status.value,contact=s.result.contact_intent if s.result else None,
            contact_flag=s.result.suggest_future_user_contact if s.result else None,
            wait=s.result.should_wait if s.result else None) for s in sessions],
            outbox=self.execution.outbox.load(),effects=self.ports['entry:B'].effect_count),default=str))
W04EntryFixture.continue_native=run
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(
    'tests.test_w04_4_boundaries.EntryBoundaryTests.test_native_unknown_delivery_does_not_prevent_later_cognition'))
raise SystemExit(not result.wasSuccessful())
