import json,pathlib,sys,unittest
from unittest.mock import patch
from contextlib import ExitStack
from continuity_engine.services.context_composer_service import ContextComposerService
from continuity_engine.services.device_operation_service import DeviceOperationService
from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
rows=[];targets=[];calls=[0];compose=ContextComposerService.compose;history=DeviceOperationService.history_context;safe=JsonExternalProviderRepository._safe
def traced_compose(self,route,*a,**kw):
    result=compose(self,route,*a,**kw)
    if route.plan.request.request_id.startswith('device-history:'):
        rows.append(dict(route=route.to_dict(),result=result.to_dict()))
    return result
def traced_history(self,request_id,*a,**kw):
    targets.append(request_id);return history(self,request_id,*a,**kw)
def traced_safe(p):calls[0]+=1;return safe(p)
with ExitStack() as stack:
    stack.enter_context(patch.object(ContextComposerService,'compose',traced_compose))
    stack.enter_context(patch.object(DeviceOperationService,'history_context',traced_history))
    stack.enter_context(patch.object(JsonExternalProviderRepository,'_safe',staticmethod(traced_safe)))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('tests.test_w04_2_simulation.W04SimulatedChainTests.test_same_root_history_requery_does_not_create_independent_evidence'))
with (pathlib.Path(__file__).parent/(sys.argv[1]+'.trace.json')).open('x',encoding='utf8') as f:
    json.dump(dict(isolated_test_only=True,targets=targets,external_registry_reads=calls[0],observations=rows),f,ensure_ascii=False,indent=2)
sys.exit(0 if result.wasSuccessful() else 1)
