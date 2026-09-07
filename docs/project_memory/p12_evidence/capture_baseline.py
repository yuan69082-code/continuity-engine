"""Read-only baseline capture; writes only this phase's evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[3]
os.chdir(root)
sys.path.insert(0, str(root))
directory = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):
    return subprocess.check_output(['git', *args], env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode('utf-8').strip()
previous = json.loads((root/'docs/project_memory/pre_p12_acceptance_evidence/before.json').read_text(encoding='utf-8'))
stable = json.loads((root/'docs/project_memory/pre_p12_r05_r06_evidence/stable-source.json').read_text(encoding='utf-8'))
assert git('rev-parse','HEAD') == '1b8020fbe687dafaaf83a629dbeee65d69a71d67'
assert git('branch','--show-current') == 'main'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
protected = {p:sha(p) for p in previous['protected']}
assert protected == previous['protected']
source = {p:sha(p) for p in stable['sourceTest']}
assert source == stable['sourceTest']
loader = unittest.TestLoader()
suite = loader.discover('tests')
def identities(s):
    for t in s:
        if isinstance(t,unittest.TestSuite): yield from identities(t)
        else: yield t.id()
ids = sorted(identities(suite))
assert not loader.errors and ids == sorted(stable['testIdentities'])
tracked = git('ls-files','-z').split('\0')
untracked = git('ls-files','--others','--exclude-standard','-z').split('\0')
p10 = {p:sha(p) for p in untracked if p.startswith('docs/project_memory/p10_evidence/')}
assert len(p10) == 31
data = {'capturedAt':datetime.now(timezone.utc).isoformat(), 'head':git('rev-parse','HEAD'),
        'branch':git('branch','--show-current'),'originMain':git('rev-parse','origin/main'),
        'aheadBehind':git('rev-list','--left-right','--count','HEAD...origin/main'),
        'sourceTest':source,'testIdentities':ids,'protected':protected,'p10Untracked':p10,
        'trackedFiles':{p:sha(p) for p in tracked if p},
        'formalFiles':{p:sha(p) for p in sorted(str(x).replace('\\','/') for x in Path('.continuity-data').rglob('*') if x.is_file())},
        'fullBaseline':'CITED, not rerun: 894 total; 893 PASS, 1 Windows symlink 1314 SKIP; 425.134 seconds',
        'baselineEvidence':'../pre_p12_r05_r06_evidence/full-stable.stderr.log',
        'workflowFiles':list(Path('.github/workflows').glob('*')) if Path('.github/workflows').exists() else [],
        'helperErrors':['Read attempts for nonexistent context_sources.py and test_p04_memory.py; corrected paths with rg; no tests executed by these reads.', 'First planning text console output used non-UTF8; source extraction preserved UTF-8 and reread with PYTHONUTF8=1.']}
path = directory/'before.json'
if path.exists(): raise FileExistsError(path)
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'head':data['head'],'sourceFiles':len(source),'tests':len(ids),'protected':len(protected),'formal':len(data['formalFiles']),'p10':len(p10),'baseline':'CITED'},ensure_ascii=False))
