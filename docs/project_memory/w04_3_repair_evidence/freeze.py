"""Collect identities only; immutable final source binding, no test execution."""
import json,pathlib,runpy,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item.id()
if __name__=='__main__':
    path=HERE/'frozen-source-01.json';assert not path.exists()
    loader=unittest.TestLoader();ids=sorted(flatten(loader.discover(str(ROOT/'tests'))))
    base=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
    snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'));src=snap['source']()
    missing=sorted(set(base['test_ids'])-set(ids))
    old_changes=[p for p,h in base['source'].items() if p.startswith('tests/') and src.get(p)!=h]
    data=dict(source=src,fingerprint=snap['fingerprint'](src),test_ids=ids,test_count=len(ids),
        original_1909_missing=missing,old_test_changes=old_changes,new_ids=sorted(set(ids)-set(base['test_ids'])),errors=loader.errors)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in data.items() if k not in ('source','test_ids','new_ids')}))
    assert not missing and not old_changes and not loader.errors
