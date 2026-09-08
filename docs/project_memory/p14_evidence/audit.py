"""Read-only P14 verification and exact pending inventory; never stages files."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))
from continuity_engine.testing.persistence import tree_inventory_hash


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT,
        env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode('utf8').strip()


def links(path, content, expected=()):
    bad=[]; count=0
    for value in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', content):
        value=unquote(value.strip().strip('<>'))
        if re.match(r'^(https?://|mailto:|#)',value):continue
        value=value.split('#')[0]
        value=re.sub(r':\d+$','',value)
        if not value:continue
        target=Path(value) if Path(value).is_absolute() else path.parent/value
        count+=1
        if not target.exists() and target.resolve() not in expected:bad.append(value)
    return count,bad


def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'final'
    if not re.fullmatch(r'[a-z0-9-]+',label):raise ValueError('invalid label')
    target=OUT/(label+'.audit.json')
    pending=OUT/(label+'.pending-files.md')
    assert not target.exists() and not pending.exists(), 'preserve original audit evidence'
    baseline=read(OUT/'before.json')
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests')
        for p in sorted((ROOT/folder).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    record={'at':datetime.now(timezone.utc).isoformat(),'sourceTest':current,'errors':[]}
    record['sourceTestCount']=len(current)
    record['sourceTestInventoryHash']='sha256:'+hashlib.sha256(json.dumps(current,sort_keys=True,
        separators=(',',':')).encode('utf8')).hexdigest()
    resume=read(OUT/'resume-affective-before.json')['sourceBefore']
    paused=read(OUT/'affective-chain-first.json')['sourceAfter']
    record['resumeMatchedPausedSource']=resume==paused
    if resume!=paused:record['errors'].append('unexplained resume source changes')
    for key in ('protected','plans','formalFiles','excludedP10'):
        mismatches=[p for p,h in baseline[key].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        record[key]={'count':len(baseline[key]),'changed':mismatches}
        if mismatches:record['errors'].append(key+' changed')
    record['formalTreeHash']=tree_inventory_hash(ROOT/'.continuity-data')
    if record['formalTreeHash']!=baseline['formalTreeHash']:record['errors'].append('formal tree changed')
    old_tests={p:h for p,h in baseline['sourceTest'].items() if p.startswith('tests/')}
    record['originalTestFileChanges']=[p for p,h in old_tests.items() if current.get(p)!=h]
    if record['originalTestFileChanges']:record['errors'].append('original test file changed')
    record['verifiedRuns']={}
    for label_run in ('p14-final-2','compatibility-final','targeted-compatibility-final','full-final'):
        run=read(OUT/(label_run+'.json'))
        record['verifiedRuns'][label_run]={'run':run.get('run'),'passed':run.get('passed'),
            'failures':len(run.get('failures',[])),'errors':len(run.get('errors',[])),
            'skips':run.get('skips',[]),'seconds':run.get('seconds'),
            'unchangedDuringRun':run['sourceBefore']==run['sourceAfter'],
            'matchesCurrent':run['sourceAfter']==current,'command':run['command']}
        changed=sorted(p for p in set(current)|set(run['sourceAfter']) if current.get(p)!=run['sourceAfter'].get(p))
        record['verifiedRuns'][label_run]['laterChangedFiles']=changed
        # The preserved 741-test compatibility run predates the final P14-only
        # stance fix. Its complete identities are also executed by final full.
        allowed_later={'src/continuity_engine/services/dynamic_mind_service.py','tests/test_p14_mind_recovery.py'}
        permitted_delta=label_run=='compatibility-final' and set(changed)<=allowed_later
        if (run.get('exitCode')!=0 or run['sourceBefore']!=run['sourceAfter']
                or (changed and not permitted_delta)):record['errors'].append(label_run+' identity/result mismatch')
    full=read(OUT/'full-final.json')
    compatibility=read(OUT/'compatibility-final.json')
    record['compatibilityIdentitiesIncludedInFinalFull']=set(compatibility['testIdentities'])<=set(full['testIdentities'])
    if not record['compatibilityIdentitiesIncludedInFinalFull']:record['errors'].append('compatibility identities missing from final full')
    record['missingOriginalTestIdentities']=sorted(set(baseline['originalTestIdentities'])-set(full['testIdentities']))
    if record['missingOriginalTestIdentities']:record['errors'].append('missing original tests')
    record['astCount']=0
    for path in current:
        if path.endswith('.py'):
            ast.parse((ROOT/path).read_text(encoding='utf-8-sig'),filename=path)
            record['astCount']+=1
    tracked=[p for p in git('diff','--name-only','-z').split('\0') if p]
    untracked=[p for p in git('ls-files','--others','--exclude-standard','-z').split('\0') if p]
    excluded=sorted(p for p in untracked if p in baseline['excludedP10'])
    if set(excluded)!=set(baseline['excludedP10']):record['errors'].append('excluded script inventory changed')
    paths=sorted(set(tracked+untracked)-set(excluded))
    generated=[target.relative_to(ROOT).as_posix(),pending.relative_to(ROOT).as_posix()]
    paths=sorted(set(paths+generated))
    record['pending']=paths
    record['excluded']=excluded
    record['pendingHashes']={p:sha(ROOT/p) for p in paths if (ROOT/p).is_file()}
    brief=(ROOT/'docs/project_memory/67_P14_ContinuousDynamicMind架构边界.md').read_text(encoding='utf8')
    allowed_code=set(re.findall(r'`((?:src|tests)/[^`]+\.py)`',brief))
    allowed_docs={'README.md'}|{p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/project_memory').glob('*.md')
        if re.match(r'^(?:00_|01_|02_|03_|04_|05_|06_|07_|10_|11_|12_|13_|67_|68_|69_|70_|CHANGELOG\.md|工程总档案\.md)',p.name)}
    record['outsideAllowedScope']=[p for p in paths if p not in allowed_code|allowed_docs
                                   and not p.startswith('docs/project_memory/p14_evidence/')]
    if record['outsideAllowedScope']:record['errors'].append('file outside Stage Brief')
    forbidden=[p for p in paths if any(x in Path(p).parts for x in
        ('.continuity-data','__pycache__','.git','build','dist')) or p.endswith(('.whl','.pyc','.zip'))]
    record['forbiddenArtifacts']=forbidden
    if forbidden:record['errors'].append('forbidden artifact')
    record['sensitiveMatches']=[];record['localLinkCount']=0;record['newBrokenLinks']=[];record['historicalBrokenLinks']=[]
    secret=re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{32,})')
    for name in paths:
        p=ROOT/name
        if not p.is_file():continue
        if p.suffix in {'.py','.md','.json','.log'}:
            content=p.read_text(encoding='utf-8-sig')
            if secret.search(content):record['sensitiveMatches'].append(name)
        if p.suffix=='.md':
            count,bad=links(p,content,{target.resolve(),pending.resolve()});record['localLinkCount']+=count
            old_bad=[]
            if name in tracked:
                _,old_bad=links(p,git('show','HEAD:'+name))
            record['historicalBrokenLinks'].extend((name,v) for v in bad if v in old_bad)
            record['newBrokenLinks'].extend((name,v) for v in bad if v not in old_bad)
    if record['sensitiveMatches'] or record['newBrokenLinks']:record['errors'].append('sensitive/link check')
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    record['diffCheck']={'exitCode':diff.returncode,'stdout':diff.stdout,'stderr':diff.stderr}
    if diff.returncode:record['errors'].append('git diff --check')
    record['git']={'branch':git('branch','--show-current'),'head':git('rev-parse','HEAD'),
        'originMain':git('rev-parse','origin/main'),'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
        'staged':git('diff','--cached','--name-only'),'status':git('status','--short','--untracked-files=all'),
        'remote':git('remote','-v'),'ciWorkflows':git('ls-files','.github/workflows')}
    ignored=[p for p in git('ls-files','--others','--ignored','--exclude-standard','-z').split('\0') if p]
    record['ignoredArtifacts']={'count':len(ignored),'paths':ignored,
        'action':'read-only inventory; not deleted or included in pending list',
        'baselineComparison':'formal seven files compared separately; no pre-P14 hash baseline for old caches'}
    if (record['git']['head']!=baseline['head'] or record['git']['originMain']!=baseline['originMain']
            or record['git']['branch']!='main' or record['git']['staged']):record['errors'].append('git baseline changed')
    pending.write_text('# P14 精确待提交清单（本轮没有 Git 写操作）\n\n'+
        f'P14 工作区文件 {len(paths)} 个，排除 P10 原有脚本 {len(excluded)} 个。验收与提交均待用户另行授权。\n\n'+
        '\n'.join('- `'+p+'`' for p in paths)+'\n\n## 原样保留的排除项\n\n'+
        '\n'.join('- `'+p+'`' for p in excluded)+'\n',encoding='utf8')
    record['pendingHashes'][pending.relative_to(ROOT).as_posix()]=sha(pending)
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:record[k] for k in ('errors','astCount','localLinkCount','formalTreeHash')},ensure_ascii=False))
    print('pending',len(paths),'excluded',len(excluded))
    return bool(record['errors'])


if __name__=='__main__':
    raise SystemExit(main())
