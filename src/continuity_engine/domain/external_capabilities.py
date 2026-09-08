"""P16 internal query/registration/candidate data, never external v1 contracts."""
from dataclasses import asdict,dataclass
import math
from .action_planning import digest,identifier,exact,hash_value
from .capability import parse_capability_datetime
from .errors import CapabilityValidationError


class ExternalCapabilityError(CapabilityValidationError):
    """Static reason codes only: never embed a provider's error or secret."""


KINDS=('memory','knowledge','mcp','skill')


@dataclass(frozen=True)
class QueryInput:
    kind: str
    query: str
    limit: int=4

    def __post_init__(self):
        if (self.kind not in KINDS or not isinstance(self.query,str) or not 1<=len(self.query)<=256
                or any(ord(c)<32 for c in self.query) or type(self.limit) is not int or not 1<=self.limit<=16):
            raise ExternalCapabilityError('EXTERNAL_QUERY_INVALID')
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,value):return cls(**exact(value,set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class ProviderDescriptor:
    connector_id: str
    version: str
    capability_ref: str
    kind: str
    credential_ref: str
    subject_id: str
    environment: str
    permission: str
    expires_at: str
    description: str
    cache_seconds: int=300
    max_results: int=8
    max_attempts: int=2

    def __post_init__(self):
        for value in (self.connector_id,self.version,self.capability_ref,self.credential_ref,self.subject_id,self.permission):identifier(value)
        if self.kind not in KINDS or self.environment not in ('TEST','RESEARCH'):
            raise ExternalCapabilityError('EXTERNAL_DESCRIPTOR_BOUNDARY')
        if self.capability_ref=='model.generate' or not self.capability_ref.startswith('external.'):
            raise ExternalCapabilityError('EXTERNAL_QUERY_ONLY')
        parse_capability_datetime(self.expires_at)
        if not isinstance(self.description,str) or not 1<=len(self.description)<=256:
            raise ExternalCapabilityError('EXTERNAL_DESCRIPTION_INVALID')
        for value,upper in ((self.cache_seconds,3600),(self.max_results,16),(self.max_attempts,3)):
            if type(value) is not int or not 1<=value<=upper:raise ExternalCapabilityError('EXTERNAL_LIMIT_INVALID')
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,v):return cls(**exact(v,set(cls.__dataclass_fields__)))
    @property
    def key(self):return self.connector_id+':'+self.version
    @property
    def adapter_id(self):return 'p16-adapter:'+digest([self.connector_id,self.version])[7:]


@dataclass(frozen=True)
class ExternalCandidate:
    source_id: str
    source_version: str
    content: str
    content_hash: str
    observed_at: str
    expires_at: str
    confidence: float
    roots: tuple[str,...]
    uncertainty: str='UNVERIFIED_EXTERNAL'

    def __post_init__(self):
        identifier(self.source_id);identifier(self.source_version);hash_value(self.content_hash)
        if (not isinstance(self.content,str) or not 1<=len(self.content)<=2048 or digest(self.content)!=self.content_hash
                or type(self.confidence) not in (int,float) or not math.isfinite(self.confidence) or not 0<=self.confidence<=1
                or self.uncertainty not in ('UNVERIFIED_EXTERNAL','DISPUTED_EXTERNAL')):
            raise ExternalCapabilityError('EXTERNAL_CANDIDATE_INVALID')
        if parse_capability_datetime(self.expires_at)<=parse_capability_datetime(self.observed_at):
            raise ExternalCapabilityError('EXTERNAL_CANDIDATE_TIME')
        if not isinstance(self.roots,tuple) or not 1<=len(self.roots)<=8 or len(set(self.roots))!=len(self.roots):
            raise ExternalCapabilityError('EXTERNAL_ROOTS_INVALID')
        for root in self.roots:
            identifier(root)
            if not root.startswith('external:'):raise ExternalCapabilityError('EXTERNAL_ROOT_NAMESPACE')
    def to_dict(self):return {**asdict(self),'roots':list(self.roots)}
    @classmethod
    def from_dict(cls,v):
        d=exact(v,set(cls.__dataclass_fields__))
        if not isinstance(d['roots'],list):raise ExternalCapabilityError('EXTERNAL_ROOTS_INVALID')
        return cls(**{**d,'roots':tuple(d['roots'])})


@dataclass(frozen=True)
class ProviderResult:
    connector_id: str
    descriptor_hash: str
    subject_id: str
    environment: str
    capability_request_id: str
    request_hash: str
    status: str
    candidates: tuple[ExternalCandidate,...]

    def __post_init__(self):
        for x in (self.connector_id,self.subject_id,self.capability_request_id):identifier(x)
        for x in (self.descriptor_hash,self.request_hash):hash_value(x)
        if self.environment not in ('TEST','RESEARCH') or self.status not in ('AVAILABLE','EMPTY','OFFLINE','TIMEOUT','CANCELLED'):
            raise ExternalCapabilityError('EXTERNAL_RESULT_INVALID')
        if not isinstance(self.candidates,tuple) or len(self.candidates)>16 or any(not isinstance(x,ExternalCandidate) for x in self.candidates):
            raise ExternalCapabilityError('EXTERNAL_RESULT_INVALID')
        if (self.status=='AVAILABLE')!=bool(self.candidates):raise ExternalCapabilityError('EXTERNAL_RESULT_STATUS')
        if len({x.source_id for x in self.candidates})!=len(self.candidates):raise ExternalCapabilityError('EXTERNAL_DUPLICATE_SOURCE')
    def to_dict(self):return {**asdict(self),'candidates':[x.to_dict() for x in self.candidates]}
    @classmethod
    def from_dict(cls,v):
        d=exact(v,set(cls.__dataclass_fields__))
        if not isinstance(d['candidates'],list):raise ExternalCapabilityError('EXTERNAL_RESULT_INVALID')
        return cls(**{**d,'candidates':tuple(ExternalCandidate.from_dict(x) for x in d['candidates'])})
    def validate_request(self,request,descriptor):
        if (self.connector_id,self.subject_id,self.environment,self.capability_request_id,self.request_hash,self.descriptor_hash)!=(
                descriptor.connector_id,request.subject_id,request.choice.environment,request.capability_request_id,request.request_hash,digest(descriptor.to_dict())):
            raise ExternalCapabilityError('EXTERNAL_RESULT_BINDING')
        if len(self.candidates)>min(descriptor.max_results,QueryInput.from_dict(request.step.input_payload).limit):
            raise ExternalCapabilityError('EXTERNAL_RESULT_BOUND_EXCEEDED')
