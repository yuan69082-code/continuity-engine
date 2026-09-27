"""Two predeclared repeats per original load. Observation after product timing."""
import json,pathlib,sys,unittest
from unittest.mock import patch
from continuity_engine.services.associative_recall_service import AssociativeRecallService
HERE=pathlib.Path(__file__).resolve().parent
rows=[];current=[''];original=AssociativeRecallService._prepare
def measured(self,perception,operation,save,**kw):
    def keep(record):
        rows.append(dict(test=current[0],**{k:record.get(k) for k in ('status','stop_reason','elapsed_ms','retrieved_count','model_calls','external_calls','policy')}))
    def saved(record):keep(record);return save(record)
    value=original(self,perception,operation,saved,**kw);keep(value[2]);return value
class Result(unittest.TextTestResult):
    def startTest(self,test):current[0]=test.id();super().startTest(test)
names=['tests.test_w02_recall_timeout.W02RecallTimeoutTests.'+n for n in ('test_four_materials_preanswer_with_original_1000ms_policy','test_third_message_sixteen_candidates_and_current_derived_sources')]
with patch.object(AssociativeRecallService,'_prepare',measured):
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromNames(names) for _ in range(2)])
    result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
with (HERE/(sys.argv[1]+'.trace.json')).open('x',encoding='utf8') as f:json.dump(rows,f,indent=2)
sys.exit(0 if result.wasSuccessful() else 1)
