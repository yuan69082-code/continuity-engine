"""Discover identities without weakening loader errors; one measured invocation."""
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root)); sys.path.insert(0,str(root/'src'))
scope,label=sys.argv[1:]
directory=Path(__file__).resolve().parent
output=directory/(label+'.tests.json')
if output.exists(): raise FileExistsError(output)
loader=unittest.TestLoader()
discovered=loader.discover(str(root/'tests'))
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite): yield from flatten(item)
        else: yield item
prefixes=('test_p04_','test_p05_','test_p06_','test_p07_','test_p08_','test_p09_','test_p11_',
          'test_learning.','test_memory_service.','test_pre_p12_')
tests=[t for t in flatten(discovered) if scope=='full' or
       (scope=='p12' and t.id().startswith('test_p12_')) or
       (scope=='compat' and t.id().startswith(prefixes))]
if loader.errors: raise RuntimeError('\n'.join(loader.errors))
if not tests: raise ValueError('empty or unsupported suite')
source={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('src','tests') for p in sorted((root/folder).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
record={'scope':scope,'command':[sys.executable,*sys.argv], 'testIdentities':[t.id() for t in tests],
        'sourceTest':source,'status':'STARTED'}
output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
started=time.perf_counter()
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
failed_cases={getattr(t,'test_case',t).id() for t,_ in (*result.failures,*result.errors)}
record.update(status='FINISHED',run=result.testsRun,passed=result.testsRun-len(failed_cases)-len(result.skipped),
              failedTestCases=sorted(failed_cases),
              failures=[(t.id(),s) for t,s in result.failures],errors=[(t.id(),s) for t,s in result.errors],
              skips=[(t.id(),s) for t,s in result.skipped],seconds=round(time.perf_counter()-started,3))
output.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k not in ('testIdentities','sourceTest')},ensure_ascii=False))
raise SystemExit(0 if result.wasSuccessful() else 1)
