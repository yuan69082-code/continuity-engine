"""Read-only completion check. Never stop other processes or remove fixtures."""
import datetime,json,os,pathlib,subprocess
HERE=pathlib.Path(__file__).resolve().parent
assert not (HERE/'process-cleanup.json').exists()
record=json.loads((HERE/'full-final-01.json').read_text(encoding='utf8'))
assert record['status']=='COMPLETED','full regression still unresolved'
command=['powershell','-NoProfile','-Command',
    "@(Get-Process python,pythonw -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,Path) | ConvertTo-Json -Depth 3"]
result=subprocess.run(command,capture_output=True,text=True,encoding='utf8')
assert result.returncode==0,result.stderr
rows=json.loads(result.stdout) if result.stdout.strip() else []
if isinstance(rows,dict):rows=[rows]
remaining=[r for r in rows if r['Id']!=os.getpid()]
phases=[json.loads(line) for line in (HERE/'targeted-final-02.stdout.log').read_text(encoding='utf8').splitlines() if line.startswith('{')]
retained=[line for line in (HERE/'full-final-01.stdout.log').read_text(encoding='utf8').splitlines() if line.startswith('RETAINED_CONTROLLED_')]
data=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),full_status=record['status'],full_exit=record['exit_code'],
    process_observation_command=command,observed_python=rows,observer_pid=os.getpid(),
    remaining_owned_processes=remaining,classification='No other Python process observed' if not remaining else 'Needs identity review; no termination authorized by this helper',
    explicit_test_subprocesses=phases,forced_test_cleanup=False,
    orchestrator_only_stop='validation-order-stop-01.json: first orchestration stopped before its full run, compatibility finished normally',
    retained_controlled_fixtures=retained,retained_reason='Original tests deliberately preserve controlled failure/interrupt evidence; no unrelated cleanup',
    no_production_service_installed=True)
(HERE/'process-cleanup.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(remaining_python_count=len(remaining),subprocess_exit_codes=[r.get('exit_code') for r in phases],retained_controlled_fixtures=len(retained))))
assert not remaining,'Need to identify remaining processes, never kill blindly'
