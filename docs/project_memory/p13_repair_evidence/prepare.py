"""One-time R1/R2 baseline capture and byte-identical independent evidence copy."""
import hashlib,json,os,subprocess
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
source=Path('C:/Users/Administrator/Documents/Codex/2026-08-24/https-github-com-yuan69082-code-continuity/reviews/p13-independent-review-20260908')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git',*args],cwd=root,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True,encoding='utf-8').strip()
old=json.loads((root/'docs/project_memory/p13_evidence/final-audit.audit.json').read_text(encoding='utf-8'))
assert not (out/'before.json').exists()
for section in ('sourceTest','protected','plans','contentHashes'):
    for name,value in old[section].items():
        assert sha(root/name)==value,(section,name)
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')==old['head']
assert git('branch','--show-current')=='main' and not git('diff','--cached','--name-only')
assert sha(source/'review_probes.py')=='934836489840b194110d303ba963c0ce95d4a804b14b872fa32b0380d36a5f53'
workspace={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*')
           if p.is_file() and not any(x in p.parts for x in ('.git','__pycache__','p13_repair_evidence')) and p.suffix!='.pyc'}
record={'at':datetime.now(timezone.utc).isoformat(),'head':old['head'],
        'sourceTest':old['sourceTest'],'protected':old['protected'],'plans':old['plans'],
        'formalFiles':old['formalFiles'],'formalTreeHash':old['formalTreeHash'],
        'excludedP10':old['excludedP10'],'workspace':workspace,'citedFullOnly':old['full'],
        'status':git('-c','core.quotepath=false','status','--porcelain=v1','--untracked-files=all'),
        'independentOriginals':{}}
(out/'independent').mkdir()
for name in ('review-report.md','review_probes.py','probes-01.stderr.log','probes-02.stderr.log',
             'helper-history.md','identity-check.json','original-p13-01.stderr.log'):
    p=source/name
    (out/'independent'/name).write_bytes(p.read_bytes())
    record['independentOriginals'][str(p)]=sha(p)
for name in ('run_tests.py','run_suite.py'):
    (out/name).write_bytes((root/'docs/project_memory/p13_evidence'/name).read_bytes())
(out/'before.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Baseline verified:',len(record['sourceTest']),'source/test/resource;',len(record['protected']),'protected; HEAD',record['head'])
