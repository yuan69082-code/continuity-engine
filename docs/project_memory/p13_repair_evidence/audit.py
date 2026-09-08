"""Read-only R1/R2 protection/identity audit and exact uncommitted manifest."""
import ast,hashlib,json,os,re,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote

root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'src'))
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=root,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True,encoding='utf-8').strip()
before=json.loads((out/'before.json').read_text(encoding='utf-8'))
previous=json.loads((root/'docs/project_memory/p13_evidence/full-final.tests.json').read_text(encoding='utf-8'))
full=json.loads((out/'full-final.tests.json').read_text(encoding='utf-8'))
targeted=json.loads((out/'p13-final.tests.json').read_text(encoding='utf-8'))
label=sys.argv[1];assert re.fullmatch('[a-z0-9-]+',label)
output=out/(label+'.audit.json');manifest=out/(label+'.pending-files.md')
assert not output.exists() and not manifest.exists(),'fresh audit label required'
source={p.relative_to(root).as_posix():sha(p) for d in ('src','tests') for p in (root/d).rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert full['status']=='FINISHED' and full['sourceTest']==source
assert not full['failures'] and not full['errors'] and full['skips']==previous['skips']
assert set(previous['testIdentities'])<=set(full['testIdentities'])
assert len(set(full['testIdentities']))==full['run']==len(full['testIdentities'])
assert set(full['testIdentities'])-set(previous['testIdentities'])=={
    x for x in targeted['testIdentities'] if x.startswith('test_p13_review_regressions.')}
assert all(source[p]==h for p,h in before['sourceTest'].items() if p.startswith('tests/'))
original_probe=ast.parse((out/'independent/review_probes.py').read_text(encoding='utf-8'))
formal_probe=ast.parse((root/'tests/test_p13_review_regressions.py').read_text(encoding='utf-8'))
extract=lambda tree:next(ast.dump(n) for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='P13ReviewProbes')
assert extract(original_probe)==extract(formal_probe),'original seven assertions changed'
for section in ('protected','plans','formalFiles','independentOriginals'):
    assert all(sha(root/p)==h for p,h in before[section].items()),section+' drift'
assert tree_inventory_hash(root/'.continuity-data')==before['formalTreeHash']
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==before['head']
assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
assert not git('ls-files','.github/workflows')
tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
excluded=set(before['excludedP10']);assert excluded<=set(untracked)
pending=sorted((set(tracked)|set(untracked))-excluded)
workspace_current={p.relative_to(root).as_posix() for p in root.rglob('*')
    if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc'}
unexpected_files=sorted(workspace_current-set(before['workspace'])-set(pending))
assert not unexpected_files,unexpected_files
old_audit=json.loads((root/'docs/project_memory/p13_evidence/final-audit.audit.json').read_text(encoding='utf-8'))
observed_bytecode=sorted(p.relative_to(root).as_posix() for p in root.rglob('*.pyc') if '.git' not in p.parts)
new_bytecode=sorted(set(observed_bytecode)-set(old_audit['observedBytecodePreserved']))
assert not new_bytecode,new_bytecode
changed=sorted(p for p,h in before['workspace'].items() if sha(root/p)!=h)
new=sorted(set(pending)-set(before['workspace']))
allowed_source={'src/continuity_engine/domain/expression.py',
 'src/continuity_engine/services/expression_policy_service.py',
 'src/continuity_engine/services/continuity_interaction_service.py',
 'src/continuity_engine/testing/p13_expression_fixture.py','tests/test_p13_review_regressions.py'}
repair_source={p for p in changed+new if p.startswith(('src/','tests/'))}
assert repair_source==allowed_source,repair_source
assert all(not p.startswith('docs/project_memory/p13_evidence/') for p in changed),'old evidence altered'
assert all(p in allowed_source or p=='README.md' or
           (p.startswith('docs/project_memory/') and p.endswith('.md') and '/' not in p[len('docs/project_memory/'):]) for p in changed)
assert all(p in allowed_source or p=='docs/project_memory/P13_独立复核返修_R1-R2.md' or
           p.startswith('docs/project_memory/p13_repair_evidence/') for p in new),new
for name,h in before['independentOriginals'].items():assert sha(out/'independent'/Path(name).name)==h
parsed=[]
for p in sorted(set(source)|{p for p in pending if p.endswith('.py')}):
    if p.endswith('.py'):ast.parse((root/p).read_text(encoding='utf-8-sig'),filename=p);parsed.append(p)
broken=[];links=[];secrets=[];whitespace=[]
patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
          r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bsk-[A-Za-z0-9]{30,}',r'\bAKIA[A-Z0-9]{16}\b']
for name in pending:
    p=root/name
    assert p.suffix not in {'.pyc','.whl','.zip','.exe','.dll'} and '__pycache__' not in p.parts
    content=p.read_text(encoding='utf-8-sig')
    if any(re.search(pattern,content) for pattern in patterns):secrets.append(name)
    for n,line in enumerate(content.splitlines(),1):
        if line.rstrip(' \t')!=line:whitespace.append({'file':name,'line':n,'raw':p.suffix=='.log'})
    if p.suffix!='.md':continue
    content=re.sub(r'```.*?```','',content,flags=re.S)
    for m in re.finditer(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',content):
        target=unquote(m.group(1).strip().strip('<>')).split('#')[0]
        if not target or re.match(r'^(https?://|mailto:|codex:)',target):continue
        resolved=Path(target) if Path(target).is_absolute() else p.parent/target
        row={'file':name,'target':target};links.append(row)
        if not resolved.exists() and resolved.resolve() not in {output.resolve(),manifest.resolve()}:broken.append(row)
assert not broken,broken
assert not secrets,secrets
assert all(x['raw'] for x in whitespace),'non-raw whitespace issue'
assert not git('diff','--check')
decisions=(root/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8')
assert decisions.count('## D-061：')==decisions.count('## D-062：')==1
assert '## D-063：' not in decisions
for filename,prefix,status in [('60_P12_规划施工测试验收矩阵.md','P12','ACCEPTED'),
                               ('64_P13_规划施工测试验收矩阵.md','P13','IMPLEMENTED_NOT_ACCEPTED')]:
    content=(root/'docs/project_memory'/filename).read_text(encoding='utf-8')
    lines=content.splitlines()
    start=next(i for i,line in enumerate(lines) if re.match(r'\| '+prefix+r'-\d\d \|',line))
    rows=[]
    for line in lines[start:]:
        if not re.match(r'\| '+prefix+r'-\d\d \|',line):break
        rows.append(line)
    assert len(rows)==12 and all(row.endswith('| '+status+' |') for row in rows)
    assert {row.split('|')[1].strip() for row in rows}=={f'{prefix}-{i:02d}' for i in range(1,13)}
current=[]
for name in pending:
    if not name.endswith('.md'):continue
    content=(root/name).read_text(encoding='utf-8')
    if '<!-- P13_REPAIR_CURRENT_START -->' in content:
        block=content.split('<!-- P13_REPAIR_CURRENT_START -->')[1].split('<!-- P13_REPAIR_CURRENT_END -->')[0]
        assert 'EVIDENCE_CONFLICT=PRESENT' in block and 'IMPLEMENTED_NOT_ACCEPTED' in block
        current.append(name)
record={'at':datetime.now(timezone.utc).isoformat(),'head':before['head'],'branch':'main',
 'originMainLocal':git('rev-parse','origin/main'),'aheadBehindLocal':git('rev-list','--left-right','--count','HEAD...origin/main'),
 'networkChecks':False,'gitWrites':False,'actionsWorkflows':[],
 'sourceTest':source,'protected':before['protected'],'plans':before['plans'],
 'formalFiles':before['formalFiles'],'formalTreeHash':before['formalTreeHash'],'excludedP10':before['excludedP10'],
 'originalTestIdentitiesPreserved':len(previous['testIdentities']),
 'newTestIdentities':sorted(set(full['testIdentities'])-set(previous['testIdentities'])),
 'full':{k:full[k] for k in ('run','passed','skips','failures','errors','seconds')},
 'AST':len(parsed),'localLinks':len(links),'brokenLinks':broken,'secretMatches':secrets,
 'rawWhitespacePreserved':whitespace,'diffCheck':'PASS','currentBlocks':current,
 'unexpectedIgnoredOrRuntimeFiles':unexpected_files,'newBytecode':new_bytecode,
 'observedBytecodePreserved':observed_bytecode,
 'repairChanged':changed,'repairNew':new,'repairSourceTests':sorted(repair_source),
 'pendingBeforeAuditPair':pending,'tracked':tracked,'untracked':untracked,'staged':[],
 'contentHashes':{p:sha(root/p) for p in pending},'auditSelfNotHashed':True}
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
all_pending=sorted(set(pending)|{output.relative_to(root).as_posix(),manifest.relative_to(root).as_posix()})
text='# P12 验收 / P13 初版与 R1/R2 返修精确未提交清单\n\n本清单不授权 Git 操作。所有文件均未暂存；31 个 P10 本地脚本单独排除。\n\n'
text+=f'HEAD `{before["head"]}`；待提交合计 {len(all_pending)}；其中本次运行/测试增量 5 个。\n\n## 本次 R1/R2 修改与新增\n\n'
text+=''.join('- `'+p+'`\n' for p in sorted(set(changed+new)|{output.relative_to(root).as_posix(),manifest.relative_to(root).as_posix()}))
text+='\n## 全部待提交文件（含原 P12/P13 成果）\n\n'+''.join('- `'+p+'`\n' for p in all_pending)
text+='\n## 原样保留的 31 个 P10 排除脚本\n\n'+''.join('- `'+p+'`\n' for p in sorted(excluded))
manifest.write_text(text,encoding='utf-8')
print(json.dumps({'head':before['head'],'repairSourceTests':len(repair_source),'pending':len(all_pending),
 'excluded':len(excluded),'AST':len(parsed),'localLinks':len(links),'full':record['full'],
 'protected':'UNCHANGED','formalTree':record['formalTreeHash'],'diffCheck':'PASS'},ensure_ascii=False))
