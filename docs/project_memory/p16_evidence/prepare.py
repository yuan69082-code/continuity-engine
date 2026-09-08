"""P16 read-only baseline and stage records; no Git writes or behavior tests."""
import hashlib,json,re,subprocess,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;DOC=ROOT/'docs/project_memory'
sys.path[:0]=[str(ROOT),str(ROOT/'src')];sys.dont_write_bytecode=True
from continuity_engine.testing.persistence import tree_inventory_hash
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def git(*args):return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,encoding='utf-8').strip()
def flatten(s):
    for t in s:
        if isinstance(t,unittest.TestSuite):yield from flatten(t)
        else:yield t
def main():
    a=read(DOC/'p15_acceptance_evidence/precommit.audit.json');b=read(DOC/'p15_acceptance_evidence/before.json')
    assert git('rev-parse','HEAD')==git('rev-parse','origin/main')=='a41a733635b0f5978c19b287274b4c63925b8979'
    assert git('branch','--show-current')=='main' and not git('diff','--name-only') and not git('diff','--cached','--name-only')
    current={p.relative_to(ROOT).as_posix():sha(p) for folder in ('src','tests') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert current==a['sourceTest']
    for k in ('protected','plans','formalFiles','excludedP10','otherPreserved'):
        for p,h in b[k].items():assert sha(ROOT/p)==h,p
    loader=unittest.TestLoader();tests=[t.id() for t in flatten(loader.discover(str(ROOT/'tests')))];assert not loader.errors
    full=read(DOC/'p15_repair_evidence/full-final.json');assert tests==full['testIdentities']
    brief=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p16-kickoff-20260909/implementation-brief.md')
    with (OUT/'implementation-brief.md').open('xb') as f:f.write(brief.read_bytes())
    baseline={'at':datetime.now(timezone.utc).isoformat(),'head':git('rev-parse','HEAD'),'originMain':git('rev-parse','origin/main'),
        'sourceTest':current,'testIdentities':tests,'citedFull':{k:full[k] for k in ('command','run','passed','skips','seconds','exitCode')},
        'baselineTestsRerun':False,'briefSource':str(brief),'briefHash':sha(brief),'formalTreeHash':tree_inventory_hash(ROOT/'.continuity-data'),
        **{k:b[k] for k in ('protected','plans','formalFiles','excludedP10','otherPreserved')},
        'gitStatus':git('status','--short','--untracked-files=all'),
        'trackedHashes':{p:sha(ROOT/p) for p in git('ls-files').splitlines()},
        'auxiliaryReadErrors':['Initial guessed action_capability_service/context_router_ports/context_composer_ports paths absent; inspected actual files instead.','PowerShell rg glob paths were invalid; used actual paths. No code changes or behavior tests occurred.']}
    with (OUT/'before.json').open('x',encoding='utf-8') as f:json.dump(baseline,f,ensure_ascii=False,indent=2);f.write('\n')
    planning=read(DOC/'p12_evidence/planning-source.json');extract={}
    for name,d in planning.items():
        assert sha(Path(d['source']))==d['sha256']
        blocks=d['blocks'];indexes={i for i,t in enumerate(blocks) if any(k in t for k in ('P16','Credential Broker','Memory Provider','Knowledge Provider','KEEP-','OVERRIDE-','附录 E','统一验收','E-1','E-2','E-3'))}
        extract[name]={'source':d['source'],'sha256':d['sha256'],'blocks':[{'index':i,'text':blocks[i]} for i in sorted(indexes)]}
    with (OUT/'planning-extract.json').open('x',encoding='utf-8') as f:json.dump(extract,f,ensure_ascii=False,indent=2);f.write('\n')
    original=DOC/'p15_repair_evidence/run.py'
    with (OUT/'run.py').open('xb') as f:f.write(original.read_bytes())
    decision=DOC/'04_决策记录.md';text=decision.read_text(encoding='utf-8-sig');assert not re.search(r'^## D-068[：:]',text,re.M)
    decision.write_text(text+'\n\n## D-068：用户授权P16外部记忆知识与可插拔能力独立施工\n\n2026-09-09用户确认开工，以本次转发简报为范围。P15已验收/push，不重复收尾。仅Engine中立Port、Registry、Broker引用、缓存及原E5-A/C1最小接线，首批全为隔离本地Fake；不选生产供应商、外网、真实凭据、Vio或Assistant。具体Stage Brief见[75](75_P16_外部记忆知识与可插拔能力架构边界.md)。最高IMPLEMENTED_NOT_ACCEPTED；D-069不创建、不使用；不Git写操作、不进入P17。\n',encoding='utf-8')
    print('P16 baseline verified',len(current),'files',len(tests),'test identities; historical full only, D-068 registered')
if __name__=='__main__':main()
