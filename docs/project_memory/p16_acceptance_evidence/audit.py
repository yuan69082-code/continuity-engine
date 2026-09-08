"""P16 acceptance precommit audit and explicit manifest; no Git mutations."""
import ast,hashlib,json,os,re,runpy,subprocess,sys,tomllib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;DOC=ROOT/'docs/project_memory'
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
helpers=runpy.run_path(str(DOC/'p14_evidence/audit.py'));sha,git,links=helpers['sha'],helpers['git'],helpers['links']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    b=read(OUT/'before.json');errors=[]
    target=OUT/'precommit.audit.json';manifest=OUT/'commit-manifest.json';listing=OUT/'commit-files.md'
    assert not any(p.exists() for p in (target,manifest,listing)), 'preserve prior audits'
    source={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    a={'at':datetime.now(timezone.utc).isoformat(),'errors':errors,'testsExecuted':False,'gitWrites':False,'stage':'P16','status':'ACCEPTED',
       'sourceTest':source,'sourceTestCount':len(source),'sourceMatchesIndependentAndFull':source==b['sourceTest'],
       'sourceTestInventoryHash':'sha256:'+hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    if source!=b['sourceTest']:errors.append('source drift')
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved','historicalEvidence'):
        changed=[p for p,h in b[k].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        a[k]={'count':len(b[k]),'changed':changed}
        if changed:errors.append(k)
    a['archiveChanged']=[name for name,v in b['reviewArchive'].items() if sha(ROOT/v['destination'])!=v['sha256'] or sha(Path(v['source']))!=v['sha256']]
    if a['archiveChanged']:errors.append('archive drift')
    a['matrixSnapshotByteExact']=sha(OUT/'matrix-before.md')==b['priorPendingHashes']['docs/project_memory/76_P16_规划施工测试验收矩阵.md']
    if not a['matrixSnapshotByteExact']:errors.append('matrix snapshot')
    a['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data');a['formalFileCount']=sum(p.is_file() for p in (ROOT/'.continuity-data').rglob('*'))
    if a['formalTreeHash']!=b['formalTreeHash'] or a['formalFileCount']!=7:errors.append('formal data')
    a['version']=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version'];a['pyprojectHash']=sha(ROOT/'pyproject.toml')
    if a['version']!='0.1.0':errors.append('version')
    a['verifiedCitedRuns']={}
    for label in ('independent-after-01','p16-final-01','compatibility-final-01','full-final-01'):
        r=read(DOC/'p16_repair_evidence'/(label+'.json'))
        a['verifiedCitedRuns'][label]={k:r[k] for k in ('command','run','passed','skips','seconds','exitCode')}
        if r['sourceBefore']!=source or r['sourceAfter']!=source or r['exitCode']:errors.append('cited '+label)
    for p in source:
        if p.endswith('.py'):ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p)
    a['sourceAstCount']=sum(p.endswith('.py') for p in source)
    for p in OUT.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    prospective={p.relative_to(ROOT).as_posix() for p in (target,manifest,listing)}
    paths=sorted((set(tracked+untracked)-set(b['excluded']))|prospective)
    a['pending']=paths;a['excluded']=b['excluded']
    a['priorPendingRetained']=set(b['approvedPriorPending'])<=set(paths)
    a['unexpectedScope']=[p for p in paths if p not in b['approvedPriorPending'] and not p.startswith('docs/project_memory/p16_acceptance_evidence/')
        and p!='docs/project_memory/P16_用户正式验收_20260909.md' and p not in {v['destination'] for v in b['reviewArchive'].values()}]
    a['changedDuringAcceptance']=[p for p,h in b['priorPendingHashes'].items() if sha(ROOT/p)!=h]
    a['unexpectedChanged']=[p for p in a['changedDuringAcceptance'] if p!='README.md' and not (Path(p).parent==Path('docs/project_memory') and p.endswith('.md'))]
    if not a['priorPendingRetained'] or a['unexpectedScope'] or a['unexpectedChanged']:errors.append('scope')
    if not set(b['excluded'])<=set(untracked):errors.append('excluded status')
    a['forbiddenArtifacts']=[p for p in paths if any(x in Path(p).parts for x in ('.git','.continuity-data','__pycache__','dist','build','node_modules')) or p.endswith(('.pyc','.whl','.zip'))]
    if a['forbiddenArtifacts']:errors.append('artifacts')
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    a['sensitiveMatches']=[];a['localLinkCount']=0;a['brokenLinks']=[];a['historicalWhitespace']=[];a['unexpectedWhitespace']=[]
    expected={p.resolve() for p in (target,manifest,listing)}
    for name in paths:
        p=ROOT/name
        if not p.is_file() or p.suffix not in ('.md','.py','.json','.log','.txt'):continue
        text=p.read_text(encoding='utf-8-sig')
        if secret.search(text):a['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            link_origin=DOC/'76_P16_规划施工测试验收矩阵.md' if p==OUT/'matrix-before.md' else p
            n,bad=links(link_origin,text,expected);a['localLinkCount']+=n;a['brokenLinks'].extend((name,v) for v in bad)
        findings=[{'line':i,'kind':'trailing whitespace'} for i,line in enumerate(text.splitlines(),1) if line.endswith((' ','\t'))]
        if text.endswith('\n\n') and text.strip():findings.append({'line':len(text.splitlines()),'kind':'new blank line at EOF'})
        if findings:
            unchanged=(b['priorPendingHashes'].get(name)==sha(p) or name in {v['destination'] for v in b['reviewArchive'].values()} or p==OUT/'matrix-before.md')
            if not unchanged and name in tracked:
                old=git('show','HEAD:'+name).splitlines()
                unchanged=all(f['kind']=='trailing whitespace' and text.splitlines()[f['line']-1] in old for f in findings)
            for finding in findings:(a['historicalWhitespace'] if unchanged else a['unexpectedWhitespace']).append({'path':name,**finding})
    if a['sensitiveMatches'] or a['brokenLinks'] or a['unexpectedWhitespace']:errors.append('documentation/material check')
    a['archiveRelativeLinkContext']={'docs/project_memory/p16_acceptance_evidence/matrix-before.md':'Raw byte-identical matrix snapshot; links retain original docs/project_memory context. Not rewritten as a new navigation document.'}
    a['historicalWarnings']=['p15_repair_evidence/formal-before.stderr.log:5 trailing whitespace; unchanged prior-stage evidence',
        'src/continuity_engine/services/subject_lifecycle_ports.py:18 EOF blank line; unchanged accepted source',
        'Git reports LF-to-CRLF checkout normalization notices; no implementation or raw worktree evidence rewritten',
        'Synthetic secret markers are intentional failure/test evidence, not real credentials; preserved and not removed to pass scanning']
    for name in ('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md','docs/project_memory/76_P16_规划施工测试验收矩阵.md'):
        block=(ROOT/name).read_text(encoding='utf-8-sig').split('<!-- P16_ACCEPTED_START -->')[1].split('<!-- P16_ACCEPTED_END -->')[0]
        if not all(v in block for v in ('P00—P16 ACCEPTED','P17—P23 NOT_STARTED','D-069','EVIDENCE_CONFLICT = NONE','PLANNING_CONFLICT = NONE','NOT_READY')):errors.append('state '+name)
    decisions=(DOC/'04_决策记录.md').read_text(encoding='utf-8-sig')
    if len(re.findall(r'^## D-069[：:]',decisions,re.M))!=1:errors.append('D-069')
    matrix=(DOC/'76_P16_规划施工测试验收矩阵.md').read_text(encoding='utf-8-sig')
    a['acceptedRows']=re.findall(r'^\| P16-(\d{2}) \|[^\n]*?\| ACCEPTED \|',matrix,re.M)
    if a['acceptedRows']!=[f'{i:02}' for i in range(1,13)]:errors.append('matrix')
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8');a['trackedDiffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:errors.append('tracked diff check')
    a['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
              'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),'staged':git('diff','--cached','--name-only'),'remote':git('remote','get-url','origin'),
              'pushRemote':git('remote','get-url','--push','origin'),'workflows':git('ls-files','.github/workflows')}
    if a['git']['branch']!='main' or a['git']['head']!=b['head'] or a['git']['originMain']!=b['head'] or a['git']['staged']:errors.append('git baseline')
    if a['git']['remote']!='https://github.com/yuan69082-code/continuity-engine.git' or a['git']['pushRemote']!=a['git']['remote']:errors.append('remote')
    manifest.write_text(json.dumps({'stage':'P16','decision':'D-069','parent':b['head'],'branch':'main','remote':a['git']['remote'],
        'message':'feat: implement and accept P16 external capability providers','files':paths,'excluded':b['excluded']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    listing.write_text('# P16 正式验收精确提交清单\n\n'+f'共 {len(paths)} 项，保留原192项并加入必要验收档案。仅这些路径获准暂存，另32项排除不动。D-069；普通提交推送Engine main。\n\n'
        +'\n'.join('- `'+p+'`' for p in paths)+'\n\n## 原样排除（32项）\n\n'+'\n'.join('- `'+p+'`' for p in b['excluded'])+'\n',encoding='utf-8')
    a['pendingHashes']={p:sha(ROOT/p) for p in paths if p!=target.relative_to(ROOT).as_posix()}
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a['git']['status']=git('status','--short','--untracked-files=all')
    a['git']['untrackedAfterAudit']=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    target.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'errors':errors,'files':len(paths),'sourceCount':len(source),'ast':a['sourceAstCount'],'links':a['localLinkCount'],
        'historicalWhitespace':len(a['historicalWhitespace']),'unexpectedWhitespace':a['unexpectedWhitespace'],'brokenLinks':a['brokenLinks']},ensure_ascii=False))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
