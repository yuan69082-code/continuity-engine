"""Observe the existing real P16 path; absence is NOT_IMPLEMENTED, not fabricated FAIL."""
import json, tempfile, importlib.util
from continuity_engine.testing.p16_provider_fixture import P16Fixture
with tempfile.TemporaryDirectory(prefix='w04-3-before-') as root:
    f=P16Fixture(root);f.query='skill:find a temporary history tool'
    result=f.submit()
    facts=f.fake.facts()
    print(json.dumps(dict(status=result.status,discovery_queries=f.external_calls,
        query_receipts=len(facts),candidate_is_authority=False,
        tool_lifecycle_entry_available=importlib.util.find_spec('continuity_engine.services.temporary_tool_service') is not None,
        connection_use_cleanup='NOT_IMPLEMENTED',subject_revision=f.state.revision)))
