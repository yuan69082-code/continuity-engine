"""Summarize preserved H1 material; do not recreate missing observations."""
from pathlib import Path
import hashlib,json
OUT=Path(__file__).resolve().parent
OLD=OUT.parent/'p18_evidence'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    target=OUT/'h1-investigation.json';assert not target.exists()
    old=read(OLD/'p18-final-04.json');final=read(OLD/'p18-final-07.json')
    row=next(json.loads(s) for s in (OLD/'p18-final-04.stdout.log').read_text(encoding='utf8').splitlines()
        if 'test_resource_wait_host_lives_and_restores_without_message' in s)
    stop=next(r for r in row['processEvidence'] if r['stage']=='controller-stop-cleanup')
    child=next(r for r in row['processEvidence'] if r['stage']=='continuous-child')
    view=json.loads(stop['stdout'])
    current=read(OUT/'formal-final-01.json')
    observations=[]
    for line in (OUT/'formal-final-01.stdout.log').read_text(encoding='utf8').splitlines():
        try:r=json.loads(line)
        except ValueError:continue
        for e in r.get('processEvidence',[]):
            if e.get('stage') in {'h1-controlled-clock-interleaving','controller-timeout-before-stop'}:
                observations.append(dict(test=r['test'],evidence=e))
    result=dict(rootCause='UNKNOWN',evidenceConflict='PRESENT',R1IsNotEstablishedH1Cause=True,
        historicalLabel='p18-final-04',historicalRun=old['run'],historicalPassed=old['passed'],historicalFailures=old['failures'],
        historicalSourceBeforeAfterMatch=old['sourceBefore']==old['sourceAfter'],
        historicalFiles={p.name:sha(p) for p in (OLD/'p18-final-04.json',OLD/'p18-final-04.stdout.log',OLD/'p18-final-04.stderr.log')},
        sourceDifferencesToPriorFinal=sorted(p for p,h in old['sourceAfter'].items() if final['sourceAfter'].get(p)!=h),
        knownAtCleanup=dict(hostAlive=view['host_alive'],exitCode=child['exitCode'],forcedCleanup=child['forcedCleanup'],
            childrenReaped=row['childrenReaped'],activity=view['activity'],reason=view['reason'],lastTime=view['last_time'],
            nextCheckAt=view['next_check_at'],lastTask=view['last_task'],observations=view['observations'],
            pendingTasks=view['pending_tasks'],unconfirmedTasks=view['unconfirmed_tasks'],resources=view['resources']),
        missingEvidence=['pre-STOP activity/reason/next_check_at','exact task states and attempts at timeout',
            'clock read and transaction interleaving at failure','resource preview result at failure',
            'byte-exact old changed source contents (only their SHA-256 inventory is retained)'],
        excludedClaims=['A no-STOP exit 2 is inconsistent with the recorded alive host and subsequent STOP exit 0.',
            'The final full run finished before quota interruption; quota interruption is not a demonstrated H1 cause.',
            'Later PASS, fairness/STOP fixes and current controlled interleavings do not prove the historical cause.'],
        currentControlledEvidence=dict(label='formal-final-01',sourceBeforeAfterMatch=current['sourceBefore']==current['sourceAfter'],
            observations=observations,interpretation='Current controlled clock overlap and pre-STOP timeout capture passed; not reconstruction of missing historical state.'),
        remainingRisk='An intermittent resource-wait observation failure cannot be ruled out from the incomplete historical record. Independent review must retain UNKNOWN or explicitly assess this residual evidence limitation.')
    with target.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    assert len(observations)==2
    print(json.dumps(dict(rootCause=result['rootCause'],controlledObservations=len(observations),oldSourceDelta=result['sourceDifferencesToPriorFinal'])))

if __name__=='__main__':main()
