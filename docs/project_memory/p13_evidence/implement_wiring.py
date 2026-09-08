"""One-time, exact internal P13 integration edits; no frozen interface changes."""
from pathlib import Path
root=Path(__file__).resolve().parents[3]
def edit(path,changes):
    p=root/path;t=p.read_text(encoding='utf-8')
    for before,after,count in changes:
        assert t.count(before)==count,(path,before,t.count(before))
        t=t.replace(before,after)
    p.write_text(t,encoding='utf-8')

edit('src/continuity_engine/domain/thinking.py',[
 ('    request_more_thinking: bool = False\n','    request_more_thinking: bool = False\n    expression_mode: str | None = None\n',1),
 ('        _require_text(self.result_id, "thinking result_id")','        if self.expression_mode is not None:\n            from .expression import ExpressionMode\n            if self.expression_mode not in {mode.value for mode in ExpressionMode}:\n                raise ThinkingValidationError("unsupported formed expression mode")\n        _require_text(self.result_id, "thinking result_id")',1),
 ('        request_more_thinking: bool = False,\n','        request_more_thinking: bool = False,\n        expression_mode: str | None = None,\n',1),
 ('            request_more_thinking=request_more_thinking,\n','            request_more_thinking=request_more_thinking,\n            expression_mode=expression_mode,\n',1),
 ('            "request_more_thinking": self.request_more_thinking,\n','            "request_more_thinking": self.request_more_thinking,\n            **({"expression_mode": self.expression_mode} if self.expression_mode is not None else {}),\n',1),
 ('            request_more_thinking=value.get("request_more_thinking", False),\n','            request_more_thinking=value.get("request_more_thinking", False),\n            expression_mode=value.get("expression_mode"),\n',1)])
edit('src/continuity_engine/domain/continuity_core.py',[
 ('    version: str = "c1-context-v1"\n','    version: str = "c1-context-v1"\n    expression_enabled: bool = False\n',1),
 ('        if (self.version != "c1-context-v1" or type(self.actions_enabled) is not bool','        if (type(self.expression_enabled) is not bool or self.version != "c1-context-v1" or type(self.actions_enabled) is not bool',1),
 ('                "pending_event_count": self.pending_event_count}','                "pending_event_count": self.pending_event_count,\n                **({"expression_enabled": True} if self.expression_enabled else {})}',1),
 ('        if not isinstance(value, dict) or set(value) != {','        if not isinstance(value, dict) or set(value)-{"expression_enabled"} != {',1),
 ('value["pending_event_count"], value["version"])','value["pending_event_count"], value["version"], value.get("expression_enabled",False))',1)])
edit('src/continuity_engine/services/continuity_core_service.py',[
 ('context_ttl=timedelta(minutes=10), planner=None, limits=None, fault=None):','context_ttl=timedelta(minutes=10), planner=None, limits=None, fault=None, expression_policy=None):',1),
 ('        self.last_trace = None','        self.expression_policy = expression_policy\n        self.last_trace = None',1),
 ('emotion, self.gates.actions, pending_events)','emotion, self.gates.actions, pending_events,\n                                        expression_enabled=self.expression_policy is not None)',1)])

p=root/'src/continuity_engine/domain/integration_results.py';t=p.read_text(encoding='utf-8')
t=t.replace('from .perception import PerceptionResult','from .perception import PerceptionResult\nfrom .expression import ExpressionArtifact',1)
start=t.index('class IntegrationDomainCheckpoint:');end=t.index('class IntegrationEvolutionCheckpoint:')
chunk=t[start:end]
chunk=chunk.replace('    approved_state_action: ApprovedStateAction | None\n','    approved_state_action: ApprovedStateAction | None\n    expression: ExpressionArtifact | None = None\n',1)
chunk=chunk.replace('        for value, name in (','        if self.expression is not None:\n            if not isinstance(self.expression, ExpressionArtifact) or self.expression.content != self.response_content:\n                raise MachineContractValidationError("expression must match checkpoint response")\n        for value, name in (',1)
chunk=chunk.replace('            "responseId": self.response_id,','            **({"expression": self.expression.to_dict()} if self.expression is not None else {}),\n            "responseId": self.response_id,',1)
chunk=chunk.replace('        data = _object(\n            value,','        data = _object(\n            {k:v for k,v in value.items() if k != "expression"} if isinstance(value,dict) else value,',1)
chunk=chunk.replace('        return cls(\n            response_id=','        return cls(\n            expression=ExpressionArtifact.from_dict(value["expression"]) if "expression" in value else None,\n            response_id=',1)
t=t[:start]+chunk+t[end:];p.write_text(t,encoding='utf-8')

edit('src/continuity_engine/services/continuity_interaction_service.py',[
 ('        response_content = self._reply_composer.compose(thinking, action)','        expression = None\n        if perception.continuity_context is not None and perception.continuity_context.expression_enabled:\n            policy = self._continuity_core.expression_policy\n            if policy is None:\n                raise CapabilityValidationError("P13_PENDING_FEATURE_DISABLED")\n            expression = policy.compose(self._continuity_core, operation, thinking, action)\n            response_content = expression.content\n        else:\n            response_content = self._reply_composer.compose(thinking, action)',1),
 ('            approved_state_action=approved,\n','            approved_state_action=approved,\n            expression=expression,\n',1),
 ('    def _verify_core_completed(self, operation, completed=None):','    def _verify_core_completed(self, operation, completed=None, *, expression_current=True):',1),
 ('            self._verify_core_evolution(operation, thinking, completed)\n','            self._verify_core_evolution(operation, thinking, completed)\n            context = progress.perception.continuity_context\n            if context.expression_enabled:\n                if core.expression_policy is None:\n                    raise CapabilityValidationError("P13_PENDING_FEATURE_DISABLED")\n                core.expression_policy.verify(core,operation,thinking,progress.action,current=expression_current)\n            elif operation.domain.expression is not None:\n                raise CapabilityValidationError("P13_ARTIFACT_WITHOUT_ORIGINAL_CONTEXT")\n',1),
 ('        self._verify_core_completed(operation)\n','        self._verify_core_completed(operation, expression_current=False)\n        expression_consumable = True\n        if operation.domain.expression is not None:\n            expression_consumable = self._continuity_core.current(\n                operation.domain_progress.perception.continuity_context)\n            if expression_consumable:\n                self._continuity_core.expression_policy.verify(self._continuity_core,operation,thinking,\n                    operation.domain_progress.action,current=True)\n',1),
 ('        self._record("completed")\n        return result','        self._record("completed")\n        if not expression_consumable:\n            from ..domain.expression import ExpressionValidationError\n            raise ExpressionValidationError("EXPRESSION_CONTEXT_STALE_OR_UNAUTHORIZED_FACTS_RECOVERED")\n        return result',1)])
edit('src/continuity_engine/services/expression_policy_service.py',[
 ('state.relationship_state.interaction_preferences','state.relationship.interaction_preferences',1)])
print('P13 internal wiring applied; legacy serialized fields omitted when disabled.')
