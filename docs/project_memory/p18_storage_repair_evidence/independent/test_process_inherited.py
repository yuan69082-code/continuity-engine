"""Run the unchanged original methods and reviewed read-overlap wrappers."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'docs/project_memory/p18_f1_h1_evidence/independent')]
import test_p18_runtime_process
import test_process_hypotheses
import json
from datetime import datetime,timezone
from continuity_engine.testing.persistence import atomic_write_json

def baseline_suite():
    suite=unittest.TestSuite()
    for cls in (test_p18_runtime_process.RuntimeProcessTests,test_process_hypotheses.OriginalFlowWithReadOverlap):
        for name in ('test_idle_and_subject_silence_do_not_end_process','test_resource_wait_host_lives_and_restores_without_message'):
            suite.addTest(cls(name))
    return suite

class AdvancingClockFlow(test_process_hypotheses.OriginalFlowWithReadOverlap):
    """Separate contrast; inherited frozen-clock counterexamples stay unchanged."""
    def start(self,command=None):
        profile=self.root/'p18-test-profile.json'
        data=json.loads(profile.read_text(encoding='utf8'))
        if data['test_clock_rate']==0:
            data['test_clock_rate']=1
            data['real_anchor']=datetime.now(timezone.utc).isoformat()
            atomic_write_json(profile,data)
            self.records.append(dict(stage='separate-continuous-clock-control',test_clock_rate=1,
                assertionTimeoutSeconds=25,originalFrozenCounterexampleUnchanged=True))
        return super().start(command)

def advancing_suite():
    return unittest.TestSuite(AdvancingClockFlow(name) for name in (
        'test_idle_and_subject_silence_do_not_end_process',
        'test_resource_wait_host_lives_and_restores_without_message'))
