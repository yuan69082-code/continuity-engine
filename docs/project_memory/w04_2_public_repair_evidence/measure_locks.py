"""One unchanged run of each failing process test, with inherited TEST tracing."""
import os,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
dest=HERE/sys.argv[1]
dest.mkdir(exist_ok=False)
env={**os.environ,'W04_LOCK_TRACE_DIR':str(dest),'PYTHONPATH':str(HERE/'lock_trace')+os.pathsep+os.environ.get('PYTHONPATH','')}
if len(sys.argv)>2 and sys.argv[2]=='hold':env['W04_LOCK_HOLD_DIAGNOSTIC']='1'
tests=['tests.test_p18_runtime_contention.RuntimeContentionTests.'+name for name in (
'test_long_busy_host_remains_live_and_diagnostic_is_not_flooded',
'test_start_waits_for_checkpoint_without_relaxing_owner_lock')]
sys.exit(subprocess.run([sys.executable,'-m','unittest',*tests,'-v'],env=env).returncode)
