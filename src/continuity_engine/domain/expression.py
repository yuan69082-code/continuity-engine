"""Internal expression values; neither cognition nor an execution authority."""
from dataclasses import dataclass, asdict
from enum import Enum
import re

from .action_planning import digest


class ExpressionValidationError(ValueError):
    pass


class ExpressionAccessError(ExpressionValidationError):
    """Current consumption denied; independently verified facts remain facts."""


class ExpressionGenerationError(ExpressionValidationError):
    """Presentation failed; this is not a subject refusal or silence."""


class ExpressionMode(str, Enum):
    RESPOND = 'RESPOND'
    SILENCE = 'SILENCE'
    REFUSE = 'REFUSE'
    QUESTION = 'QUESTION'
    CONFRONT = 'CONFRONT'
    DEFER = 'DEFER'
    PURSUE = 'PURSUE'


def _hash(value):
    if not isinstance(value,str) or re.fullmatch(r'sha256:[0-9a-f]{64}',value) is None:
        raise ExpressionValidationError('EXPRESSION_HASH_INVALID')


@dataclass(frozen=True)
class ExpressionDecision:
    mode: str
    binding_hash: str
    content_hash: str
    state_hash: str
    context_hash: str
    layout: str
    compact: bool
    emphasis: bool
    reason_codes: tuple[str, ...]
    status: str = 'SUBJECT_EXPRESSION'
    version: str = 'p13-expression-v1'

    def __post_init__(self):
        if self.mode not in {m.value for m in ExpressionMode}:
            raise ExpressionValidationError('EXPRESSION_MODE_INVALID')
        for h in (self.binding_hash,self.content_hash,self.state_hash,self.context_hash):
            _hash(h)
        if (self.version!='p13-expression-v1' or self.layout not in {'plain','quoted'}
                or type(self.compact) is not bool or type(self.emphasis) is not bool
                or self.status not in {'SUBJECT_EXPRESSION','SUBJECT_SILENCE','PLATFORM_DENIED'}
                or (self.status=='SUBJECT_SILENCE' and self.mode!='SILENCE')
                or (self.mode=='SILENCE' and self.status=='SUBJECT_EXPRESSION')
                or not isinstance(self.reason_codes,tuple) or not self.reason_codes
                or any(not isinstance(x,str) or re.fullmatch('[A-Z_]+',x) is None for x in self.reason_codes)):
            raise ExpressionValidationError('EXPRESSION_DECISION_INVALID')

    def to_dict(self):
        return {**asdict(self),'reason_codes':list(self.reason_codes)}

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or set(value)!=set(cls.__dataclass_fields__):
            raise ExpressionValidationError('EXPRESSION_DECISION_SHAPE_INVALID')
        if not isinstance(value['reason_codes'],list):
            raise ExpressionValidationError('EXPRESSION_REASONS_INVALID')
        return cls(**{**value,'reason_codes':tuple(value['reason_codes'])})

    def trace(self):
        # No body, preference prose, rationale or hidden model reasoning.
        return self.to_dict()


@dataclass(frozen=True)
class PresentationCandidate:
    decision_hash: str
    mode: str
    body: str
    layout: str
    compact: bool
    emphasis: bool


def render_body(body, decision):
    """Only whitespace and formatting. Never drop a sentence or negate a stance."""
    if decision.status in {'SUBJECT_SILENCE','PLATFORM_DENIED'}:
        return ''
    if decision.compact:
        body='\n'.join(line for line in body.splitlines() if line.strip())
    if decision.layout=='quoted':
        body='\n'.join('> '+line for line in body.splitlines())
    if decision.emphasis:
        body='**'+body+'**'
    return body


@dataclass(frozen=True)
class ExpressionArtifact:
    decision: ExpressionDecision
    content: str
    content_hash: str

    def __post_init__(self):
        if not isinstance(self.decision,ExpressionDecision) or not isinstance(self.content,str):
            raise ExpressionValidationError('EXPRESSION_ARTIFACT_INVALID')
        if digest(self.content)!=self.content_hash:
            raise ExpressionValidationError('EXPRESSION_ARTIFACT_HASH_INVALID')
        if self.decision.status in {'SUBJECT_SILENCE','PLATFORM_DENIED'} and self.content:
            raise ExpressionValidationError('EXPRESSION_NONEMPTY_SILENCE_OR_DENIAL')

    def to_dict(self):
        return {'decision':self.decision.to_dict(),'content':self.content,'content_hash':self.content_hash}

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or set(value)!={'decision','content','content_hash'}:
            raise ExpressionValidationError('EXPRESSION_ARTIFACT_SHAPE_INVALID')
        return cls(ExpressionDecision.from_dict(value['decision']),value['content'],value['content_hash'])
