"""Typed W03 view of unfinished matters held inside SubjectState.continuity.

This is an internal state value, not a Scheduler queue or another authority.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .errors import StateValidationError


STATUSES = frozenset({'OPEN', 'WAITING', 'DEFERRED', 'FAILED', 'COMPLETED', 'CANCELLED'})
URGENCIES = frozenset({'LOW', 'NORMAL', 'URGENT'})
TERMINAL = frozenset({'COMPLETED', 'CANCELLED'})


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise StateValidationError('W03_ITEM_'+name+'_INVALID')
    return value


def _time(value, name, *, optional=False):
    if value is None and optional:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError as exc:
            raise StateValidationError('W03_ITEM_'+name+'_INVALID') from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StateValidationError('W03_ITEM_'+name+'_INVALID')
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


@dataclass(frozen=True)
class UnfinishedItem:
    item_id: str
    subject_id: str
    environment: str
    title: str
    source_roots: tuple[str, ...]
    willing: bool
    importance_reason: str
    urgency: str
    due_at: str | None
    wait_condition: str | None
    next_step: str
    status: str
    created_at: str
    updated_at: str
    revision: int = 0
    completion: dict | None = None
    last_progress: str | None = None

    def __post_init__(self):
        for name in ('item_id', 'subject_id', 'title', 'importance_reason', 'next_step'):
            _text(getattr(self, name), name.upper())
        if self.environment not in {'TEST', 'RESEARCH'} or self.urgency not in URGENCIES or self.status not in STATUSES:
            raise StateValidationError('W03_ITEM_BOUNDARY_INVALID')
        if type(self.willing) is not bool or type(self.revision) is not int or self.revision < 0:
            raise StateValidationError('W03_ITEM_VALUE_INVALID')
        if not isinstance(self.source_roots, tuple) or not self.source_roots or len(set(self.source_roots)) != len(self.source_roots):
            raise StateValidationError('W03_ITEM_ROOTS_INVALID')
        for root in self.source_roots:
            _text(root, 'ROOT')
        for name in ('created_at','updated_at'):
            object.__setattr__(self, name, _time(getattr(self,name),name.upper()))
        for name in ('due_at',):
            object.__setattr__(self, name, _time(getattr(self,name),name.upper(),optional=True))
        for name in ('wait_condition','last_progress'):
            if getattr(self,name) is not None:
                _text(getattr(self,name),name.upper())
        if self.updated_at < self.created_at:
            raise StateValidationError('W03_ITEM_TIME_ORDER_INVALID')
        if self.status == 'WAITING' and self.wait_condition is None:
            raise StateValidationError('W03_ITEM_WAIT_CONDITION_MISSING')
        if self.status == 'COMPLETED':
            if not isinstance(self.completion, dict) or set(self.completion) != {'kind','identity','hash'}:
                raise StateValidationError('W03_ITEM_COMPLETION_EVIDENCE_MISSING')
            if self.completion['kind'] not in {'INTERNAL_EVENT','ACTION_RECEIPT'}:
                raise StateValidationError('W03_ITEM_COMPLETION_KIND_INVALID')
            for name in ('identity','hash'):
                _text(self.completion[name], 'COMPLETION_'+name.upper())
        elif self.completion is not None:
            raise StateValidationError('W03_ITEM_PREMATURE_COMPLETION')

    def to_dict(self):
        return {**self.__dict__, 'source_roots': list(self.source_roots),
                'completion': dict(self.completion) if self.completion is not None else None}

    @classmethod
    def from_dict(cls, value: Any):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise StateValidationError('W03_ITEM_SHAPE_INVALID')
        if not isinstance(value['source_roots'], list):
            raise StateValidationError('W03_ITEM_ROOTS_INVALID')
        return cls(**{**value, 'source_roots': tuple(value['source_roots'])})


def item_records(value, *, subject_id=None, environment=None):
    if not isinstance(value, list) or len(value) > 64:
        raise StateValidationError('W03_ITEM_RECORDS_INVALID')
    parsed = [UnfinishedItem.from_dict(item) for item in value]
    if len({item.item_id for item in parsed}) != len(parsed):
        raise StateValidationError('W03_ITEM_DUPLICATE_ID')
    if any(subject_id is not None and item.subject_id != subject_id or
           environment is not None and item.environment != environment for item in parsed):
        raise StateValidationError('W03_ITEM_SUBJECT_ENVIRONMENT_MISMATCH')
    return [item.to_dict() for item in parsed]


def active_titles(continuity):
    """Legacy strings remain readable; typed matters add one current view."""
    known = list(continuity.unfinished_items)
    for item in item_records(continuity.item_records):
        if item['status'] not in TERMINAL and item['title'] not in known:
            known.append(item['title'])
    return known
