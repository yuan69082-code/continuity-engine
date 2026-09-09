"""Check a swapped TEST World port cannot write another subject's world."""
import json
import sys
import tempfile
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[3]),str(Path(__file__).resolve().parents[3]/'src')]
from continuity_engine.testing.p17_execution_fixture import P17Fixture
from continuity_engine.testing.persistence import tree_inventory_hash

with tempfile.TemporaryDirectory(prefix='p17a-') as a, tempfile.TemporaryDirectory(prefix='p17b-') as b:
    f=P17Fixture(Path(a));f.submit();other=P17Fixture(Path(b))
    request,run=f.manual(decision='wrong-world-port')
    f.execution.adapters[f.fake.adapter_id]=other.fake
    before=tree_inventory_hash(other.runtime.data_root)
    try:result=f.execution.execute(request);outcome='ACCEPTED'
    except Exception:outcome='REJECTED'
    after=tree_inventory_hash(other.runtime.data_root)
    print(json.dumps(dict(outcome=outcome,other_subject_effects=other.fake.effect_count,other_world_unchanged=before==after)))
    assert outcome=='REJECTED' and before==after,'P17 swapped World Adapter crossed subject boundary'
