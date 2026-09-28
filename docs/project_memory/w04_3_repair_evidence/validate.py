"""Fixed sequential validation; aborts on first failure or source change."""
import json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf8'))
frozen=read(HERE/'frozen-source-01.json')
target=read(HERE/'targeted-final-01.json')
assert target['exit_code']==0 and target['hash_before']==target['hash_after']==frozen['fingerprint']
old=ROOT/'docs/project_memory/w04_3_evidence'
groups=[('w04-3-final-01',['-m','unittest','-v','tests.test_w04_3_tools','tests.test_w04_3_repairs']),
        ('w04-12-final-01',read(old/'special-final-02.json')['command'][1:]),
        ('compatibility-final-01',read(old/'compatibility-final-02.json')['command'][1:]),
        ('full-final-01',['-m','unittest','discover','-s','tests','-v'])]
for label,args in groups:assert not (HERE/(label+'.json')).exists(),label
for label,args in groups:
    done=subprocess.run([sys.executable,str(HERE/'run.py'),label,*args],cwd=ROOT)
    record=read(HERE/(label+'.json'))
    if done.returncode or record['hash_before']!=record['hash_after'] or record['hash_after']!=frozen['fingerprint']:
        print('STOP validation: '+label,flush=True);sys.exit(done.returncode or 2)
