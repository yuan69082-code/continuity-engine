"""Expression consumes completed Engine thinking; it never forms new cognition."""
import json
from continuity_engine.domain.action_planning import digest, ActionChoice, ActionSpecification
from continuity_engine.domain.action_capability import InternalActionRequest
from continuity_engine.domain.action import ActionIntent, ResourceLimits, RiskLevel
from continuity_engine.domain.context_composition import ContextAuthority
from continuity_engine.domain.models import EmotionState
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.domain.expression import (
    ExpressionDecision, ExpressionArtifact, ExpressionValidationError,
    ExpressionAccessError, ExpressionGenerationError, PresentationCandidate, render_body,
)
from .expression_ports import DeterministicPresentation


class ExpressionPolicyService:
    def __init__(self, presentation=None, *, maximum_characters=8192):
        if type(maximum_characters) is not int or not 1<=maximum_characters<=65536:
            raise ExpressionValidationError('EXPRESSION_LIMIT_INVALID')
        self.presentation=presentation or DeterministicPresentation()
        self.maximum_characters=maximum_characters
        self.last_trace=None

    @staticmethod
    def binding(operation,thinking,action,context):
        session=thinking.session
        if (session.result is None or not session.completed_successfully
                or session.perception_snapshot!=thinking.perception
                or thinking.perception!=operation.domain_progress.perception
                or thinking.perception.continuity_context!=context
                or thinking.perception.subject_id!=operation.subject_id
                or context.composition.snapshot.subject_id!=operation.subject_id
                or context.route.plan.request.request_id!=operation.request_id
                or context.composition.snapshot.source_revision!=operation.input_revision
                or session.subject_id!=operation.subject_id
                or session.think_id!=operation.domain_progress.think_session_id
                or session.result.result_id!=operation.domain_progress.thinking_result_id
                or operation.domain_progress.action is None
                or action.to_dict()!=operation.domain_progress.action.to_dict()
                or action.context.thinking_result.to_dict()!=session.result.to_dict()):
            raise ExpressionValidationError('EXPRESSION_ORIGINAL_INPUT_BINDING_INVALID')
        context.validate_perception(thinking.perception)
        return digest({'request':operation.request_id,'request_hash':operation.request_hash,
            'operation':operation.operation_id,'subject':operation.subject_id,
            'binding':operation.binding_id,'binding_version':operation.binding_version,
            'revision':operation.input_revision,'think_session':session.think_id,
            'thinking':session.result.to_dict(),'action':action.to_dict(),
            'context':context.binding_hash()})

    @staticmethod
    def mode(result):
        return result.expression_mode or ('SILENCE' if result.should_wait else 'RESPOND')

    @staticmethod
    def authorization_request(core,operation,context,thinking,action):
        """Exact confirmation view only; never registered, submitted or executed.

        Its identity binds the original operation, formed result and Action. The
        existing confirmation port owns approval; no receipt or old Action is
        itself a renewed approval of present consumption.
        """
        binding=next((b for b in core.capabilities if b.capability=='expression.emit'),None)
        if binding is None or binding.permission!='expression:emit':
            raise ExpressionAccessError('EXPRESSION_CAPABILITY_UNAVAILABLE')
        snapshot=context.composition.snapshot
        key=ExpressionPolicyService.binding(operation,thinking,action,context)
        choice=ActionChoice('expression-access:'+key[7:],'p13-expression-access-v1',
            operation.subject_id,snapshot.environment,snapshot.snapshot_hash,snapshot.source_revision,
            tuple(f.fragment_id for f in snapshot.fragments),'ACTION_INTENT',
            (ActionSpecification('expression','expression.emit','engine.local',key),),
            format_contract_datetime(snapshot.composed_at),
            format_contract_datetime(snapshot.composed_at+core.context_ttl))
        return InternalActionRequest(choice,'expression',None,binding.adapter.adapter_id,binding.canonical_hash())

    def _authorize(self,core,operation,thinking,action,context):
        request=self.authorization_request(core,operation,context,thinking,action)
        binding=next(b for b in core.capabilities if b.capability=='expression.emit')
        intent=ActionIntent(intent_id=request.operation_id,action_type=binding.action_type,
            source_thought='sealed-original-expression',reason='current-expression-access',
            target=request.step.target,expected_effect='local-presentation-only',confidence=1.0,
            risk_level=RiskLevel.LOW,required_permissions=[binding.permission],
            estimated_resource_cost=binding.cost,created_at=core.clock())
        # Assessment is read-only: no allocation, ActionSession, request or charge.
        decision=core.action_gate.assess_local_action(intent,subject_id=operation.subject_id,
            environment=context.composition.snapshot.environment,limits=core.limits or ResourceLimits(),
            confirmed=core.constraints.confirmed(request))
        if not decision.approved:
            raise ExpressionAccessError('EXPRESSION_CURRENT_'+decision.rejection_reason)
        if not core.constraints.recoverable(request) or not core.constraints.reality_allowed(request):
            raise ExpressionAccessError('EXPRESSION_CURRENT_BOUNDARY_DENIED')

    @staticmethod
    def _style_inputs(context,at):
        """Only the already authorized, exact Composer projection can style text."""
        inputs={};basis=[]
        for fragment in context.composition.snapshot.fragments:
            if fragment.authority is not ContextAuthority.CONFIRMED_STATE or fragment.source_id!='engine.subject-state':
                continue
            section=fragment.stable_source_id.rsplit(':',1)[-1]
            if section not in {'identity','relationship','emotion_state'}:
                continue
            if section in inputs or fragment.missing_markers or fragment.conflict_markers:
                raise ExpressionAccessError('EXPRESSION_STYLE_SOURCE_AMBIGUOUS')
            inputs[section]=json.loads(fragment.content)
            basis.append((fragment.reference_id,fragment.fragment_id,fragment.version,fragment.content_hash))
        prefs=inputs.get('identity',{}).get('expression_preferences',[])
        relationship=inputs.get('relationship',{}).get('interaction_preferences',[])
        emotion=inputs.get('emotion_state')
        intensity=(EmotionState.from_dict(emotion).effective_at(at)['intensity']
                   if emotion is not None and context.effective_emotion.get('status')!='FEATURE_GATED' else 0)
        reasons=tuple(section.upper()+'_CONTEXT_'+('USED' if section in inputs else 'ABSENT')
                      for section in ('identity','relationship','emotion_state'))
        return prefs,relationship,intensity,digest(basis),reasons

    def decide(self, core,operation,thinking,action,context):
        binding=self.binding(operation,thinking,action,context)
        if not context.expression_enabled or not core.enabled or core.expression_policy is not self:
            raise ExpressionValidationError('EXPRESSION_FEATURE_BINDING_INVALID')
        if not core.current(context):
            raise ExpressionAccessError('EXPRESSION_CONTEXT_STALE_OR_UNAUTHORIZED')
        result=thinking.session.result
        mode=self.mode(result)
        denied=not action.decision.approved or action.decision.requires_confirmation
        if not denied and mode!='SILENCE':
            self._authorize(core,operation,thinking,action,context)
        prefs,relationship,intensity,state_hash,source_reasons=self._style_inputs(context,thinking.perception.perceived_at)
        layout='quoted' if 'formal' in relationship else 'plain'
        compact='concise' in prefs
        emphasis=('emphasis' in prefs and isinstance(intensity,(int,float)) and intensity>=0.5)
        status='PLATFORM_DENIED' if denied else ('SUBJECT_SILENCE' if mode=='SILENCE' else 'SUBJECT_EXPRESSION')
        reasons=('FORMED_ENGINE_INTENT' if result.expression_mode else 'LEGACY_THINKING_FLAGS',
                 'CURRENT_CONTEXT',*source_reasons,
                 'ACTION_GATE_DENIED' if denied else ('NO_VISIBLE_EXPRESSION' if mode=='SILENCE' else 'CURRENT_ACTION_GATE_CHECKED'))
        return ExpressionDecision(mode,binding,digest(result.result_summary),state_hash,
            context.binding_hash(),layout,compact,emphasis,reasons,status)

    def compose(self,core,operation,thinking,action):
        context=thinking.perception.continuity_context
        decision=self.decide(core,operation,thinking,action,context)
        body=thinking.session.result.result_summary
        if decision.status=='SUBJECT_EXPRESSION':
            if len(body)>self.maximum_characters:
                raise ExpressionGenerationError('EXPRESSION_BUDGET_REQUIRES_NEW_UPSTREAM_DECISION')
            try:
                candidate=self.presentation.present(decision,body)
            except Exception as exc:
                # Do not put provider text or exception messages in the trace.
                raise ExpressionGenerationError('EXPRESSION_GENERATION_FAILED') from exc
            expected=PresentationCandidate(digest(decision.to_dict()),decision.mode,body,
                decision.layout,decision.compact,decision.emphasis)
            if type(candidate) is not PresentationCandidate or candidate!=expected:
                raise ExpressionGenerationError('EXPRESSION_GENERATOR_CHANGED_ENGINE_DECISION')
        # Recheck after the untrusted pure seam; prevent invalidation/mutable input races.
        if self.decide(core,operation,thinking,action,context)!=decision:
            raise ExpressionValidationError('EXPRESSION_INPUT_CHANGED_DURING_GENERATION')
        content=render_body(body,decision)
        if len(content)>self.maximum_characters:
            raise ExpressionGenerationError('EXPRESSION_PRESENTATION_BUDGET_EXCEEDED')
        self.last_trace=decision.trace()
        return ExpressionArtifact(decision,content,digest(content))

    def verify(self,core,operation,thinking,action,*,current):
        context=thinking.perception.continuity_context
        artifact=operation.domain.expression
        if not isinstance(artifact,ExpressionArtifact):
            raise ExpressionValidationError('EXPRESSION_COMPLETED_ARTIFACT_MISSING')
        decision=artifact.decision
        result=thinking.session.result
        denied=not action.decision.approved or action.decision.requires_confirmation
        expected_status='PLATFORM_DENIED' if denied else ('SUBJECT_SILENCE' if self.mode(result)=='SILENCE' else 'SUBJECT_EXPRESSION')
        if (decision.binding_hash!=self.binding(operation,thinking,action,context)
                or decision.context_hash!=context.binding_hash()
                or decision.mode!=self.mode(result)
                or decision.status!=expected_status
                or decision.content_hash!=digest(result.result_summary)
                or artifact.content!=render_body(result.result_summary,decision)
                or operation.domain.response_content!=artifact.content):
            raise ExpressionValidationError('EXPRESSION_COMPLETED_BINDING_MISMATCH')
        if current and decision!=self.decide(core,operation,thinking,action,context):
            raise ExpressionValidationError('EXPRESSION_CURRENT_DECISION_MISMATCH')
        self.last_trace=decision.trace()
        return artifact
