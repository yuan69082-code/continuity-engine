"""P13 Golden on the normal Engine C1 submit path, in an isolated TEST root."""
from dataclasses import replace
from pathlib import Path

from continuity_engine.services.expression_policy_service import ExpressionPolicyService
from continuity_engine.services.expression_ports import DeterministicPresentation
from .p08_action_fixture import _validate_fixture_root
from .p09_core_fixture import P09Fixture


class FakePresentation(DeterministicPresentation):
    def __init__(self):
        self.calls=0
        self.behavior='success'
        self.on_present=None

    def present(self,decision,body):
        self.calls+=1
        if self.on_present is not None:
            self.on_present()
        if self.behavior=='failure':
            raise RuntimeError('synthetic presentation failure')
        candidate=super().present(decision,body)
        if self.behavior=='reverse':
            return replace(candidate,body='I agree with this claim.')
        if self.behavior=='mode':
            return replace(candidate,mode='RESPOND' if candidate.mode!='RESPOND' else 'REFUSE')
        if self.behavior=='binding':
            return replace(candidate,decision_hash='sha256:'+'0'*64)
        return candidate


class P13Fixture(P09Fixture):
    def __init__(self,root:Path,*,expression_mode='RESPOND',body='I do not agree with this claim.',
                 presentation=None,expression_enabled=True,**options):
        _validate_fixture_root(root)  # Before P01 genesis, directories or any writes.
        self.expression_mode=expression_mode
        self.body=body
        self.presentation=presentation or FakePresentation()
        self.expression_enabled=expression_enabled
        self._expression_confirmed_operations=set()
        super().__init__(root,expression_policy=(ExpressionPolicyService(self.presentation)
                         if expression_enabled else None),**options)

    def reopen(self):
        app=super().reopen()
        if self.expression_enabled:
            original_choose=self.core.policy.choose
            def choose(operation,context,thinking,action):
                # Explicit TEST consent for this exact expression view, once.
                # Clearing/withdrawing confirmation must survive later replay.
                if operation.operation_id not in self._expression_confirmed_operations:
                    request=self.core.expression_policy.authorization_request(self.core,operation,context,thinking,action)
                    self.constraints.confirmed_ids.add(request.idempotency_key)
                    self._expression_confirmed_operations.add(operation.operation_id)
                return original_choose(operation,context,thinking,action)
            self.core.policy.choose=choose
        original=self.provider.think
        def think(perception,budget):
            result=original(perception,budget)
            return replace(result,result_summary=self.body,
                expression_mode=self.expression_mode if self.expression_enabled else None,
                should_wait=self.expression_mode=='SILENCE')
        self.provider.think=think
        return app

    def artifact(self,request):
        return self.app.ledger.load_operation(request['requestId']).domain.expression

    @property
    def state(self):
        return self.runtime.subject_states.load(self.runtime.descriptor.subject_id)


def main():
    import argparse,json,tempfile
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,help='Independent TEST root; protected overlaps are rejected before writes.')
    args=parser.parse_args()
    def run(root):
        records=[]
        for mode in ('RESPOND','SILENCE','REFUSE','QUESTION','CONFRONT','DEFER','PURSUE'):
            # P01 creates independent sandbox identities itself. Avoid adding
            # an unnecessary mode directory to Windows' already deep paths.
            f=P13Fixture(root,expression_mode=mode)
            request=f.request();result=f.submit(request);artifact=f.artifact(request)
            before=(f.adapter.effect_count,f.adapter.credits)
            f.reopen();replayed=f.submit(request)
            assert replayed.to_dict()==result.to_dict()
            assert before==(f.adapter.effect_count,f.adapter.credits)
            records.append({'mode':mode,'status':artifact.decision.status,
                'content':artifact.content,'revision':f.state.revision,
                'sameReplay':True,'externalDeliveryClaimed':False})
        print(json.dumps({'fixture':'p13-expression-golden-v1','scenarios':records},ensure_ascii=False,indent=2))
    if args.root is not None:
        _validate_fixture_root(args.root);run(args.root)
    else:
        with tempfile.TemporaryDirectory(prefix='p13-golden-') as temp:
            run(Path(temp))


if __name__=='__main__':
    main()
