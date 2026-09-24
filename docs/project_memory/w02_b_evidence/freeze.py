"""Freeze a validation candidate, preserving original test identities/bytes."""
import json,sys,unittest
from pathlib import Path
from snapshot import ROOT,HERE,collect,fingerprint,read

sys.path[:0]=[str(ROOT),str(ROOT/'src')]
def identities(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from identities(item)
        else:yield item.id().removeprefix('tests.')

loader=unittest.TestLoader();suite=loader.discover(str(ROOT/'tests'))
ids=list(identities(suite));assert not loader.errors,loader.errors
old=read(ROOT/'docs/project_memory/w02_a_evidence/repair_r1_r2/full-final-02.json')
old_ids={s.removeprefix('tests.') for s in old['testIdentities']}
data=collect();base=read(HERE/'baseline.json')
assert old_ids<=set(ids)
assert len(ids)==len(set(ids))
assert all(data['source'][p]==h for p,h in base['source'].items() if p.startswith('tests/'))
assert data['protectedUnchanged'] and data['excludedUnchanged'] and not data['staged']
assert data['head']==base['head'] and data['indexHash']==base['indexHash']
data.update(testIdentities=ids,originalTests=len(old_ids),newTestIdentities=sorted(set(ids)-old_ids),
            originalTestFilesUnchanged=True)
destination=HERE/(sys.argv[1]+'.json')
with destination.open('x',encoding='utf-8') as out:json.dump(data,out,ensure_ascii=False,indent=2)
print(json.dumps({'sourceFiles':len(data['source']),'sourceHash':data['sourceHash'],
                  'tests':len(ids),'original':len(old_ids),'new':len(data['newTestIdentities'])}))
