"""Internal lifecycle values; SubjectState and original Event history own state."""
from dataclasses import dataclass
from datetime import datetime

from .dynamic_mind import utc, timestamp, text


class LifecycleError(ValueError):
    pass


STATES = {'CREATE', 'ACTIVE', 'SUSPENDED', 'ARCHIVED', 'DELETED'}
TRANSITIONS = {
    ('CREATE', 'ACTIVATE'): 'ACTIVE',
    ('ACTIVE', 'SUSPEND'): 'SUSPENDED',
    ('SUSPENDED', 'RESUME'): 'ACTIVE',
    ('ACTIVE', 'ARCHIVE'): 'ARCHIVED',
    ('SUSPENDED', 'ARCHIVE'): 'ARCHIVED',
    ('ARCHIVED', 'RESUME'): 'ACTIVE',
    ('CREATE', 'DELETE'): 'DELETED',
    ('SUSPENDED', 'DELETE'): 'DELETED',
    ('ARCHIVED', 'DELETE'): 'DELETED',
}


def transition(status, operation):
    try:
        return TRANSITIONS[status, operation]
    except KeyError as exc:
        raise LifecycleError('SUBJECT_LIFECYCLE_TRANSITION_DENIED') from exc


def lifecycle_status(state):
    value = getattr(state.temporal, 'subject_lifecycle', None)
    return 'ACTIVE' if value is None else SubjectLifecycle.from_dict(value).status


@dataclass(frozen=True)
class LifecyclePolicy:
    # No production archive or retention decision is implied by construction.
    archive_configured: bool = False
    delete_retention_seconds: int | None = None
    allow_test_logical_delete: bool = False

    def __post_init__(self):
        if (type(self.archive_configured) is not bool or type(self.allow_test_logical_delete) is not bool
                or self.delete_retention_seconds is not None and (
                    type(self.delete_retention_seconds) is not int or self.delete_retention_seconds < 0)):
            raise LifecycleError('SUBJECT_POLICY_INVALID')


@dataclass(frozen=True)
class LifecycleCommand:
    command_id: str
    subject_id: str
    environment: str
    expected_revision: int
    requested_at: datetime
    reason: str
    operation: str
    initiator: str

    def __post_init__(self):
        for value in (self.command_id, self.subject_id, self.reason): text(value)
        object.__setattr__(self, 'requested_at', utc(self.requested_at))
        if self.environment not in {'TEST', 'RESEARCH'}:
            raise LifecycleError('SUBJECT_ENVIRONMENT_INVALID')
        if type(self.expected_revision) is not int or self.expected_revision < 0:
            raise LifecycleError('SUBJECT_REVISION_INVALID')
        allowed = {'OWNER': {'CREATE', 'ACTIVATE', 'SUSPEND', 'RESUME', 'ARCHIVE', 'DELETE'},
                   'SUBJECT': {'SUSPEND_INTENT', 'ARCHIVE_INTENT'}}
        if self.operation not in allowed.get(self.initiator, set()):
            raise LifecycleError('SUBJECT_INITIATOR_OPERATION_INVALID')

    def to_dict(self):
        return {**self.__dict__, 'requested_at': timestamp(self.requested_at)}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise LifecycleError('SUBJECT_COMMAND_SHAPE_INVALID')
        return cls(**value)


@dataclass(frozen=True)
class SubjectLifecycle:
    subject_id: str
    environment: str
    owner_principal_id: str
    status: str
    changed_at: datetime
    reason: str
    version: str = 'p15-subject-lifecycle-v1'

    def __post_init__(self):
        for value in (self.subject_id, self.owner_principal_id, self.reason): text(value)
        object.__setattr__(self, 'changed_at', utc(self.changed_at))
        if (self.environment not in {'TEST', 'RESEARCH'} or self.status not in STATES
                or self.version != 'p15-subject-lifecycle-v1'):
            raise LifecycleError('SUBJECT_LIFECYCLE_VALUE_INVALID')

    def to_dict(self):
        return {**self.__dict__, 'changed_at': timestamp(self.changed_at)}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise LifecycleError('SUBJECT_LIFECYCLE_SHAPE_INVALID')
        return cls(**value)


@dataclass(frozen=True)
class TestMigrationCommand:
    command_id: str
    subject_id: str
    source_subject_id: str
    source_event_id: str
    source_hash: str
    source_revision: int
    expected_revision: int
    environment: str = 'TEST'
    data_type: str = 'PUBLIC_OBSERVATION'

    def __post_init__(self):
        for key in ('command_id','subject_id','source_subject_id','source_event_id','source_hash'):
            text(getattr(self,key))
        if (self.environment!='TEST' or self.data_type!='PUBLIC_OBSERVATION'
                or self.subject_id==self.source_subject_id or
                any(type(x) is not int or x<0 for x in (self.source_revision,self.expected_revision))):
            raise LifecycleError('SUBJECT_TEST_MIGRATION_INVALID')

    def to_dict(self):return dict(self.__dict__)
