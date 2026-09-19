"""Sequential final validation. Never retry or proceed past a failed group."""
from pathlib import Path
import os, subprocess, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
GROUPS=(
    ('resume-final-02','--review-class','test_independent_resume.IndependentResumeTests'),
    ('confirmation-final-02','--review-class','test_pause_resume_confirmation.PauseResumeConfirmation'),
    ('p18-final-02','test_p18_'),
    ('compatibility-final-01','test_thinking','test_perception','test_action','test_awakening',
     'test_e5_capability_recovery','test_p02_','test_p09_','test_p14_','test_p16_',
     'test_p17_','test_resources','test_p11_','test_pre_p12'),
    ('full-final-01',),
)
if __name__=='__main__':
    for group in GROUPS:
        command=[sys.executable,str(HERE/'run.py'),*group]
        result=subprocess.run(command,cwd=ROOT,env={**os.environ,'PYTHONUTF8':'1',
            'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'src')})
        if result.returncode:
            print('Validation stopped at '+group[0],flush=True)
            raise SystemExit(result.returncode)
