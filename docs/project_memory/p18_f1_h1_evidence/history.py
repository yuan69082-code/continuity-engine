"""Read-only historical identity comparison; new output never replaces old evidence."""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2];DOC=OUT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))

before=read(OUT/'before.json')
index={}
for p in DOC.rglob('*.py'):
    index.setdefault(sha(p),[]).append(p.relative_to(ROOT).as_posix())
records={}
for issue,path in [('H1',DOC/'p18_evidence/p18-final-04.json'),('F1',DOC/'p18_repair_evidence/full-final-01.json')]:
    run=read(path);old=run['sourceBefore'];current=before['sourceTest']
    relevant={p:{'historical':h,'current':current.get(p),'archivedExactCopies':index.get(h,[])}
        for p,h in old.items() if any(x in p for x in ('runtime','thinking','json_repository','scheduler'))}
    records[issue]=dict(original=path.relative_to(ROOT).as_posix(),sha256=sha(path),
        run={k:run[k] for k in ('run','passed','exitCode','seconds','skips','failures')},
        sourceStable=old==run['sourceAfter'],changedSince=[p for p,h in old.items() if current.get(p)!=h],
        addedSince=[p for p in current if p not in old],relevantIdentities=relevant)
target=OUT/'historical-identities.json'
with target.open('x',encoding='utf8') as stream:json.dump(records,stream,ensure_ascii=False,indent=2)
print(json.dumps({k:{'changed':v['changedSince'],'exactArchives':{p:r['archivedExactCopies'] for p,r in v['relevantIdentities'].items() if r['archivedExactCopies']}} for k,v in records.items()},ensure_ascii=False))
