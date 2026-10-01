"""Explicit one-pass group order. Any nonzero group stops; no retries."""
import json,pathlib,subprocess,sys
here=pathlib.Path(__file__).resolve().parent
labels=['targeted-final-02','w04-final-02','public-final-02','full-final-02']
assert all(not (here/(label+'.json')).exists() for label in labels)
diagnostic=json.loads((here/'full-errors-stations-after-01.json').read_text(encoding='utf8'))
assert diagnostic['status']=='COMPLETED' and diagnostic['exit_code']==0
for label in labels:
    result=subprocess.call([sys.executable,str(here/'final-validation-02.py'),label],cwd=here.parents[2])
    if result:raise SystemExit(result)
