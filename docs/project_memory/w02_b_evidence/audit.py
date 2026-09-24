"""Read-only closing checks; writes only the explicitly named W02-B audit files."""
import ast
import datetime
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote
from snapshot import HERE,ROOT,collect,read,sha,fingerprint

SELF_NAMES=('final.audit.json','final.files.json','final.pending-files.md')
DOCS=('README.md','docs/project_memory/01_当前状态.md','docs/project_memory/03_施工日志.md',
      'docs/project_memory/04_决策记录.md','docs/project_memory/06_未完成事项.md',
      'docs/project_memory/CHANGELOG.md','docs/project_memory/工程总档案.md')

def git(*args):
    return subprocess.run(['git','-c','core.quotepath=false',*args],cwd=ROOT,capture_output=True,encoding='utf-8')

def dump(path,data):
    with path.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(data,out,ensure_ascii=False,indent=2);out.write('\n')

def links(path,text):
    found=[]
    for match in re.finditer(r'(?<!!)\[[^\]\n]*\]\(([^\n]+?)\)',text):
        target=match[1].strip().strip('<>')
        if re.match(r'^(https?://|mailto:|#)',target):continue
        target=unquote(target.split('#')[0])
        if not target:continue
        if re.match(r'^[A-Za-z]:[/\\]',target):dest=Path(target)
        elif target.startswith('/'):dest=Path(target)
        else:dest=path.parent/target
        generated=dest.resolve() in {(HERE/n).resolve() for n in SELF_NAMES}
        found.append(dict(line=text[:match.start()].count('\n')+1,target=target,exists=dest.exists() or generated,
                          generatedByThisAudit=generated))
    return found

def main():
    for name in SELF_NAMES:assert not (HERE/name).exists(), 'audit output already exists'
    attempt=1
    while (HERE/f'diff-check-{attempt:02}.json').exists() or (HERE/f'audit-attempt-{attempt:02}.json').exists():
        attempt+=1
    diff_name=f'diff-check-{attempt:02}.json'
    frozen=read(HERE/'frozen-source-04.json'); base=read(HERE/'baseline.json');now=collect()
    errors=[]
    def check(ok,name):
        if not ok:errors.append(name)
        return bool(ok)
    identity=check(now['source']==frozen['source'],'source differs from frozen')
    check(now['head']==base['head'] and now['branch']=='main','git baseline changed')
    check(now['localOrigin']==base['localOrigin'] and now['origin']==base['origin'],'remote configuration/cache changed')
    remote=read(HERE/'remote-check.json')
    check(remote['actualRemoteMain']==now['head'],'actual remote main differs')
    check(now['indexHash']==base['indexHash'] and not now['staged'],'index changed')
    check(now['protected']==base['protected'],'protected group changed')
    check(now['excluded']==base['excluded'],'excluded group changed')
    check(all(now['source'][p]==h for p,h in base['source'].items() if p.startswith('tests/')),'original test changed')
    plans=[]
    for p in base['plans']:
        actual=sha(ROOT/p['copy']);check(actual==p['sha256'],'current archived planning changed')
        original=Path(p['original']);original_hash=sha(original) if original.is_file() else None
        if original_hash is not None:check(original_hash==p['sha256'],'current original planning differs')
        plans.append(dict(copy=p['copy'],sha256=actual,expected=p['sha256'],original=p['original'],
                          originalHash=original_hash,originalCheck='MATCH' if original_hash==p['sha256'] else 'UNAVAILABLE'))
    check('0.1.0' in (ROOT/'pyproject.toml').read_text(),'version unexpected')
    labels=('w02-b-final-04','w02-a-compatibility-04','affected-compatibility-04','full-final-04')
    runs={}
    for label in labels:
        d=read(HERE/(label+'.json'))
        check(d['status']=='FINISHED' and d.get('exitCode')==0,'run not successful: '+label)
        same=d['sourceBefore']==d.get('sourceAfter')==now['source'];check(same,'run identity: '+label)
        runs[label]=dict(status=d['status'],run=d.get('run'),passed=d.get('passed'),skips=d.get('skips'),
            failures=d.get('failures'),errors=d.get('errors'),seconds=d.get('seconds'),exitCode=d.get('exitCode'),
            sourceMatches=same,sourceHash=fingerprint(d['sourceBefore']))
    full=read(HERE/'full-final-04.json')
    normalize=lambda ids:{i.removeprefix('tests.') for i in ids}
    old=read(ROOT/'docs/project_memory/w02_a_evidence/repair_r1_r2/full-final-02.json')
    full_ids=normalize(full['testIdentities']);old_ids=normalize(old['testIdentities'])
    check(full_ids==set(frozen['testIdentities']) and old_ids<=full_ids,'test identities changed')
    diff=git('diff','--check')
    dump(HERE/diff_name,dict(command=['git','diff','--check'],exitCode=diff.returncode,stdout=diff.stdout,stderr=diff.stderr))
    check(diff.returncode==0,'git diff --check')
    tracked=[p for p in git('diff','--name-only','-z').stdout.split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').stdout.split('\0') if p]
    excluded=set(base['excluded']);check(excluded<=set(untracked),'excluded file no longer untracked')
    pending=sorted(set(tracked+untracked)-excluded | {str((HERE/n).relative_to(ROOT)).replace('\\','/') for n in SELF_NAMES})
    allowed_source={p for p,h in now['source'].items() if base['source'].get(p)!=h}
    for p in pending:
        check(p in allowed_source or p in DOCS or p.startswith('docs/project_memory/w02_b_evidence/'),'out of scope: '+p)
    bodies={}
    link_details=[];broken_new=[];broken_old=[]
    for p in pending:
        path=ROOT/p
        if path.suffix!='.md' or not path.exists():continue
        text=path.read_text(encoding='utf-8-sig')
        prior=git('show','HEAD:'+p) if p in tracked else None
        oldtext=prior.stdout if prior and prior.returncode==0 else ''
        if p in DOCS:
            bodies[p]=check(oldtext in text,'historical document changed: '+p)
        old_targets={item['target'] for item in links(path,oldtext)}
        for item in links(path,text):
            item={**item,'file':p};link_details.append(item)
            if not item['exists']:
                (broken_old if item['target'] in old_targets else broken_new).append(item)
    check(not broken_new,'new broken links')
    parsed=[];parse_errors=[]
    for p in now['source']:
        if p.endswith('.py'):
            try:ast.parse((ROOT/p).read_text(encoding='utf-8-sig'),filename=p);parsed.append(p)
            except Exception as exc:parse_errors.append(dict(file=p,type=type(exc).__name__))
    check(not parse_errors,'AST invalid')
    rules={'privateKey':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
           'awsKey':r'\bAKIA[A-Z0-9]{16}\b','githubToken':r'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
           'providerKey':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b'}
    sensitive=[];artifacts=[];whitespace=[];raw_whitespace=[];historical_whitespace=[]
    for p in pending:
        path=ROOT/p
        if not path.exists():continue
        if '__pycache__' in path.parts or path.suffix.lower() in {'.pyc','.zip','.whl','.exe','.dll'} or any(x in path.parts for x in ('build','dist','.venv')):
            artifacts.append(p)
        try:text=path.read_text(encoding='utf-8-sig')
        except UnicodeError:artifacts.append(p);continue
        unchanged_lines=set()
        if p in tracked:
            previous=git('show','HEAD:'+p)
            if previous.returncode==0:
                matcher=difflib.SequenceMatcher(None,previous.stdout.splitlines(),text.splitlines(),autojunk=False)
                for tag,a,b,c,d in matcher.get_opcodes():
                    if tag=='equal':unchanged_lines.update(range(c+1,d+1))
        for name,pattern in rules.items():
            for m in re.finditer(pattern,text):sensitive.append(dict(file=p,rule=name,line=text[:m.start()].count('\n')+1))
        for i,line in enumerate(text.splitlines(),1):
            if line.rstrip(' \t')!=line:
                (raw_whitespace if path.suffix=='.log' else historical_whitespace if i in unchanged_lines
                 else whitespace).append(dict(file=p,line=i))
    check(not sensitive,'possible secret pattern');check(not artifacts,'unexpected artifact');check(not whitespace,'new non-log whitespace')
    sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
    from continuity_engine.testing.persistence import tree_inventory_hash
    formal_hash=tree_inventory_hash(ROOT/'.continuity-data')
    check(formal_hash=='sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2','formal tree changed')
    process=read(HERE/'process-cleanup.json')
    check(process.get('ownedRunPidsAlive')==[],'owned test process remains')
    if errors:
        failure=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),errors=errors,
            sourceHash=now['sourceHash'],sourceFrozenEqual=identity,runs=runs,
            newBrokenLinks=broken_new,historicalBrokenLinks=broken_old,
            possibleSecretPatterns=sensitive,artifactRisks=artifacts,newWhitespace=whitespace,
            historicalWhitespace=historical_whitespace,rawLogWhitespace=raw_whitespace,
            diffCheckRecord=diff_name,processCleanup=process,git=now['status'])
        dump(HERE/f'audit-attempt-{attempt:02}.json',failure)
        print(json.dumps(failure,ensure_ascii=False))
        raise SystemExit(1)
    selfs={str((HERE/n).relative_to(ROOT)).replace('\\','/') for n in SELF_NAMES}
    hashes={p:sha(ROOT/p) for p in pending if p not in selfs}
    dump(HERE/'final.files.json',dict(pending=pending,hashes=hashes,selfHashExcluded=sorted(selfs),
        excluded=now['excluded'],sourceChanged=sorted(allowed_source),sourceHash=now['sourceHash']))
    file_lines=['# W02-B 精确待提交与排除清单','',
        '仅供复核，尚未授权暂存或提交。本文件不执行Git写操作。文件集合从实际tracked diff与untracked中扣除原57项得到；来源逐项核对允许范围。',
        '',f'本批 {len(pending)} 项；原57项排除材料（32旧材料+25W01/规划）原样保留。源码/测试/资源{len(now["source"])}项指纹：`{now["sourceHash"]}`。',
        '', '文件hash见[机器清单](final.files.json)，全状态与保护核验见[审计](final.audit.json)。审计/清单三个自身文件为避免递归hash明确不自证，其余逐项SHA256；不是漏列文件。','',
        '## 本批成果','', '| 路径 | SHA256 |','|---|---|']
    file_lines.extend(f'| `{p}` | `{hashes.get(p,"SELF_HASH_EXCLUDED")}` |' for p in pending)
    file_lines += ['', '## 排除材料（不暂存、不删除、不移动）','', '| 路径 | SHA256 |','|---|---|']
    file_lines.extend(f'| `{p}` | `{h}` |' for p,h in sorted(now['excluded'].items()))
    with (HERE/'final.pending-files.md').open('x',encoding='utf-8',newline='\n') as out:out.write('\n'.join(file_lines)+'\n')
    audit=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),errors=errors,
        sourceCount=len(now['source']),sourceHash=now['sourceHash'],sourceFrozenEqual=identity,
        originalTests=len(old_ids),newTests=len(full_ids-old_ids),finalTests=len(full_ids),originalTestFilesExact=True,
        runs=runs,protectedUnchanged=now['protected']==base['protected'],protected=now['protected'],
        currentPlans=plans,excludedCount=len(excluded),excludedUnchanged=now['excluded']==base['excluded'],
        formalTreeHash=formal_hash,version='0.1.0',historicalDocBodiesExact=bodies,
        ast=dict(count=len(parsed),errors=parse_errors),links=dict(count=len(link_details),newBroken=broken_new,historicalBroken=broken_old),
        sensitiveScan=dict(rules=list(rules),hits=sensitive,limitation='Scoped patterns and diff review, not proof of absence of every possible secret'),
        artifactRisks=artifacts,newWhitespaceWarnings=whitespace,rawLogWhitespacePreserved=raw_whitespace,
        unchangedHistoricalWhitespace=historical_whitespace,
        diffCheck=dict(exitCode=diff.returncode,record=diff_name),processCleanup=process,
        pendingCount=len(pending),pendingFiles=pending,selfHashExcluded=sorted(selfs),
        git={k:now[k] for k in ('head','branch','localOrigin','origin','status','staged','tracked','indexHash')},
        indexUnchanged=now['indexHash']==base['indexHash'],gitWritesPerformed=False,
        remoteCheck=remote,
        remoteNote='Actual remote read-only query verified same main; first sandbox credential error retained. No push or CI PASS claim.',
        status='IMPLEMENTED_NOT_ACCEPTED',planningConflict='NONE',evidenceConflict='PRESENT',historicalF1H1F2='UNKNOWN')
    dump(HERE/'final.audit.json',audit)
    assert all((HERE/n).is_file() for n in SELF_NAMES)
    # Finish this newly generated audit after its own path exists. No run log or
    # prior audit is overwritten; this file is expressly excluded from self-hash.
    audit['git']['status']=git('status','--short','--untracked-files=all').stdout.strip()
    audit['git']['statusTiming']='after all three generated closing files exist'
    (HERE/'final.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:audit[k] for k in ('errors','sourceCount','sourceHash','pendingCount','excludedCount','formalTreeHash','indexUnchanged')},ensure_ascii=False))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
