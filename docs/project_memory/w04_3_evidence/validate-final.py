"""One ordered validation plan; stops on any failure, never reruns a label."""
import json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
HERE=pathlib.Path(__file__).resolve().parent
frozen=json.loads((HERE/'frozen-source-02.json').read_text(encoding='utf8'))
target=json.loads((HERE/'targeted-final-01.json').read_text(encoding='utf8'))
assert target.get('exit_code')==0 and target['hash_before']==target['hash_after']==frozen['fingerprint']
old=json.loads((ROOT/'docs/project_memory/w04_2_completion_evidence/compatibility-final-01.json').read_text(encoding='utf8'))
groups=[('special-final-01',['-m','unittest','-v','tests.test_w04_1_environment','tests.test_w04_2_simulation','tests.test_w04_2_registry_recheck','tests.test_w04_2_history_selection']),
        ('compatibility-final-01',old['command'][1:]),
        ('full-final-01',['-m','unittest','discover','-s','tests','-v'])]
for label,args in groups:
    assert not (HERE/(label+'.json')).exists(),label
for label,args in groups:
    done=subprocess.run([sys.executable,str(HERE/'run.py'),label,*args],cwd=ROOT)
    record=json.loads((HERE/(label+'.json')).read_text(encoding='utf8'))
    if done.returncode or record['hash_before']!=record['hash_after'] or record['hash_after']!=frozen['fingerprint']:
        print('STOP validation:',label,flush=True);sys.exit(done.returncode or 2)
