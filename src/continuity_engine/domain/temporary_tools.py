"""W04-3 internal commands. Discovery is evidence, never permission or state authority."""
from dataclasses import asdict, dataclass
from .action_planning import digest, exact, identifier, hash_value
from .capability import parse_capability_datetime
from .environment_access import Attachment, AttachmentKind, DiscoveryState
from .execution import ExecutionError


@dataclass(frozen=True)
class ToolOffer:
    tool_id: str
    version: str
    purpose: str
    route: str
    dependencies: tuple[str, ...]
    attachment: Attachment

    def __post_init__(self):
        for x in (self.tool_id, self.version, self.purpose): identifier(x)
        if self.route not in {'API', 'UI'} or not isinstance(self.dependencies, tuple):
            raise ExecutionError('TOOL_OFFER_INVALID')
        for x in self.dependencies: identifier(x)
        if (len(set(self.dependencies)) != len(self.dependencies) or len(self.dependencies)>16
                or not isinstance(self.attachment, Attachment)
                or self.attachment.kind is not AttachmentKind.TOOL_EGRESS
                or self.attachment.state is not DiscoveryState.DISCOVERED):
            raise ExecutionError('TOOL_OFFER_INVALID')

    def to_dict(self):
        return {**asdict(self), 'dependencies': list(self.dependencies), 'attachment': self.attachment.to_dict()}

    @classmethod
    def from_dict(cls, value):
        d=exact(value,set(cls.__dataclass_fields__))
        if not isinstance(d['dependencies'],list): raise ExecutionError('TOOL_OFFER_INVALID')
        return cls(**{**d,'dependencies':tuple(d['dependencies']), 'attachment':Attachment.from_dict(d['attachment'])})


@dataclass(frozen=True)
class ToolLease:
    discovery_request_id: str
    source_id: str
    offer_hash: str
    purpose: str
    scope: str
    credential_ref: str
    mode: str
    expires_at: str
    test_budget: int
    grant_ref: str

    def __post_init__(self):
        for x in (self.discovery_request_id,self.source_id,self.purpose,self.scope,self.credential_ref,self.grant_ref): identifier(x)
        if not self.credential_ref.startswith('credential:'): raise ExecutionError('TOOL_CREDENTIAL_REFERENCE_REQUIRED')
        hash_value(self.offer_hash);parse_capability_datetime(self.expires_at)
        if self.mode not in {'SINGLE','TIMED','PERSISTENT'} or type(self.test_budget) is not int or not 0<=self.test_budget<=100:
            raise ExecutionError('TOOL_LEASE_INVALID')

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,value): return cls(**exact(value,set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class ToolCommand:
    operation: str
    lease: ToolLease
    connection_request_id: str | None = None
    reason: str = 'TASK'

    def __post_init__(self):
        if self.operation not in {'connect','verify','close'} or not isinstance(self.lease,ToolLease):
            raise ExecutionError('TOOL_COMMAND_INVALID')
        if (self.operation=='connect') != (self.connection_request_id is None):
            raise ExecutionError('TOOL_CONNECTION_REFERENCE_REQUIRED')
        if self.connection_request_id is not None: identifier(self.connection_request_id)
        if self.reason not in {'TASK','COMPLETE','CANCEL','EXPIRE','REVOKE','RETRY_CLEANUP'}:
            raise ExecutionError('TOOL_COMMAND_REASON')
        if self.operation!='close' and self.reason!='TASK': raise ExecutionError('TOOL_COMMAND_REASON')

    @property
    def capability(self): return 'tool.'+self.operation
    @property
    def hash(self): return digest(self.to_dict())
    def to_dict(self): return {**asdict(self),'lease':self.lease.to_dict()}
    @classmethod
    def from_dict(cls,value):
        d=exact(value,set(cls.__dataclass_fields__))
        return cls(**{**d,'lease':ToolLease.from_dict(d['lease'])})
