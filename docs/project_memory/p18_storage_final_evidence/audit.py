"""Final read-only verification plus exact P18 manifests. No Git writes."""
import ast,datetime,hashlib,json,os,re,runpy,subprocess,tomllib,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
suffix='-'+sys.argv[1] if len(sys.argv)>1 else ''
audit_name='final.audit'+suffix+'.json'
pending_name='final.pending-files'+suffix+'.md'
changes_name='turn-changes'+suffix+'.json'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf8',env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
def paths(*args):return git(*args).stdout.splitlines()
def create(name,value):
    with (OUT/name).open('x',encoding='utf8') as f:f.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n')
b=read(OUT/'before.json');frozen=read(OUT/'frozen-source-02.json')
source=runpy.run_path(str(OUT/'run.py'))['source_hashes']()
from continuity_engine.testing.persistence import tree_inventory_hash
assert source==frozen['source']
docs=read(OUT/'documentation-files.json');allowed=set(docs+b['allowedRuntimeFiles'])
preserved_changes={p for p,h in b['existingPending'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h}
assert preserved_changes<=allowed
assert all(sha(ROOT/p)==h for group in b['protected'].values() for p,h in group.items())
assert sha(ROOT/'pyproject.toml')==b['pyproject']
formal={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'.continuity-data').rglob('*') if p.is_file()}
assert formal==b['protected']['formalFiles']
formal_tree_hash=tree_inventory_hash(ROOT/'.continuity-data')
assert formal_tree_hash==b['formalTreeHash']
version=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf8'))['project']['version']
assert version=='0.1.0'
archives={}
for original,row in b['archives'].items():
    # Runtime originals were intentionally changed; their archived preimages
    # retain the frozen hash. Planning-side originals must still be identical.
    assert sha(ROOT/row['copy'])==row['sha256']
    if original not in b['allowedRuntimeFiles']:assert sha(ROOT/original)==row['sha256']
    archives[original]=row
staged=paths('diff','--cached','--name-only');assert not staged
head=git('rev-parse','HEAD').stdout.strip();origin=git('rev-parse','origin/main').stdout.strip()
assert head==origin==b['head'] and git('branch','--show-current').stdout.strip()=='main'
selected=read(OUT/'selected-runs.json')['runs'];results={};processes=[]
for label in selected:
    r=read(OUT/(label+'.json'));assert r['sourceBefore']==source==r['sourceAfter'] and r['exitCode']==0
    results[label]={k:r[k] for k in ('run','passed','seconds','exitCode','status','skips')}
    results[label].update(failures=len(r['failures']),errors=len(r['errors']))
    for line in (OUT/(label+'.stdout.log')).read_text(encoding='utf8').splitlines():
        if not line.startswith('{'):continue
        try:row=json.loads(line)
        except ValueError:continue
        if 'childrenReaped' in row:assert row['childrenReaped'] is True
        if 'readerReaped' in row:assert row['readerReaped'] is True
        for item in row.get('processEvidence',[]):
            if item.get('stage')=='continuous-child':
                assert item['exitCode'] is not None and not item['forcedCleanup']
                processes.append({'label':label,**item})
observation=read(OUT/'process-observation-final.json')
assert not observation['matchingProcesses']
manifest_names=[changes_name,pending_name,audit_name]
pending=sorted(set(paths('diff','--name-only')+paths('ls-files','--others','--exclude-standard')+
    [(OUT/n).relative_to(ROOT).as_posix() for n in manifest_names])-set(b['excluded']))
new=[p for p in pending if p not in b['existingPending']]
assert all(p.startswith('docs/project_memory/p18_storage_final_evidence/') or p in docs or
           p in {'tests/test_p18_storage_retry.py','tests/test_p18_storage_runtime.py'} for p in new)
changes={p:{'before':b['existingPending'].get(p),'after':sha(ROOT/p)} for p in pending
    if (ROOT/p).exists() and (p not in b['existingPending'] or p in preserved_changes)}
create(changes_name,{'existingChanged':sorted(preserved_changes),'new':new,'hashes':changes,
    'generatedManifestSelfHashes':'Latest audit excludes its own hash; all paths still listed.'})
excluded={**b['protected']['excludedP10'],**b['protected']['otherPreserved']}
text='# P18 最终精确未提交清单\n\n'
text+=f'全部P18成果 {len(pending)} 项；本轮前已有 {len(b["existingPending"])} 项完整保留，仅明确许可文件追加/补修。本轮新增 {len(new)} 项；另有32项排除材料未变。清单不构成暂存或提交授权。\n\n'
text+='## 本轮修改既有文件\n\n'+'\n'.join('- '+p for p in sorted(preserved_changes))+'\n\n'
text+='## 本轮新增文件\n\n'+'\n'.join('- '+p for p in new)+'\n\n'
text+='## 完整P18成果\n\n'+'\n'.join('- '+p for p in pending)+'\n\n'
text+='## 原32项排除材料与SHA256\n\n'+'\n'.join('- '+p+' — '+h for p,h in excluded.items())+'\n'
create(pending_name,text)

asts=[]
for folder in (ROOT/'src',ROOT/'tests',OUT):
    for p in folder.rglob('*.py'):
        ast.parse(p.read_text(encoding='utf-8-sig'));asts.append(p.relative_to(ROOT).as_posix())
links=[];bad=[]
for p in [ROOT/n for n in docs]+list(OUT.rglob('*.md')):
    for dest in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        if dest.startswith(('https:','http:','#','app:')):continue
        target=dest.split('#')[0].strip('<>')
        if not target:continue
        q=(p.parent/target).resolve()
        if not q.exists() and q!=(OUT/audit_name).resolve():bad.append({'file':p.relative_to(ROOT).as_posix(),'target':target})
        links.append(dest)
secrets=[];format_findings=[]
for rel in pending:
    p=ROOT/rel
    if p.is_file() and p.suffix in {'.md','.json','.log','.py'}:
        body=p.read_text(encoding='utf-8-sig')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}',body):secrets.append(rel)
        warning_lines=[i for i,line in enumerate(body.splitlines(),1) if line.endswith((' ','\t'))]
        if warning_lines:format_findings.append({'file':rel,'trailingWhitespaceLines':warning_lines,'newThisTurn':rel in new,
            'rawEvidencePreserved':p.suffix=='.log'})
diff=git('diff','--check')
gitstatus={'branch':'main','head':head,'localOrigin':origin,'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main').stdout.strip(),
 'staged':staged,'trackedChanges':paths('diff','--name-only'),
 'untracked':sorted(set(paths('ls-files','--others','--exclude-standard')+[(OUT/audit_name).relative_to(ROOT).as_posix()])),
 'statusPorcelain':git('status','--porcelain=v1','--untracked-files=all').stdout,'remoteQueried':False}
create(audit_name,{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'stage':'P18','status':'IMPLEMENTED_NOT_ACCEPTED','planningConflict':'NONE','evidenceConflict':'PRESENT',
 'source':source,'sourceHash':frozen['sourceHash'],'tests':len(frozen['identities']),'originalTestsRetained':len(b['testIdentities']),
 'originalAssertionsUnchanged':True,'newFormalTests':len(frozen['addedIdentities']),'results':results,
 'protectedUnchanged':True,'protectedCounts':{k:len(v) for k,v in b['protected'].items()},'formalFiles':formal,
 'formalTreeHash':formal_tree_hash,'pyprojectHash':b['pyproject'],'version':version,
 'archives':archives,'excluded':excluded,'existingPending':len(b['existingPending']),'existingChanged':sorted(preserved_changes),
 'pendingCount':len(pending),'newCount':len(new),'pendingHashes':{p:sha(ROOT/p) for p in pending if p!=(OUT/audit_name).relative_to(ROOT).as_posix()},
 'pythonASTFiles':len(asts),'pythonAST':'PASS','linkCount':len(links),'linkWarnings':bad,
 'secretSignatureFindings':secrets,'secretScanLimit':'Specific key signatures; explicit synthetic TEST failure evidence retained; not an exhaustive secret classifier.',
 'formatFindings':format_findings,'diffCheck':{'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr},
 'processes':processes,'processObservation':observation,'git':gitstatus,'gitWrites':False,'CI':'NOT_RUN_NO_CLAIM'})
print(json.dumps({'pending':len(pending),'new':len(new),'excluded':len(excluded),'sourceHash':frozen['sourceHash'],
    'AST':len(asts),'links':len(links),'linkWarnings':bad,'secretFindings':secrets,'diffCheck':diff.returncode,
    'formatFiles':len(format_findings),'tracked':len(gitstatus['trackedChanges']),'untracked':len(gitstatus['untracked'])},ensure_ascii=False))
