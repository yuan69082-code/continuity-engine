import cProfile,json,pathlib,pstats,sys,unittest
from unittest.mock import patch
from continuity_engine.services.associative_recall_service import AssociativeRecallService
HERE=pathlib.Path(__file__).resolve().parent
rows=[];original=AssociativeRecallService._prepare
def measured(self,*a,**kw):
    profile=cProfile.Profile();profile.enable()
    try:return original(self,*a,**kw)
    finally:
        profile.disable();stats=pstats.Stats(profile)
        rows.append([dict(file=k[0],line=k[1],function=k[2],primitive=v[0],calls=v[1],own_seconds=v[2],total_seconds=v[3]) for k,v in stats.stats.items()])
with patch.object(AssociativeRecallService,'_prepare',measured):
    names=['tests.test_w02_recall_timeout.W02RecallTimeoutTests.'+n for n in ('test_four_materials_preanswer_with_original_1000ms_policy','test_third_message_sixteen_candidates_and_current_derived_sources')]
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
with (HERE/(sys.argv[1]+'.trace.json')).open('x',encoding='utf8') as f:json.dump(rows,f,indent=2)
sys.exit(0 if result.wasSuccessful() else 1)
