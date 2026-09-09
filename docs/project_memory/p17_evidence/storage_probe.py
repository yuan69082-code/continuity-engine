"""Isolated P17 storage-boundary measurement; never uses another running Fixture."""
from pathlib import Path
import json
import sys
import tempfile
sys.path[:0]=[str(Path(__file__).resolve().parents[3]),str(Path(__file__).resolve().parents[3]/'src')]
from continuity_engine.testing.p17_execution_fixture import P17Fixture
from continuity_engine.domain.execution import BlastRadius

with tempfile.TemporaryDirectory(prefix='p17-storage-boundary-') as directory:
    f=P17Fixture(Path(directory));f.submit()
    previous=len(json.dumps(f.fake.store.load()).encode())
    limit=previous+1024
    f.execution.limits=BlastRadius(storage_bytes=limit)
    request,run=f.manual(decision='storage-boundary')
    result=run()
    actual=len(json.dumps(f.fake.store.load()).encode())
    print(json.dumps(dict(status=result.status,before_bytes=previous,limit=limit,after_bytes=actual,effects=f.fake.effect_count)))
    assert actual<=limit,'P17 Fake storage bound exceeded'
