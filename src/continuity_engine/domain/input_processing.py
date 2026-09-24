"""Non-authoritative W02 input checkpoint inside the existing operation journal."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re

from .action_planning import digest
from .errors import CapabilityValidationError


class InputDisposition(str, Enum):
    TEMP_USE = 'TEMP_USE'
    CANDIDATE = 'CANDIDATE'
    NEEDS_EVIDENCE = 'NEEDS_EVIDENCE'
    REFERENCE_EXISTING = 'REFERENCE_EXISTING'
    LONG_TERM_PROPOSAL = 'LONG_TERM_PROPOSAL'
    NOT_ADOPTED = 'NOT_ADOPTED'
    FAILED_WAITING = 'FAILED_WAITING'


@dataclass(frozen=True)
class StationReceipt:
    station: str
    disposition: InputDisposition
    reason: str
    results: tuple[str, ...] = ()
    attempt: int = 1

    def __post_init__(self):
        if (self.station not in {'conversation', 'memory', 'verification'}
                or not isinstance(self.disposition, InputDisposition)
                or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,79}', self.reason)
                or type(self.attempt) is not int or self.attempt < 1
                or not isinstance(self.results, tuple)
                or any(not isinstance(x, str) or not x for x in self.results)):
            raise CapabilityValidationError('INPUT_RECEIPT_INVALID')

    def to_dict(self):
        return dict(station=self.station, disposition=self.disposition.value,
                    reason=self.reason, results=list(self.results), attempt=self.attempt)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'station', 'disposition', 'reason', 'results', 'attempt'}:
            raise CapabilityValidationError('INPUT_RECEIPT_SHAPE_INVALID')
        return cls(data['station'], InputDisposition(data['disposition']), data['reason'],
                   tuple(data['results']), data['attempt'])


@dataclass(frozen=True)
class InputProcessingRecord:
    manifest: dict
    receipts: tuple[StationReceipt, ...] = ()
    version: str = 'w02-input-v1'

    def __post_init__(self):
        m = self.manifest
        if (self.version != 'w02-input-v1' or not isinstance(m, dict) or set(m) != {
                'request_id', 'operation_id', 'subject_id', 'environment', 'perception_hash',
                'source', 'interpretation', 'stations', 'recorded_at'}
                or m['environment'] not in {'TEST', 'RESEARCH'}
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', m['perception_hash'])):
            raise CapabilityValidationError('INPUT_MANIFEST_INVALID')
        if (not m['stations'] or m['stations'][0] != 'conversation'
                or len(set(m['stations'])) != len(m['stations'])
                or set(m['stations']) - {'conversation', 'memory', 'verification'}):
            raise CapabilityValidationError('INPUT_STATIONS_INVALID')
        previous = {}
        for receipt in self.receipts:
            if not isinstance(receipt, StationReceipt) or receipt.station not in m['stations']:
                raise CapabilityValidationError('INPUT_RECEIPT_STATION_INVALID')
            old = previous.get(receipt.station)
            if receipt.attempt != (old.attempt + 1 if old else 1):
                raise CapabilityValidationError('INPUT_RECEIPT_ORDER_INVALID')
            if old and old.disposition is not InputDisposition.FAILED_WAITING:
                raise CapabilityValidationError('INPUT_COMPLETED_STATION_REWRITTEN')
            previous[receipt.station] = receipt

    @property
    def binding_hash(self):
        return digest(self.manifest)

    def latest(self, station):
        return next((r for r in reversed(self.receipts) if r.station == station), None)

    def append(self, station, disposition, reason, results=()):
        old = self.latest(station)
        return replace(self, receipts=(*self.receipts, StationReceipt(
            station, disposition, reason, tuple(results), old.attempt + 1 if old else 1)))

    def validate_successor(self, current):
        if (not isinstance(current, InputProcessingRecord) or current.manifest != self.manifest
                or current.receipts[:len(self.receipts)] != self.receipts):
            raise CapabilityValidationError('INPUT_HISTORY_CHANGED')

    def validate_binding(self, operation, perception=None):
        m = self.manifest
        if (m['request_id'], m['operation_id'], m['subject_id']) != (
                operation.request_id, operation.operation_id, operation.subject_id):
            raise CapabilityValidationError('INPUT_OPERATION_MISMATCH')
        if perception is not None:
            raw = perception.to_dict()
            raw.pop('continuity_context', None)
            if digest(raw) != m['perception_hash']:
                raise CapabilityValidationError('INPUT_PERCEPTION_MISMATCH')

    def to_dict(self):
        return dict(version=self.version, manifest=self.manifest,
                    receipts=[r.to_dict() for r in self.receipts])

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'version', 'manifest', 'receipts'}:
            raise CapabilityValidationError('INPUT_CHECKPOINT_SHAPE_INVALID')
        return cls(data['manifest'], tuple(StationReceipt.from_dict(r) for r in data['receipts']), data['version'])
