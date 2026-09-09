"""Internal P17 world policy. No execution facts or Subject authority here."""
from dataclasses import asdict, dataclass
from enum import Enum

from .action_planning import digest, exact, identifier
from .errors import CapabilityValidationError


class ExecutionError(CapabilityValidationError):
    """Only static, non-secret diagnostics cross the execution boundary."""


class World(str, Enum):
    TEST = 'TEST'
    RESEARCH = 'RESEARCH'
    REAL = 'REAL'


class Outcome(str, Enum):
    SUBJECT_REFUSAL = 'SUBJECT_REFUSAL'
    PLATFORM_DENIAL = 'PLATFORM_DENIAL'
    REALITY_DENIAL = 'REALITY_DENIAL'
    CAPABILITY_UNAVAILABLE = 'CAPABILITY_UNAVAILABLE'
    RESOURCE_EXHAUSTED = 'RESOURCE_EXHAUSTED'
    RESEARCH_UNAVAILABLE = 'RESEARCH_UNAVAILABLE'
    GENERATION_FAILED = 'GENERATION_FAILED'
    NETWORK_FAILED = 'NETWORK_FAILED'
    RECOVERABILITY_NOT_READY = 'RECOVERABILITY_NOT_READY'
    UNKNOWN = 'UNKNOWN'
    CANCELLED = 'CANCELLED'
    COMPLETED = 'COMPLETED'


@dataclass(frozen=True)
class WorldCapability:
    capability_ref: str
    version: str
    subject_id: str
    environment: str
    world: str
    asset: str
    adapter_id: str
    credential_ref: str
    permission: str = 'test:execute'
    cost: int = 1
    max_attempts: int = 2
    max_output_bytes: int = 4096
    compensation: bool = False

    def __post_init__(self):
        for name in ('capability_ref','version','subject_id','asset','adapter_id','credential_ref','permission'):
            identifier(getattr(self, name))
        if self.environment not in ('TEST','RESEARCH') or self.world not in {w.value for w in World}:
            raise ExecutionError('EXECUTION_WORLD_INVALID')
        if self.capability_ref == 'model.generate':
            raise ExecutionError('MODEL_GENERATE_REMAINS_THINKING')
        if (type(self.cost) is not int or not 0 <= self.cost <= 100
                or type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 3
                or type(self.max_output_bytes) is not int or not 1 <= self.max_output_bytes <= 65536
                or type(self.compensation) is not bool):
            raise ExecutionError('EXECUTION_LIMIT_INVALID')

    def to_dict(self):
        return asdict(self)

    @property
    def hash(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        return cls(**exact(value, set(cls.__dataclass_fields__)))


@dataclass(frozen=True)
class BlastRadius:
    requests: int = 16
    concurrent: int = 1
    credits: int = 16
    messages: int = 16
    storage_bytes: int = 65536

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise ExecutionError('EXECUTION_LIMIT_INVALID')


DELIVERY_STATES = {'PENDING','DISPATCHING','UNKNOWN','DELIVERED','CANCELLED'}
ROUTES = {'WAIT','REQUEST_INFORMATION','ABANDON','RETRY','CHANGE_ROUTE'}
