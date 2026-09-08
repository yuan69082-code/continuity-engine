"""P15 acceptance precommit audit and exact manifest; read-only Git operations."""
import ast,hashlib,json,os,re,runpy,subprocess,sys,tomllib
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
H=runpy.run_path(str(ROOT/'docs/project_memory/p14_evidence/audit.py'))
sha,links=H['sha'],H['links']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8',stderr=subprocess.PIPE).strip()
def save(p,o):
    with p.open('x',encoding='utf-8') as f:json.dump(o,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    b=read(OUT/'before.json');old=read(ROOT/'docs/project_memory/p15_repair_evidence/final.audit.json')
    a={'at':datetime.now(timezone.utc).isoformat(),'errors':[],'testsExecuted':False,'gitWrites':False}
    a['sourceTest']={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests')
        for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    if a['sourceTest']!=b['sourceTest']:a['errors'].append('source identity')
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        a[k]={'count':len(b[k]),'changed':[p for p,h in b[k].items() if sha(ROOT/p)!=h]}
        if a[k]['changed']:a['errors'].append(k)
    a['historyChanged']=[p for p,h in b['originalPending'].items() if p.startswith((
        'docs/project_memory/p15_evidence/','docs/project_memory/p15_repair_evidence/')) and sha(ROOT/p)!=h]
    if a['historyChanged']:a['errors'].append('historical evidence')
    archive=read(OUT/'archive-index.json');a['archiveCount']=len(archive)
    a['archiveChanged']=[e['path'] for e in archive if sha(Path(e['source']))!=e['sha256'] or sha(ROOT/e['path'])!=e['sha256']]
    if a['archiveChanged']:a['errors'].append('archive')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if a['formalTreeHash']!=b['formalTreeHash']:a['errors'].append('formal tree')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8-sig'))['project']['version']
    if a['version']!='0.1.0':a['errors'].append('version')
    a['citedFull']=read(ROOT/'docs/project_memory/p15_repair_evidence/full-final.json')
    r=a['citedFull'];a['citedFull']={k:r[k] for k in ('command','run','passed','skips','seconds','exitCode')}
    if r['sourceBefore']!=a['sourceTest'] or r['sourceAfter']!=a['sourceTest'] or r['exitCode']:a['errors'].append('full citation')
    tracked=set(filter(None,git('diff','--name-only','-z').split('\0')))
    untracked=set(filter(None,git('ls-files','--others','--exclude-standard','-z').split('\0')))
    excludes=set(b['excludedP10'])|set(b['otherPreserved'])
    target=OUT/'precommit.audit.json';manifest=OUT/'commit-manifest.json';listing=OUT/'commit-files.md'
    prospective={p.relative_to(ROOT).as_posix() for p in (target,manifest,listing)}
    paths=sorted((tracked|untracked)-excludes|prospective)
    additions=set(paths)-set(b['originalPending'])
    if any(not(p.startswith('docs/project_memory/p15_acceptance_evidence/') or p=='docs/project_memory/P15_用户正式验收_20260909.md') for p in additions):a['errors'].append('unexpected added path')
    if not set(b['originalPending'])<=set(paths):a['errors'].append('missing original P15 file')
    if not excludes<=untracked:a['errors'].append('excluded status')
    a['originalPendingCount']=len(b['originalPending']);a['pendingCount']=len(paths);a['newFiles']=sorted(additions)
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build')) or p.endswith(('.pyc','.whl','.zip'))]
    if a['forbiddenArtifacts']:a['errors'].append('artifact')
    a['stateDocuments']=[];a['stateErrors']=[]
    for name in paths:
        p=ROOT/name
        if p.suffix!='.md' or not p.is_file():continue
        text=p.read_text(encoding='utf-8-sig')
        if '<!-- P15_ACCEPTED_START -->' in text:
            block=text.split('<!-- P15_ACCEPTED_START -->')[1].split('<!-- P15_ACCEPTED_END -->')[0]
            a['stateDocuments'].append(name)
            if not all(s in block for s in ('P00—P15 ACCEPTED','P16—P23 NOT_STARTED','PLANNING_CONFLICT=NONE','EVIDENCE_CONFLICT=NONE','D-067')):a['stateErrors'].append(name)
    dt=(ROOT/'docs/project_memory/04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-067[：:]',dt,re.M))!=1 or re.search(r'^## D-068[：:]',dt,re.M):a['stateErrors'].append('decision')
    matrix=(ROOT/'docs/project_memory/72_P15_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['acceptedRows']=re.findall(r'^\| P15-(\d{2}) \|[^\n]*?\| ACCEPTED \|',matrix,re.M)
    if a['acceptedRows']!=[f'{i:02}' for i in range(1,13)]:a['stateErrors'].append('matrix')
    if a['stateErrors']:a['errors'].append('current state')
    save(manifest,{'parent':b['head'],'branch':'main','remote':'https://github.com/yuan69082-code/continuity-engine.git',
        'message':'feat: implement and accept P15 subject growth and lifecycle','paths':paths,'excludedP10':sorted(b['excludedP10']),
        'otherExcluded':sorted(b['otherPreserved']),'count':len(paths)})
    listing.write_text('# P15正式验收完整提交清单\n\n共'+str(len(paths))+'项：原218项加本次'+str(len(additions))+'项必要归档。只按明确路径暂存，不使用git add .或git add -A。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 排除并原样保留的31个P10脚本\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(b['excludedP10']))+'\n\n## 排除并原样保留的旧P14接续报告\n\n'
        +'\n'.join('- `'+p+'`' for p in sorted(b['otherPreserved']))+'\n',encoding='utf-8')
    a['astCount']=0;a['localLinks']=0;a['newBrokenLinks']=[];a['historicalBrokenLinks']=[];a['sensitiveMatches']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.py','.json','.log'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.py':ast.parse(text,filename=name);a['astCount']+=1
        if p.suffix=='.md':
            n,bad=links(p,text,{target.resolve()});a['localLinks']+=n
            oldbad=links(p,git('show','HEAD:'+name))[1] if name in tracked else []
            a['newBrokenLinks'].extend((name,x) for x in bad if x not in oldbad)
            a['historicalBrokenLinks'].extend((name,x) for x in bad if x in oldbad)
    if a['newBrokenLinks'] or a['sensitiveMatches']:a['errors'].append('links or sensitive content')
    for name in a['sourceTest']:
        if name.endswith('.py'):ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)
    a['sourceAstCount']=sum(p.endswith('.py') for p in a['sourceTest'])
    result=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    a['diffCheck']={'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    if result.returncode:a['errors'].append('diff check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'staged':git('diff','--cached','--name-only'),'origin':git('remote','get-url','origin'),'pushOrigin':git('remote','get-url','--push','origin'),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'workflows':git('ls-files','.github/workflows')}
    if a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['branch']!='main' or a['git']['staged']:a['errors'].append('Git')
    if a['git']['origin']!=read(manifest)['remote'] or a['git']['pushOrigin']!=read(manifest)['remote']:a['errors'].append('remote')
    a['workingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix()}
    save(target,a)
    print(json.dumps({k:a[k] for k in ('errors','pendingCount','archiveCount','sourceAstCount','astCount','localLinks','formalTreeHash')},ensure_ascii=False))
    return bool(a['errors'])

if __name__=='__main__':raise SystemExit(main())
