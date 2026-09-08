"""Typed subjective long-term records embedded only in SubjectState."""
from copy import deepcopy
from dataclasses import dataclass
from .dynamic_mind import text, utc, timestamp
from .errors import LearningValidationError


def growth_document(value, *, kind, subject_id=None):
    expected = {'version','subject_id','environment','authority','entries'}
    if (not isinstance(value,dict) or set(value)!=expected or value['version']!='p15-'+kind+'-v1'
            or value['environment'] not in {'TEST','RESEARCH'}
            or value['authority']!='SUBJECTIVE_INTERPRETATION' or not isinstance(value['entries'],list)):
        raise LearningValidationError('GROWTH_DOCUMENT_INVALID')
    text(value['subject_id'])
    if subject_id is not None and value['subject_id']!=subject_id:
        raise LearningValidationError('GROWTH_SUBJECT_MISMATCH')
    seen=set()
    for entry in value['entries']:
        fields={'id','object_id','interpretation','source_roots','version','updated_at'}
        if kind=='relationships':fields |= {'stances'}
        if not isinstance(entry,dict) or set(entry)!=fields:
            raise LearningValidationError('GROWTH_ENTRY_INVALID')
        for key in ('id','object_id','interpretation'):text(entry[key])
        utc(entry['updated_at'])
        if type(entry['version']) is not int or entry['version']<1 or entry['id'] in seen:
            raise LearningValidationError('GROWTH_ENTRY_IDENTITY_INVALID')
        seen.add(entry['id'])
        roots=entry['source_roots']
        if not isinstance(roots,list) or not roots or len(set(roots))!=len(roots):
            raise LearningValidationError('GROWTH_ROOTS_INVALID')
        for root in roots:text(root)
        if kind=='relationships':
            if not isinstance(entry['stances'],list) or len(set(entry['stances']))!=len(entry['stances']):
                raise LearningValidationError('GROWTH_STANCES_INVALID')
            for stance in entry['stances']:text(stance)
    return deepcopy(value)


@dataclass(frozen=True)
class GrowthCommand:
    command_id: str
    subject_id: str
    environment: str
    expected_revision: int
    learning_id: str
    operation: str
    reason: str
    trait_id: str | None = None

    def __post_init__(self):
        for key in ('command_id','subject_id','learning_id','reason'):text(getattr(self,key))
        if (self.environment not in {'TEST','RESEARCH'} or self.operation not in {'SOLIDIFY','ROLLBACK'}
                or type(self.expected_revision) is not int or self.expected_revision<0
                or self.operation=='ROLLBACK' and not self.trait_id):
            raise LearningValidationError('GROWTH_COMMAND_INVALID')

    def to_dict(self):return dict(self.__dict__)
