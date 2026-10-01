"""Internal W04 entry provenance. Neither a platform API nor a fact authority."""
from dataclasses import asdict, dataclass
import math
import re
from datetime import datetime, timezone

from .action_planning import digest, identifier
from .capability import parse_capability_datetime
from .environment_access import AttachmentUse, EnvironmentAccessError


def reject(code):
    raise EnvironmentAccessError('ENTRY_' + code)


def entry_time(value):
    """Keep the received offset verbatim; compare instants in UTC internally.

    This is entry provenance, not a change to the frozen UTC fact contract.
    """
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value):
        reject('TIME_FORMAT')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        reject('TIME_FORMAT')


@dataclass(frozen=True)
class ContactIntent:
    """Formed Thinking intention, not a permission or proof of delivery."""
    item_id: str
    entry_id: str
    version: str = 'w04-contact-intent-v1'

    def __post_init__(self):
        identifier(self.item_id)
        identifier(self.entry_id)
        if self.version != 'w04-contact-intent-v1':
            reject('CONTACT_INTENT_VERSION')

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            reject('CONTACT_INTENT_SHAPE')
        return cls(**value)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class EntryBinding:
    entry_id: str
    use: AttachmentUse
    user_id: str
    user_account: str
    subject_account: str
    recipient_account: str
    audience: str
    read_from: tuple[str, ...]
    can_receive: bool
    can_initiate: bool
    contact_enabled: bool
    verified_at: str
    expires_at: str
    version: int = 1
    send_use: AttachmentUse | None = None

    def __post_init__(self):
        for value in (self.entry_id, self.user_id, self.user_account,
                      self.subject_account, self.recipient_account):
            identifier(value)
        if not isinstance(self.use, AttachmentUse) or self.use.session_id is None:
            reject('BINDING_USE')
        if self.send_use is not None and (not isinstance(self.send_use, AttachmentUse) or
                (self.send_use.subject_id, self.send_use.environment, self.send_use.account_id) !=
                (self.use.subject_id, self.use.environment, self.subject_account)):
            reject('SENDER_USE')
        if self.audience not in {'PRIVATE', 'GROUP'} or self.user_account == self.subject_account:
            reject('ROLE_BINDING')
        if self.audience == 'PRIVATE' and self.recipient_account != self.user_account:
            reject('RECIPIENT_BINDING')
        if type(self.version) is not int or self.version < 1:
            reject('BINDING_VERSION')
        if any(type(v) is not bool for v in (self.can_receive, self.can_initiate, self.contact_enabled)):
            reject('BINDING_FLAGS')
        if not isinstance(self.read_from, tuple) or len(set(self.read_from)) != len(self.read_from):
            reject('TRANSFER_SCOPE')
        for value in self.read_from:
            identifier(value)
        if parse_capability_datetime(self.expires_at) <= parse_capability_datetime(self.verified_at):
            reject('BINDING_TIME')

    def to_dict(self):
        return {**asdict(self), 'read_from': list(self.read_from)}

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            reject('BINDING_SHAPE')
        return cls(**{**value, 'use': AttachmentUse(**value['use']), 'read_from': tuple(value['read_from']),
                      'send_use': AttachmentUse(**value['send_use']) if value['send_use'] is not None else None})

    @property
    def fingerprint(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class EntryMessage:
    entry_id: str
    external_message_id: str
    sender_account: str
    recipient_account: str
    audience: str
    occurred_at: str
    observed_at: str
    recorded_at: str
    uncertainty_seconds: float = 0
    item_id: str | None = None
    reply_to: str | None = None
    mirror_of: str | None = None
    role: str = 'USER'
    preferred_entry_id: str | None = None

    def __post_init__(self):
        for value in (self.entry_id, self.external_message_id, self.sender_account, self.recipient_account):
            identifier(value)
        for value in (self.item_id, self.reply_to, self.mirror_of, self.preferred_entry_id):
            if value is not None:
                identifier(value)
        if self.role not in {'USER', 'SUBJECT_ECHO', 'SUBJECT_CONTINUATION'} or self.audience not in {'PRIVATE', 'GROUP'}:
            reject('MESSAGE_ROLE')
        times = [entry_time(v) for v in (self.occurred_at, self.observed_at, self.recorded_at)]
        if times[2] < times[1]:
            reject('OBSERVATION_ORDER')
        if type(self.uncertainty_seconds) not in (int, float) or not math.isfinite(self.uncertainty_seconds) or self.uncertainty_seconds < 0:
            reject('TIME_UNCERTAINTY')

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            reject('MESSAGE_SHAPE')
        return cls(**value)


def validate_entry_record(value):
    if not isinstance(value, dict) or set(value) != {'version', 'message', 'binding', 'binding_hash', 'content_hash'}:
        reject('RECORD_SHAPE')
    if value['version'] != 'w04-entry-v1':
        reject('RECORD_VERSION')
    message = EntryMessage.from_dict(value['message'])
    binding = EntryBinding.from_dict(value['binding'])
    if message.entry_id != binding.entry_id or value['binding_hash'] != binding.fingerprint:
        reject('RECORD_BINDING')
    if not isinstance(value['content_hash'], str) or len(value['content_hash']) != 71 or not value['content_hash'].startswith('sha256:'):
        reject('RECORD_CONTENT')
    return message, binding
