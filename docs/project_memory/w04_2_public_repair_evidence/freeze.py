"""Inventory only; discover test identities without executing tests."""
import json,pathlib,runpy,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
S=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
loader=unittest.TestLoader();suite=loader.discover(str(ROOT/'tests'))
def ids(s):
    for x in s:
        if isinstance(x,unittest.TestSuite):yield from ids(x)
        else:yield x.id()
current=list(ids(suite));old=json.loads((ROOT/'docs/project_memory/w04_2_evidence/baseline-test-identities.json').read_text())['ids']
source=S['source']()
data=dict(source=source,fingerprint=S['fingerprint'](source),test_ids=current,test_count=len(current),
          old_1802_missing=sorted(set(old)-set(current)),discovery_errors=loader.errors)
with (HERE/'frozen-source-01.json').open('x',encoding='utf8') as f:json.dump(data,f,indent=2)
print(json.dumps({k:v for k,v in data.items() if k not in ('source','test_ids')}))
