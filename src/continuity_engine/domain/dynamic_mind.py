"""Internal P14 values. These are candidates until the existing Evolution commits.

No store, clock reader, provider, permission decision or execution lives here.
Provider hidden reasoning is not an accepted field in any persisted value.
"""
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import math


class MindValidationError(ValueError):
    pass


DRIVES = ('intimacy', 'exploration', 'sexual', 'solitude', 'expression', 'protection', 'rest')
SOMATIC = ('tension', 'relaxation', 'restlessness', 'heaviness', 'excitement', 'warmth')
PHASES = ('arise', 'intensify', 'weaken', 'persist', 'suppress', 'fail_to_suppress',
          'disappear', 'recur', 'conflict', 'transform', 'act', 'abandon')
EPISODE_KINDS = ('joy', 'sadness', 'fear', 'disgust', 'anger', 'boredom', 'delight', 'helplessness')


def utc(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError as exc:
            raise MindValidationError('MIND_TIME_INVALID') from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MindValidationError('MIND_TIME_REQUIRES_TRUSTED_UTC')
    return value.astimezone(timezone.utc)


def timestamp(value):
    return utc(value).isoformat().replace('+00:00', 'Z')


def ratio(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise MindValidationError('MIND_RATIO_INVALID')
    return float(value)


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise MindValidationError('MIND_TEXT_INVALID')
    return value


def strings(values):
    if not isinstance(values, list) or len(values) > 64:
        raise MindValidationError('MIND_REFERENCES_INVALID')
    for value in values:
        text(value)
    if len(values) != len(set(values)):
        raise MindValidationError('MIND_DUPLICATE_REFERENCES')


@dataclass(frozen=True)
class MindState:
    subject_id: str
    environment: str
    updated_at: datetime
    drives: dict
    fatigue: float = 0.0
    arousal: float = 0.0
    somatic: dict = field(default_factory=lambda: dict.fromkeys(SOMATIC, 0.0))
    episodes: list = field(default_factory=list)
    dispositions: list = field(default_factory=list)
    desires: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    will: list = field(default_factory=list)
    thoughts: list = field(default_factory=list)
    regulation: dict = field(default_factory=dict)
    subjective_seconds: float = 0.0
    version: str = 'p14-mind-v1'

    def __post_init__(self):
        text(self.subject_id)
        if self.environment not in {'TEST', 'RESEARCH'} or self.version != 'p14-mind-v1':
            raise MindValidationError('MIND_BOUNDARY_INVALID')
        object.__setattr__(self, 'updated_at', utc(self.updated_at))
        for name, keys in [('drives', DRIVES), ('somatic', SOMATIC)]:
            values = getattr(self, name)
            if not isinstance(values, dict) or set(values) != set(keys):
                raise MindValidationError('MIND_DIMENSIONS_INCOMPLETE')
            for value in values.values():
                ratio(value)
        ratio(self.fatigue)
        ratio(self.arousal)
        if (type(self.subjective_seconds) not in (int, float)
                or not math.isfinite(self.subjective_seconds) or self.subjective_seconds < 0):
            raise MindValidationError('MIND_SUBJECTIVE_TIME_INVALID')
        schemas = {
            'episodes': {'id', 'object', 'kind', 'source_keys', 'interpretation', 'unresolved',
                         'status', 'intensity', 'created_at', 'updated_at', 'trajectory', 'resolution'},
            'dispositions': {'object', 'kind', 'basis'},
            'desires': {'id', 'drive', 'object', 'origin', 'phase', 'strength', 'reason',
                        'created_at', 'updated_at', 'trajectory'},
            'conflicts': {'id', 'object', 'poles', 'reason'},
            'will': {'desire_id', 'stance', 'supporting_reasons', 'opposing_reasons', 'alternatives',
                     'commitment', 'decision', 'action_tendency'},
            'thoughts': {'id', 'theme', 'content', 'reason', 'desire_ids', 'conflict_ids',
                         'created_at', 'last_recurred_at', 'recurrences', 'unresolved'},
        }
        for name, keys in schemas.items():
            values = getattr(self, name)
            if not isinstance(values, list) or len(values) > 64:
                raise MindValidationError('MIND_STATE_CAPACITY_EXCEEDED')
            identities = []
            for value in values:
                allowed_shapes = (keys, keys | {'concern_basis'}) if name == 'episodes' else (keys,)
                if not isinstance(value, dict) or set(value) not in allowed_shapes:
                    raise MindValidationError('MIND_RECORD_SHAPE_INVALID:' + name)
                identities.append(value.get('id', value.get('desire_id',
                                 (value.get('object'), value.get('kind')))))
            if len(identities) != len(set(identities)):
                raise MindValidationError('MIND_RECORD_IDENTITY_CONFLICT')
        for episode in self.episodes:
            text(episode['id']); text(episode['unresolved'])
            if episode['kind'] not in EPISODE_KINDS or episode['status'] not in {'unresolved', 'processing', 'resolved'}:
                raise MindValidationError('MIND_EPISODE_INVALID')
            strings(episode['source_keys'])
            if 'concern_basis' in episode:
                basis = episode['concern_basis']
                if (not isinstance(basis, dict) or set(basis) != {'source_key', 'occurred_at'}
                        or basis['source_key'] not in episode['source_keys']
                        or utc(basis['occurred_at']) > self.updated_at):
                    raise MindValidationError('MIND_CONCERN_BASIS_INVALID')
            text(episode['object']); text(episode['interpretation']); ratio(episode['intensity'])
            if not utc(episode['created_at']) <= utc(episode['updated_at']) <= self.updated_at:
                raise MindValidationError('MIND_EPISODE_TIME_INVALID')
            if not isinstance(episode['trajectory'], list) or len(episode['trajectory']) > 8:
                raise MindValidationError('MIND_EPISODE_TRAJECTORY_INVALID')
            for point in episode['trajectory']:
                if not isinstance(point, dict) or set(point) != {'at', 'reason', 'source_key'}:
                    raise MindValidationError('MIND_EPISODE_TRAJECTORY_INVALID')
                utc(point['at']); text(point['reason']); text(point['source_key'])
            if episode['resolution'] is not None:
                resolution = episode['resolution']
                if not isinstance(resolution, dict) or set(resolution) != {
                        'episode_id', 'interpretation', 'reason', 'source_keys', 'resolve'}:
                    raise MindValidationError('MIND_RESOLUTION_SHAPE_INVALID')
                strings(resolution['source_keys']); text(resolution['interpretation']); text(resolution['reason'])
                if type(resolution['resolve']) is not bool or resolution['episode_id'] != episode['id']:
                    raise MindValidationError('MIND_RESOLUTION_BINDING_INVALID')
                if not resolution['source_keys'] or not set(resolution['source_keys']) <= set(episode['source_keys']):
                    raise MindValidationError('MIND_RESOLUTION_BINDING_INVALID')
            if episode['status'] == 'resolved' and not episode['resolution']:
                raise MindValidationError('MIND_RESOLUTION_BASIS_MISSING')
        for disposition in self.dispositions:
            text(disposition['object']); text(disposition['kind']); strings(disposition['basis'])
            if not disposition['basis']:
                raise MindValidationError('MIND_DISPOSITION_BASIS_MISSING')
        for desire in self.desires:
            text(desire['id']); text(desire['object'])
            if desire['drive'] not in DRIVES or desire['phase'] not in PHASES or desire['origin'] != 'ENDOGENOUS':
                raise MindValidationError('MIND_DESIRE_INVALID')
            ratio(desire['strength']); text(desire['reason']); utc(desire['created_at']); utc(desire['updated_at'])
            if not isinstance(desire['trajectory'], list) or len(desire['trajectory']) > 8:
                raise MindValidationError('MIND_DESIRE_TRAJECTORY_INVALID')
            for point in desire['trajectory']:
                if not isinstance(point, dict) or set(point) != {'at', 'phase', 'reason'} or point['phase'] not in PHASES:
                    raise MindValidationError('MIND_DESIRE_TRAJECTORY_INVALID')
                utc(point['at']); text(point['reason'])
        desire_ids = {d['id'] for d in self.desires}
        conflict_ids = {c['id'] for c in self.conflicts}
        for conflict in self.conflicts:
            text(conflict['id']); text(conflict['object']); text(conflict['reason']); strings(conflict['poles'])
            if len(conflict['poles']) < 2:
                raise MindValidationError('MIND_CONFLICT_POLES_MISSING')
        for thought in self.thoughts:
            text(thought['content']); text(thought['theme']); text(thought['reason'])
            strings(thought['desire_ids']); strings(thought['conflict_ids'])
            if type(thought['recurrences']) is not int or thought['recurrences'] < 1:
                raise MindValidationError('MIND_THOUGHT_RECURRENCE_INVALID')
            if (not set(thought['desire_ids']) <= desire_ids or not set(thought['conflict_ids']) <= conflict_ids
                    or type(thought['unresolved']) is not bool
                    or not utc(thought['created_at']) <= utc(thought['last_recurred_at']) <= self.updated_at):
                raise MindValidationError('MIND_THOUGHT_BINDING_INVALID')
        for evaluation in self.will:
            strings(evaluation['supporting_reasons']); strings(evaluation['opposing_reasons'])
            strings(evaluation['alternatives']); text(evaluation['commitment'])
            if evaluation['stance'] not in {'consider', 'pursue', 'hold', 'abandon'}:
                raise MindValidationError('MIND_WILL_INVALID')
            if evaluation['desire_id'] not in desire_ids or evaluation['decision'] not in {'DEFER', 'QUESTION', 'PURSUE'}:
                raise MindValidationError('MIND_WILL_BINDING_INVALID')
            text(evaluation['action_tendency'])
        if self.regulation and (set(self.regulation) != {'strategy', 'desire_id', 'reason', 'outcome', 'capacity', 'load'}
                                or self.regulation['outcome'] not in {'success', 'failure'}):
            raise MindValidationError('MIND_REGULATION_INVALID')
        if self.regulation:
            ratio(self.regulation['capacity']); ratio(self.regulation['load']); text(self.regulation['reason'])
            if (self.regulation['desire_id'] not in desire_ids
                    or self.regulation['strategy'] not in {'suppress', 'reappraise', 'rest'}):
                raise MindValidationError('MIND_REGULATION_BINDING_INVALID')

    @classmethod
    def create(cls, subject_id, environment, at):
        return cls(subject_id, environment, utc(at), dict.fromkeys(DRIVES, 0.0))

    def to_dict(self):
        # Validate mutable nested data before every serialization.
        self.__post_init__()
        result = deepcopy(self.__dict__)
        result['updated_at'] = timestamp(self.updated_at)
        return result

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise MindValidationError('MIND_STATE_SHAPE_INVALID')
        return cls(**deepcopy(value))

    def with_body(self, *, fatigue=None, **somatic):
        if set(somatic) - set(SOMATIC):
            raise MindValidationError('MIND_SOMATIC_DIMENSION_INVALID')
        return replace(self, fatigue=self.fatigue if fatigue is None else fatigue,
                       somatic={**self.somatic, **somatic})

    def with_dispositions(self, values):
        """Value construction only, never an authorization or state write."""
        return replace(self, dispositions=deepcopy(values))


@dataclass(frozen=True)
class MindEvolution:
    state: MindState
    influence: dict
    changes: tuple[str, ...]


def context_state_document(state):
    """Exact bounded state projection for P05/P06, with the complete value hash.

    Detailed current records stay in SubjectState and the original Evolution
    history. This projection is not another store and cannot be written back.
    Legacy projections are byte-for-byte unchanged when no mind exists.
    """
    from .action_planning import digest
    value = state.to_dict()
    for section,key in [('identity','self_narrative'),('relationship','objects')]:
        growth=value[section].get(key)
        if growth is not None:
            value[section][key]={'version':growth['version'],'state_hash':digest(growth),
                'authority':growth['authority'],'entry_count':len(growth['entries']),
                'recent_interpretation':growth['entries'][-1]['interpretation'][:160] if growth['entries'] else '',
                'detail':'bounded subjective projection; full roots remain in SubjectState/Evolution'}
    mind = value['intentions'].get('dynamic_mind')
    if mind is not None:
        value['intentions']['dynamic_mind'] = {
            'version': mind['version'], 'state_hash': digest(mind),
            'subject_id': mind['subject_id'], 'environment': mind['environment'],
            'updated_at': mind['updated_at'], 'subjective_seconds': mind['subjective_seconds'],
            'episode_count': len(mind['episodes']), 'desire_count': len(mind['desires']),
            'conflict_count': len(mind['conflicts']), 'thought_count': len(mind['thoughts']),
            'detail': 'authorized-current-state-projection; not the complete private record',
        }
    return value
