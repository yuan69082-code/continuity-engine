"""Two real receipted queries, then one read of each; no randomized retry."""
import json,pathlib,sys,unittest
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import patch
from continuity_engine.domain.integration_results import format_contract_datetime as fmt
from continuity_engine.services.context_composer_service import ContextComposerService
from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
from tests.test_w04_2_simulation import W04SimulatedChainTests
records=[];compositions=[];current=[''];reads=[0]
oldcompose=ContextComposerService.compose;oldsafe=JsonExternalProviderRepository._safe
def compose(self,route,*a,**kw):
    result=oldcompose(self,route,*a,**kw)
    if route.plan.request.request_id.startswith('device-history:'):
        compositions.append(dict(target=current[0],status=result.status.value,budget=result.trace.budget.to_dict(),
            decisions=[d.to_dict() for d in result.trace.decisions],
            retained=[] if result.snapshot is None else [f.stable_source_id for f in result.snapshot.fragments]))
    return result
def safe(p):reads[0]+=1;return oldsafe(p)
case=W04SimulatedChainTests('test_same_root_history_requery_does_not_create_independent_evidence')
try:
    case.setUp();f=case.f;now=f.runtime.clock.now()
    row=dict(source_id='source:one',root_id='root:one',version='v1',readable=True,
        software_id='software:a',device_id='device:a',session_id='session:a',object_id='object:continuity',
        occurred_at=fmt(now),expires_at=fmt(now+timedelta(hours=1)),content='continuity same root')
    f.fake.change(history=[row])
    requests=[case.run_action('query',history=asdict(f.scope(query_id='query:'+str(i))))[0] for i in range(2)]
    perception=f.app.ledger.load_operation(f.last_request['requestId']).domain_progress.perception
    before=dict(revision=f.state.revision,effects=f.fake.effect_count,credits=f.fake.credits)
    with patch.object(ContextComposerService,'compose',compose),patch.object(JsonExternalProviderRepository,'_safe',staticmethod(safe)):
        for r in requests:
            current[0]=r.capability_request_id
            try:
                context=f.device.history_context(r.capability_request_id,perception)
                records.append(dict(request=r.capability_request_id,status='RETURNED',roots=sorted({root for x in context.snapshot.fragments if x.source_type=='execution_result' for root in x.provenance_roots})))
            except Exception as exc:
                records.append(dict(request=r.capability_request_id,status='REJECTED',error_type=type(exc).__name__,static_code='DEVICE_HISTORY_CONTEXT_NOT_READY' if str(exc)=='DEVICE_HISTORY_CONTEXT_NOT_READY' else 'OTHER_ERROR'))
    after=dict(revision=f.state.revision,effects=f.fake.effect_count,credits=f.fake.credits)
    report=dict(before=before,after=after,external_registry_reads=reads[0],records=records,compositions=compositions,
        evidence_kind='controlled two current reads; unchanged 2048 budget; original authority and records')
    with (pathlib.Path(__file__).parent/(sys.argv[1]+'.trace.json')).open('x',encoding='utf8') as out:json.dump(report,out,indent=2)
    print(json.dumps(report))
finally:case.doCleanups()
sys.exit(0 if all(r['status']=='RETURNED' for r in records) else 1)
