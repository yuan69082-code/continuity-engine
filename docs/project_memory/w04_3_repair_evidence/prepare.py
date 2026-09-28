"""Read-only baseline and immutable repair evidence setup; never Git mutation."""
import datetime, hashlib, json, pathlib, runpy, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).parent
OLD=ROOT/'docs/project_memory/w04_3_evidence'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git','-c','core.quotepath=false',*a],cwd=ROOT,encoding='utf8').strip()
snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
base=read(OLD/'baseline.json'); frozen=read(OLD/'frozen-source-03.json'); manifest=read(OLD/'final.files.json')
src=snap['source'](); assert src==frozen['source']
assert git('rev-parse','HEAD')=='f64fb797ae4defae2dfd16278f38e89c8b13cd66'
assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
for group,items in base['protected'].items():
    for p,h in items.items():assert sha(ROOT/p)==h,(group,p)
for p,h in base['retained'].items():assert sha(ROOT/p)==h,p
for r in base['planning']:assert sha(ROOT/r['archivePath'])==r['archiveSha256']
old_hashes={p:sha(ROOT/p) for p in manifest['paths']}
for p,h in manifest['hashes'].items():assert old_hashes[p]==h,p
changes=set(git('diff','--name-only').splitlines())|set(git('ls-files','--others','--exclude-standard').splitlines())
expected=set(manifest['paths'])|set(base['retained'])
new=set(p for p in changes if p.startswith(HERE.relative_to(ROOT).as_posix()+'/'))
assert changes-new==expected,dict(extra=sorted(changes-new-expected),missing=sorted(expected-changes))
out=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=git('rev-parse','HEAD'),branch='main',
         source=src,fingerprint=snap['fingerprint'](src),previous_paths=manifest['paths'],previous_hashes=old_hashes,
         protected=base['protected'],planning=base['planning'],retained=base['retained'],
         test_ids=frozen['test_ids'],status=git('status','--short','--untracked-files=all'),staged=[],
         index_hash=sha(ROOT/'.git/index'),auxiliary='First PowerShell read used unsupported brace syntax; parser error, no file or Engine mutation.')
with (HERE/'baseline.json').open('x',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
(HERE/'run.py').write_bytes((OLD/'run.py').read_bytes())
print(json.dumps(dict(source=len(src),fingerprint=out['fingerprint'],previous=len(old_hashes),retained=len(base['retained']),protected='UNCHANGED')))
