"""Finite sequential gates for the frozen source; stop at first failed group."""
import ast,json,pathlib,runpy,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
S=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
frozen=json.loads((HERE/'frozen-source-01.json').read_text(encoding='utf8'))
old=ROOT/'docs/project_memory/w04_2_public_repair_evidence'
parsed=ast.parse((old/'measure_recall.py').read_text(encoding='utf8'))
five=next(ast.literal_eval(n.value) for n in parsed.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TESTS' for t in n.targets))
compat=json.loads((old/'compatibility-current-01.json').read_text(encoding='utf8'))['command'][1:]
groups=[
 ('targeted-final-01',['-m','unittest','tests.test_w04_2_history_selection','tests.test_p18_runtime_contention','-v']),
 ('recall-formal-final-01',['-m','unittest',*five,'-v']),
 ('recall-load-final-01',['-m','unittest',*five[:2],'-v']),
 ('special-final-01',['-m','unittest','tests.test_w04_1_environment','tests.test_w04_2_simulation','tests.test_w04_2_registry_recheck','tests.test_w04_2_history_selection','-v']),
 ('compatibility-final-01',compat),
]
for label,arguments in groups:
    if S['source']()!=frozen['source']:raise RuntimeError('FROZEN_SOURCE_CHANGED')
    print('STARTING '+label,flush=True)
    result=subprocess.run([sys.executable,str(HERE/'run.py'),label,*arguments],cwd=ROOT)
    if result.returncode:sys.exit(result.returncode)
print('FIXED_GATES_COMPLETED; full regression has not been started',flush=True)
