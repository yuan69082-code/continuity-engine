"""P18 host lifecycle metadata, separate from Subject and work authorities."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math


class RuntimeBoundaryError(ValueError):
    """Only static diagnostic codes cross the runtime control boundary."""


class RuntimeDeferred(RuntimeBoundaryError):
    pass


STATES={'START','RUNNING','PAUSED','SUSPENDED','RESUME','RECOVER','STOP','ARCHIVED'}
ACTIVITIES={'IDLE','COGNITION','MAINTENANCE','WAITING_RESOURCES','WAITING_VERIFICATION','BACKOFF','PAUSED','STOPPED','CLOCK_WAIT'}


def utc(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset().total_seconds()!=0:
        raise RuntimeBoundaryError('RUNTIME_CLOCK_INVALID')
    return value.astimezone(timezone.utc)


def stamp(value):return utc(value).isoformat()
def parse(value):
    try:return utc(datetime.fromisoformat(value))
    except Exception:raise RuntimeBoundaryError('RUNTIME_CLOCK_INVALID') from None


@dataclass(frozen=True)
class RuntimePolicy:
    # Infrastructure pacing, never a product lifetime or permission to contact.
    idle_wait_seconds: float = 1.0
    minimum_spacing_seconds: float = 60.0
    retry_seconds: float = 5.0
    clock_jump_seconds: float = 3600.0
    need_delta: float = 0.02
    max_failures: int = 3

    def __post_init__(self):
        for key in ('idle_wait_seconds','minimum_spacing_seconds','retry_seconds','clock_jump_seconds','need_delta'):
            v=getattr(self,key)
            if type(v) not in (int,float) or not math.isfinite(v) or v<=0:
                raise RuntimeBoundaryError('RUNTIME_POLICY_INVALID')
        if self.idle_wait_seconds>5 or self.need_delta>1 or type(self.max_failures) is not int or not 1<=self.max_failures<=16:
            raise RuntimeBoundaryError('RUNTIME_POLICY_INVALID')


@dataclass(frozen=True)
class RuntimePrincipal:
    principal_id: str
    subject_id: str
    environment: str
    operations: frozenset[str]


@dataclass(frozen=True)
class RuntimeNeed:
    identity: str
    kind: str
    due_at: datetime
    priority: int

    def __post_init__(self):
        if self.kind not in {'cognition','maintenance'} or not isinstance(self.identity,str) or not self.identity:
            raise RuntimeBoundaryError('RUNTIME_NEED_INVALID')
        utc(self.due_at)


@dataclass(frozen=True)
class RuntimeDeliveryPolicy:
    """Delivery policy is explicit; absence never means unlimited contact."""
    configured: bool = False
    start_hour_utc: int = 0
    end_hour_utc: int = 24
    minimum_interval_seconds: int = 60

    def __post_init__(self):
        if (type(self.configured) is not bool or type(self.start_hour_utc) is not int
                or type(self.end_hour_utc) is not int or not 0<=self.start_hour_utc<self.end_hour_utc<=24
                or type(self.minimum_interval_seconds) is not int or self.minimum_interval_seconds<1):
            raise RuntimeBoundaryError('RUNTIME_DELIVERY_POLICY_INVALID')

    def allows(self,at,last_delivery):
        at=utc(at)
        return (self.configured and self.start_hour_utc<=at.hour<self.end_hour_utc
                and (last_delivery is None or (at-utc(last_delivery)).total_seconds()>=self.minimum_interval_seconds))
