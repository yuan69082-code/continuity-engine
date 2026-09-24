"""W02-B data/Fake only; all work uses the normal C1 entry and repositories."""
from dataclasses import replace
from .w02_input_fixture import W02InputFixture
from continuity_engine.services.continuity_core_service import ContinuityCoreGates


class W02RecallFixture(W02InputFixture):
    def __init__(self,root,*,gates=None,**options):
        super().__init__(root,gates=replace(gates or ContinuityCoreGates(),automatic_recall=True),**options)


def golden_phase(root,phase):
    """Explicit TEST controller. The show phase is a read-only stored view."""
    import json
    from pathlib import Path
    from .p08_action_fixture import _validate_fixture_root
    from .sandbox import P01SandboxManager
    from .persistence import tree_inventory_hash
    from continuity_engine.domain.errors import IntegrationExecutionError
    root=_validate_fixture_root(Path(root)); manifest=root/'w02-b-golden.json'
    if phase=='prepare':
        f=W02RecallFixture(root)
        f.event('old-meal',content='我吃过螺蛳粉。')
        r=f.message('我又在吃螺蛳粉。')
        def interrupted(stage,operation):
            if stage=='after_c1_action_completed':raise RuntimeError('W02_RECALL_EFFECT_RETURN_LOST')
        f.app.adapter.service._fault_injector=interrupted
        try:f.submit(r)
        except IntegrationExecutionError as exc:
            if str(exc.__cause__)!='W02_RECALL_EFFECT_RETURN_LOST':raise
        else:raise AssertionError('controlled interruption missing')
        saved={'sandbox':f.runtime.descriptor.sandbox_id,'request':r,'revision':f.runtime.subject_state().revision,
               'record':f.context(r).recall}
        manifest.write_text(json.dumps(saved,ensure_ascii=False),encoding='utf-8')
        assert (f.provider.calls,f.adapter.effect_count,f.adapter.credits)==(1,1,1)
        return {'phase':phase,'model_calls':1,'effects':1,'credits':1,'recall':saved['record']}
    saved=json.loads(manifest.read_text(encoding='utf-8'))
    manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    f=W02RecallFixture(root,manager=manager,runtime=manager.open_runtime(saved['sandbox']))
    before=tree_inventory_hash(f.runtime.data_root)
    if phase=='resume':f.submit(saved['request'])
    elif phase!='show':raise ValueError('unknown phase')
    view=f.app.adapter.service.recall_outcome(saved['request']['requestId'])
    assert view['record']==saved['record']
    assert (f.provider.calls,f.adapter.execute_calls,f.adapter.effect_count,f.adapter.credits)==(0,0,1,1)
    assert f.runtime.subject_state().revision==saved['revision']
    if phase=='show':assert tree_inventory_hash(f.runtime.data_root)==before
    return {'phase':phase,'model_calls':0,'new_effects':0,'total_effects':1,'credits':1,'view':view}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--phase',choices=('prepare','resume','show'),required=True)
    args=parser.parse_args()
    print(json.dumps(golden_phase(args.root,args.phase),ensure_ascii=False))
