"""Sequential fixed-source validation. Stop on the first nonzero result."""
import json,runpy,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
frozen=json.loads((OUT/'frozen-source-02.json').read_text(encoding='utf8'))['source']
hashes=runpy.run_path(str(OUT/'run.py'))['source_hashes']
assert hashes()==frozen
groups=[
 ('originals-final-03',['--review-class','original_suites.baseline_suite']),
 ('advancing-final-02',['--review-class','original_suites.advancing_suite']),
 ('prior-boundaries-final-01',['--review-class','original_suites.IndependentPersistenceTests']),
 ('native-denial-final-02',['--review-class','test_native_access.native_suite']),
 ('p18-final-01',['test_p18_']),
 ('compatibility-final-01',['test_repository','test_event_persistence','test_evolution','test_service','test_p03_',
  'test_p15_','test_thinking','test_perception','test_action','test_awakening','test_e5_capability_recovery','test_p02_',
  'test_p09_','test_p14_','test_p16_','test_p17_','test_resources','test_p11_','test_pre_p12'])]
for label,args in groups:
 assert not (OUT/(label+'.json')).exists()
for label,args in groups:
 assert hashes()==frozen
 result=subprocess.run([sys.executable,str(OUT/'run.py'),label,*args],cwd=ROOT)
 assert hashes()==frozen
 if result.returncode:raise SystemExit(result.returncode)
print('FINAL TARGETED AND COMPATIBILITY GROUPS COMPLETE; FULL NOT YET RUN',flush=True)
