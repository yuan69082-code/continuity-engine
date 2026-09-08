"""Documentation-only final identity, state, links and exact pending-file audit."""
import ast,hashlib,json,os,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote

root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent;docs=root/'docs/project_memory'
sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'src'))
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=root,
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True,encoding='utf-8').strip()
before=read(out/'before.json');document_paths=read(out/'document-paths.json')
output=out/'final.audit.json';manifest=out/'final.pending-files.md'
assert not output.exists() and not manifest.exists(),'audit evidence must not be overwritten'
source={p.relative_to(root).as_posix():sha(p) for d in ('src','tests') for p in (root/d).rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
assert source==before['sourceTest'], 'source/test change during acceptance'
for key in ('protected','plans','formalFiles','independentOriginals'):
    assert all(sha(root/p)==h for p,h in before[key].items()),key+' changed'
for name in before['copiedOriginalNames']:
    original=next(p for p in before['independentOriginals'] if Path(p).name==name)
    assert sha(out/'independent'/name)==before['independentOriginals'][original]
assert tree_inventory_hash(root/'.continuity-data')==before['formalTreeHash']
assert git('branch','--show-current')=='main'
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==before['head']
assert not git('diff','--cached','--name-only')
assert not git('ls-files','.github/workflows')
tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
excluded=set(before['excludedP10']);assert excluded<=set(untracked)
pending=sorted((set(tracked)|set(untracked))-excluded)
changed=sorted(p for p,h in before['workspace'].items() if sha(root/p)!=h)
new=sorted(set(pending)-set(before['workspace']))
assert changed==sorted(document_paths),changed
assert set(before['pendingBeforeAcceptance'])<=set(pending),'preexisting result missing'
assert all(p=='docs/project_memory/P13_用户正式验收_20260908.md' or
           p.startswith('docs/project_memory/p13_acceptance_evidence/') for p in new),new
assert all(sha(root/p)==h for p,h in before['workspace'].items() if p not in document_paths),'history/unrelated drift'
workspace={p.relative_to(root).as_posix() for p in root.rglob('*')
    if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix!='.pyc'}
unexpected=sorted(workspace-set(before['workspace'])-set(pending));assert not unexpected,unexpected
decisions=(docs/'04_决策记录.md').read_text(encoding='utf-8')
assert all(decisions.count('## D-'+n+'：')==1 for n in ('061','062','063'))
assert '## D-064：' not in decisions
assert '## D-062 R1/R2 施工完成事实（不是新验收决定）' in decisions
assert 'P13 IMPLEMENTED_NOT_ACCEPTED；EVIDENCE_CONFLICT=PRESENT。' in decisions
for path in document_paths:
    text=(root/path).read_text(encoding='utf-8')
    assert text.startswith('<!-- P13_ACCEPTED_START -->')
    block=text.split('<!-- P13_ACCEPTED_END -->')[0]
    assert all(s in block for s in ('P00—P13 ACCEPTED','P13-01—P13-12 ACCEPTED',
        'P14—P23 NOT_STARTED','PLANNING_CONFLICT=NONE','EVIDENCE_CONFLICT=NONE'))
matrix=(docs/'64_P13_规划施工测试验收矩阵.md').read_text(encoding='utf-8').splitlines()
start=next(i for i,line in enumerate(matrix) if line.startswith('| P13-01 |'))
rows=matrix[start:start+12]
assert all(row.endswith('| ACCEPTED |') for row in rows)
assert {row.split('|')[1].strip() for row in rows}=={f'P13-{i:02d}' for i in range(1,13)}
broken=[];links=[];secrets=[];raw_whitespace=[];parsed=[]
patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
          r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bsk-[A-Za-z0-9]{30,}',r'\bAKIA[A-Z0-9]{16}\b']
for name in pending:
    p=root/name;assert p.suffix not in {'.pyc','.whl','.zip','.exe','.dll'} and '__pycache__' not in p.parts
    text=p.read_text(encoding='utf-8-sig')
    if any(re.search(pattern,text) for pattern in patterns):secrets.append(name)
    for number,line in enumerate(text.splitlines(),1):
        if line.rstrip(' \t')!=line:raw_whitespace.append({'file':name,'line':number,'rawLog':p.suffix=='.log'})
    if p.suffix=='.py':ast.parse(text,filename=name);parsed.append(name)
    if p.suffix!='.md':continue
    text=re.sub(r'```.*?```','',text,flags=re.S)
    for m in re.finditer(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
        target=unquote(m.group(1).strip().strip('<>')).split('#')[0]
        if not target or re.match(r'^(https?://|mailto:|codex:)',target):continue
        resolved=Path(target) if Path(target).is_absolute() else p.parent/target
        row={'file':name,'target':target};links.append(row)
        if not resolved.exists() and resolved.resolve() not in {output.resolve(),manifest.resolve()}:broken.append(row)
assert not broken,broken
assert not secrets,secrets
assert all(row['rawLog'] for row in raw_whitespace),'non-raw formatting issue'
check=subprocess.run(['git','diff','--check'],cwd=root,capture_output=True,text=True,
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
assert check.returncode==0,check.stdout+check.stderr
record={'at':datetime.now(timezone.utc).isoformat(),'head':before['head'],'branch':'main',
 'originMainLocal':git('rev-parse','origin/main'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
 'sourceTest':source,'protected':before['protected'],'plans':before['plans'],'formalFiles':before['formalFiles'],
 'formalTreeHash':before['formalTreeHash'],'excludedP10':before['excludedP10'],
 'sourceTestUnchanged':True,'unchangedReviewedWorkspaceExceptListedDocuments':True,
 'independentOriginalsAndCopiesUnchanged':True,'testsExecutedThisTurn':False,
 'independentRuns':before['independentRuns'],'citedFullOnly':before['citedFullOnly'],
 'decision':'D-063','P00-P13':'ACCEPTED','P13EngineSide':'ACCEPTED','P13MatrixAccepted':12,
 'P14-P23':'NOT_STARTED','PLANNING_CONFLICT':'NONE','EVIDENCE_CONFLICT':'NONE',
 'archiveChangedExisting':changed,'archiveNewBeforeAuditPair':new,'pendingBeforeAuditPair':pending,
 'tracked':tracked,'untracked':untracked,'staged':[],'networkChecks':False,'gitWrites':False,'actionsWorkflows':[],
 'localLinksChecked':len(links),'brokenLinks':broken,'secretMatches':secrets,'parsedPendingPython':parsed,
 'rawWhitespacePreserved':raw_whitespace,'unexpectedFiles':unexpected,'diffCheck':{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr},
 'contentHashes':{p:sha(root/p) for p in pending},'auditSelfNotHashed':True}
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
all_pending=sorted(set(pending)|{output.relative_to(root).as_posix(),manifest.relative_to(root).as_posix()})
accept_new=sorted(set(new)|{output.relative_to(root).as_posix(),manifest.relative_to(root).as_posix()})
text='# P13 验收归档与完整未提交清单\n\n此清单不构成 Git 授权。暂存区空，未提交/推送。\n\n'
text+=f'全部待提交 {len(all_pending)} 个文件（原172个成果保留），另排除31个P10本地脚本。本次验收修改 {len(changed)} 个既有档案，新增 {len(accept_new)} 个档案/证据/审计文件；源码与测试零修改。\n\n'
text+='## 本次修改的既有档案\n\n'+''.join('- `'+p+'`\n' for p in changed)
text+='\n## 本次新增档案、证据与审计\n\n'+''.join('- `'+p+'`\n' for p in accept_new)
text+='\n## 全部待提交成果\n\n'+''.join('- `'+p+'`\n' for p in all_pending)
text+='\n## 原样保留的31个排除脚本\n\n'+''.join('- `'+p+'`\n' for p in sorted(excluded))
manifest.write_text(text,encoding='utf-8')
print(json.dumps({'decision':'D-063','changedDocuments':len(changed),'newArchiveFiles':len(accept_new),
 'pending':len(all_pending),'excluded':len(excluded),'sourceUnchanged':len(source),'protectedUnchanged':len(before['protected']),
 'linksChecked':len(links),'diffCheck':check.returncode,'head':before['head']},ensure_ascii=False))
