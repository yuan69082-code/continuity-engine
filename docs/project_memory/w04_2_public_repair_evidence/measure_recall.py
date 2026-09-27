"""Run the original five tests once with bounded per-prepare aggregate timing."""
from collections import defaultdict
from contextlib import ExitStack
import json, pathlib, sys, time, unittest
from unittest.mock import patch
from continuity_engine.services import associative_recall_service as rm
from continuity_engine.services.context_router_service import ContextRouterService
from continuity_engine.services.context_composer_service import ContextComposerService
from continuity_engine.services.input_context_source import InputContextSource,HistoricalInputContextSource
from continuity_engine.services.external_capability_service import ExternalCapabilityService
from continuity_engine.services.external_context_source import ExternalContextSource
from continuity_engine.services.external_absorption_service import ExternalAbsorptionService
from continuity_engine.storage import json_integration_repository as jm
HERE=pathlib.Path(__file__).resolve().parent
TESTS=[
'tests.test_w02_recall_timeout.W02RecallTimeoutTests.test_four_materials_preanswer_with_original_1000ms_policy',
'tests.test_w02_recall_timeout.W02RecallTimeoutTests.test_third_message_sixteen_candidates_and_current_derived_sources',
'tests.test_w02_integration.W02IntegratedChainTests.test_partial_derived_withdrawal_invalidates_integrated_reply_and_support',
'tests.test_w02_integration.W02IntegratedChainTests.test_raw_message_stations_old_memory_receipt_and_final_preanswer_context',
'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_w02_a_and_b_real_ingress_share_pre_answer_external_candidate']
def main():
    dest=HERE/(sys.argv[1]+'.trace.json')
    if dest.exists():raise ValueError('existing trace')
    active=[None];records=[];current=[''];overhead=[0,0]
    with ExitStack() as stack:
        def wrap(obj,name,label,static=False):
            original=getattr(obj,name)
            def measured(*a,**kw):
                item=active[0]
                if item is None:return original(*a,**kw)
                t=time.perf_counter_ns()
                try:return original(*a,**kw)
                finally:
                    end=time.perf_counter_ns();m=item['metrics'][label];m[0]+=1;m[1]+=end-t
                    overhead[0]+=time.perf_counter_ns()-end;overhead[1]+=1
            stack.enter_context(patch.object(obj,name,staticmethod(measured) if static else measured))
        for obj,name,label in (
            (ContextRouterService,'route','router'),(ContextComposerService,'compose','composer'),
            (rm.AssociativeRecallService,'_authorize','authorize'),(rm.AssociativeRecallService,'_preference_candidates','preference'),
            (InputContextSource,'_material','input_material'),(HistoricalInputContextSource,'retrieve','history'),
            (jm.JsonIntegrationResultLedger,'_load_operations','operations_load'),(jm.JsonIntegrationResultLedger,'_load_capability_document','capability_load'),
            (jm,'deepcopy','journal_copy'),(rm,'assess','candidate_assess'),(ExternalContextSource,'_items','external_items'),
            (ExternalCapabilityService,'absorbed','absorbed'),(ExternalCapabilityService,'cached','cached'),(ExternalCapabilityService,'_verified','verified'),
            (ExternalAbsorptionService,'current','current'),(ExternalAbsorptionService,'_proof','proof'),
            (jm.json,'loads','json_loads')):wrap(obj,name,label)
        wrap(jm.JsonIntegrationResultLedger,'_validate_operation_set','operation_full_validation',True)
        origread=pathlib.Path.read_bytes
        def read(p):
            if active[0] is None:return origread(p)
            t=time.perf_counter_ns()
            try:
                value=origread(p)
                if p.name in ('operation-journal.first-round-v1.json','capability-ledger.v1.json'):
                    active[0]['bytes'][p.name]+=len(value)
                return value
            finally:
                end=time.perf_counter_ns();m=active[0]['metrics']['read:'+p.name];m[0]+=1;m[1]+=end-t
        stack.enter_context(patch.object(pathlib.Path,'read_bytes',read))
        original=rm.AssociativeRecallService._prepare
        def prepare(self,*a,**kw):
            item=dict(test=current[0],metrics=defaultdict(lambda:[0,0]),bytes=defaultdict(int));records.append(item);active[0]=item;t=time.perf_counter_ns()
            ledgers=[]
            for binding in self.core.router._bindings:
                ledger=getattr(binding.source,'ledger',None)
                if ledger is not None and hasattr(ledger,'_operation_read_scope'):ledgers.append(ledger)
            item['operation_scopes']=[x._operation_read_scope.get() is not None for x in ledgers]
            try:
                value=original(self,*a,**kw);item['result']='RETURNED';return value
            except BaseException as exc:
                item['error_type']=type(exc).__name__;raise
            finally:
                item['total_ms']=(time.perf_counter_ns()-t)/1e6;active[0]=None
                item['metrics']={k:dict(count=v[0],ms=v[1]/1e6) for k,v in item['metrics'].items()}
        stack.enter_context(patch.object(rm.AssociativeRecallService,'_prepare',prepare))
        class Result(unittest.TextTestResult):
            def startTest(self,test):current[0]=test.id();super().startTest(test)
        runner=unittest.TextTestRunner(verbosity=2,resultclass=Result)
        result=runner.run(unittest.defaultTestLoader.loadTestsFromNames(TESTS))
    dest.write_text(json.dumps(dict(instrumented=True,records=records,bookkeeping_ms=overhead[0]/1e6,wrapper_calls=overhead[1],note='nested times not additive; overhead excludes timer and call-dispatch cost'),indent=2)+'\n',encoding='utf8')
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
