"""Collect test identities without running tests; do not replace a frozen record."""
import json, pathlib, runpy, unittest, sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite): yield from flatten(item)
        else: yield item.id()
if __name__=='__main__':
    target=HERE/(sys.argv[1] if len(sys.argv)>1 else 'frozen-source-01.json')
    assert not target.exists()
    loader=unittest.TestLoader();ids=sorted(flatten(loader.discover(str(ROOT/'tests'))))
    old=json.loads((ROOT/'docs/project_memory/w04_2_completion_evidence/frozen-source-01.json').read_text(encoding='utf8'))
    snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
    source=snap['source']();missing=sorted(set(old['test_ids'])-set(ids))
    data=dict(source=source,fingerprint=snap['fingerprint'](source),test_ids=ids,test_count=len(ids),
              old_1863_missing=missing,new_ids=sorted(set(ids)-set(old['test_ids'])),discovery_errors=loader.errors)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(fingerprint=data['fingerprint'],test_count=len(ids),missing=len(missing),errors=len(loader.errors))))
    assert not missing and not loader.errors
