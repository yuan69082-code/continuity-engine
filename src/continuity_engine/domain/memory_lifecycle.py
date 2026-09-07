"""Internal P12 commands. No production retention policy or deletion credential."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
import re

from .errors import MemoryValidationError
from .memory import MemoryLifecycle, MemoryRecord, MemoryStatus, _canonical_hash, _utc, _format_datetime, _parse_datetime


class LifecycleAction(str, Enum):
    DEACTIVATE = 'deactivate'
    ARCHIVE = 'archive'
    RESTORE = 'restore'
    DELETE = 'delete'
    DOWNWEIGHT = 'downweight'
    DECAY = 'decay'


@dataclass(frozen=True)
class ForgettingPolicy:
    """Explicitly injected policy; no automatic scheduling, production defaults or purge."""
    policy_id: str
    half_life_seconds: float

    def __post_init__(self):
        if (not isinstance(self.policy_id, str) or not self.policy_id.strip()
                or isinstance(self.half_life_seconds, bool)
                or not isinstance(self.half_life_seconds, (float, int))
                or not math.isfinite(self.half_life_seconds) or self.half_life_seconds <= 0):
            raise MemoryValidationError('explicit finite positive decay policy required')

    def to_dict(self):
        return {'policy_id': self.policy_id, 'half_life_seconds': self.half_life_seconds}


@dataclass(frozen=True)
class MemoryLifecycleCommand:
    command_id: str
    subject_id: str
    environment: str
    memory_id: str
    action: LifecycleAction
    expected_revision: int
    expected_hash: str
    permission_id: str
    permission_revision: int
    scope: str
    reason: str
    issued_at: datetime
    expires_at: datetime
    confirmation_id: str
    source_hashes: tuple[tuple[str, str], ...]
    factor: float | None = None
    policy: ForgettingPolicy | None = None

    def __post_init__(self):
        for field in ('command_id','subject_id','memory_id','permission_id','scope','reason','confirmation_id'):
            if not isinstance(getattr(self,field), str) or not getattr(self,field).strip():
                raise MemoryValidationError(f'{field} must be non-empty')
        if self.environment not in ('ENGINE','TEST','RESEARCH'):
            raise MemoryValidationError('unsupported lifecycle environment')
        try:
            object.__setattr__(self, 'action', LifecycleAction(self.action))
        except (ValueError, TypeError) as exc:
            raise MemoryValidationError('unsupported lifecycle action') from exc
        for value in (self.expected_revision,self.permission_revision):
            if isinstance(value,bool) or not isinstance(value,int) or value < 0:
                raise MemoryValidationError('expected revisions must be non-negative integers')
        if not isinstance(self.expected_hash,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',self.expected_hash):
            raise MemoryValidationError('expected hash required')
        object.__setattr__(self,'issued_at',_utc(self.issued_at,'issued_at'))
        object.__setattr__(self,'expires_at',_utc(self.expires_at,'expires_at'))
        if self.expires_at <= self.issued_at:
            raise MemoryValidationError('command time interval invalid')
        if (not isinstance(self.source_hashes,tuple) or not self.source_hashes
                or any(not isinstance(p,tuple) or len(p)!=2 or not all(isinstance(x,str) and x for x in p) for p in self.source_hashes)
                or len({p[0] for p in self.source_hashes}) != len(self.source_hashes)):
            raise MemoryValidationError('complete distinct source hashes required')
        if self.action is LifecycleAction.DOWNWEIGHT:
            if isinstance(self.factor,bool) or not isinstance(self.factor,(int,float)) or not 0 <= self.factor < 1:
                raise MemoryValidationError('downweight factor must be finite and below one')
        elif self.factor is not None:
            raise MemoryValidationError('factor belongs only to downweight')
        if (self.action is LifecycleAction.DECAY) != isinstance(self.policy, ForgettingPolicy):
            raise MemoryValidationError('decay requires an explicit policy; other actions do not')

    def to_dict(self):
        return {k: (v.value if isinstance(v,Enum) else _format_datetime(v) if isinstance(v,datetime)
                    else v.to_dict() if isinstance(v,ForgettingPolicy) else [list(p) for p in v] if k=='source_hashes' else v)
                for k,v in ((f,getattr(self,f)) for f in self.__dataclass_fields__)}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data,dict) or set(data)!=set(cls.__dataclass_fields__):
            raise MemoryValidationError('invalid lifecycle command fields')
        values=dict(data)
        for field in ('issued_at','expires_at'):
            values[field]=_parse_datetime(values[field],field)
        values['source_hashes']=tuple(tuple(p) for p in values['source_hashes'])
        if values['policy'] is not None: values['policy']=ForgettingPolicy(**values['policy'])
        return cls(**values)

    def canonical_hash(self):
        return _canonical_hash(self.to_dict())


def lifecycle_result(memory: MemoryRecord, command: MemoryLifecycleCommand, now: datetime) -> MemoryRecord:
    """Pure deterministic transition; authorization belongs to the coordinating service."""
    now=_utc(now,'lifecycle time')
    if (memory.memory_id!=command.memory_id or memory.subject_id!=command.subject_id
            or memory.environment!=command.environment or memory.scope!=command.scope
            or memory.revision!=command.expected_revision or memory.canonical_hash()!=command.expected_hash):
        raise MemoryValidationError('memory command identity/version/hash/scope mismatch')
    state=memory.effective_lifecycle
    if memory.status is not MemoryStatus.ACTIVE or state is MemoryLifecycle.DELETED:
        raise MemoryValidationError('revoked, corrected or deleted memory cannot be restored or revised')
    action=command.action
    if action is LifecycleAction.RESTORE and state not in (MemoryLifecycle.INACTIVE,MemoryLifecycle.ARCHIVED):
        raise MemoryValidationError('restore requires inactive or archived memory')
    if action in (LifecycleAction.DOWNWEIGHT,LifecycleAction.DECAY) and state is not MemoryLifecycle.ACTIVE:
        raise MemoryValidationError('weight changes require an active lifecycle')
    if action is LifecycleAction.DEACTIVATE and state is not MemoryLifecycle.ACTIVE:
        raise MemoryValidationError('deactivate requires active lifecycle')
    if action is LifecycleAction.ARCHIVE and state not in (MemoryLifecycle.ACTIVE,MemoryLifecycle.INACTIVE):
        raise MemoryValidationError('archive requires active or inactive lifecycle')
    payload=memory.to_dict()
    payload.update(revision=memory.revision+1, memory_version=memory.memory_version+1,
                   lifecycle_command_id=command.command_id)
    if action in (LifecycleAction.DEACTIVATE,LifecycleAction.ARCHIVE,LifecycleAction.RESTORE,LifecycleAction.DELETE):
        payload['lifecycle']={LifecycleAction.DEACTIVATE:'inactive',LifecycleAction.ARCHIVE:'archived',
                              LifecycleAction.RESTORE:'active',LifecycleAction.DELETE:'deleted'}[action]
        if action is LifecycleAction.RESTORE:
            payload['retrieval_weight']=1.0
            payload['weight_updated_at']=_format_datetime(now)
    else:
        previous=memory.weight_updated_at or memory.consolidated_at
        if now < previous: raise MemoryValidationError('clock precedes previous weight update')
        factor=(command.factor if action is LifecycleAction.DOWNWEIGHT
                else 2 ** (-(now-previous).total_seconds()/command.policy.half_life_seconds))
        payload['retrieval_weight']=round(memory.effective_weight*factor,12)
        payload['weight_updated_at']=_format_datetime(now)
        payload['lifecycle']='active'
    return MemoryRecord.from_dict(payload)
