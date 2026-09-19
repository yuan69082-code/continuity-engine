"""Pin final source and original formal identities before sequential validation."""
import hashlib,json,runpy,unittest,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
util=runpy.run_path(str(OUT/'run.py'));before=json.loads((OUT/'before.json').read_text(encoding='utf8'))
source=util['source_hashes']()
allowed=['src/continuity_engine/storage/json_repository.py','src/continuity_engine/storage/json_runtime_repository.py']
changed=[p for p,h in before['sourceTest'].items() if source.get(p)!=h]
assert sorted(changed)==sorted(allowed)
loader=unittest.TestLoader();identities=[t.id() for t in util['flatten'](loader.discover(str(ROOT/'tests')))]
assert not loader.errors and len(identities)==len(set(identities))
assert set(before['testIdentities'])<=set(identities)
record={'source':source,'sourceHash':'sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
 'originalIdentities':before['testIdentities'],'addedIdentities':sorted(set(identities)-set(before['testIdentities'])),
 'identities':identities,'changedRuntimeFiles':changed,'originalAssertionsFilesUnchanged':True}
name='frozen-source'+('-'+sys.argv[1] if len(sys.argv)>1 else '')+'.json'
with (OUT/name).open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps({'files':len(source),'tests':len(identities),'added':len(record['addedIdentities']),'sourceHash':record['sourceHash']}))
