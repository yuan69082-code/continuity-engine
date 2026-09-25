"""W02-C internal evidence bindings, never a second request or fact authority."""
from dataclasses import dataclass

from .action_planning import digest, exact, hash_value, identifier
from .capability import parse_capability_datetime
from .external_capabilities import ExternalCapabilityError


@dataclass(frozen=True)
class ExternalRootProof:
    root_id: str
    connector_id: str
    descriptor_hash: str
    subject_id: str
    environment: str
    version: str
    canonical_hash: str
    material_hashes: tuple[str, ...]
    observed_at: str
    valid_until: str
    read_scope: str
    status: str
    material_role: str = 'DATA'

    def __post_init__(self):
        for value in (self.root_id, self.connector_id, self.subject_id, self.version, self.read_scope):
            identifier(value)
        if (not self.root_id.startswith('external:') or self.environment not in ('TEST', 'RESEARCH')
                or self.status not in ('ACTIVE', 'REVOKED', 'DELETED')
                or self.material_role not in ('DATA', 'INSTRUCTION')
                or not isinstance(self.material_hashes, tuple) or not self.material_hashes
                or len(self.material_hashes) > 16 or len(set(self.material_hashes)) != len(self.material_hashes)):
            raise ExternalCapabilityError('EXTERNAL_ROOT_PROOF_INVALID')
        hash_value(self.canonical_hash)
        hash_value(self.descriptor_hash)
        for value in self.material_hashes:
            hash_value(value)
        if self.canonical_hash not in self.material_hashes:
            raise ExternalCapabilityError('EXTERNAL_ROOT_PROOF_INVALID')
        if parse_capability_datetime(self.valid_until) <= parse_capability_datetime(self.observed_at):
            raise ExternalCapabilityError('EXTERNAL_ROOT_PROOF_TIME')

    def to_dict(self):
        return {**self.__dict__, 'material_hashes': list(self.material_hashes)}

    @classmethod
    def from_dict(cls, value):
        data = exact(value, set(cls.__dataclass_fields__))
        if not isinstance(data['material_hashes'], list):
            raise ExternalCapabilityError('EXTERNAL_ROOT_PROOF_INVALID')
        return cls(**{**data, 'material_hashes': tuple(data['material_hashes'])})

    @property
    def binding_hash(self):
        # An additional attested translation/summary is another rendering of
        # the same root, not a new version or a new independent experience.
        return digest({k:v for k,v in self.to_dict().items() if k != 'material_hashes'})


@dataclass(frozen=True)
class AbsorptionDecision:
    source_id: str
    source_version: str
    content_hash: str
    roots: tuple[str, ...]
    proof_hashes: tuple[str, ...]
    disposition: str
    reason: str

    def __post_init__(self):
        identifier(self.source_id)
        identifier(self.source_version)
        hash_value(self.content_hash)
        if (not isinstance(self.roots, tuple) or not self.roots or len(self.roots) != len(self.proof_hashes)
                or self.disposition not in ('CANDIDATE', 'REFERENCE_EXISTING', 'TEMP_USE', 'NEEDS_EVIDENCE',
                                            'CONFLICT', 'NOT_ADOPTED', 'FAILED_WAITING')
                or not isinstance(self.reason, str) or not self.reason):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_INVALID')
        for root, proof_hash in zip(self.roots, self.proof_hashes):
            identifier(root)
            hash_value(proof_hash)

    def to_dict(self):
        return {**self.__dict__, 'roots': list(self.roots), 'proof_hashes': list(self.proof_hashes)}

    @classmethod
    def from_dict(cls, value):
        data = exact(value, set(cls.__dataclass_fields__))
        if not isinstance(data['roots'], list) or not isinstance(data['proof_hashes'], list):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_INVALID')
        return cls(**{**data, 'roots': tuple(data['roots']), 'proof_hashes': tuple(data['proof_hashes'])})


@dataclass(frozen=True)
class ExternalAbsorptionRecord:
    request_id: str
    request_hash: str
    result_hash: str
    subject_id: str
    environment: str
    acquired_at: str
    decisions: tuple[AbsorptionDecision, ...]
    version: str = 'w02-external-absorption-v1'

    def __post_init__(self):
        for value in (self.request_id, self.subject_id):
            identifier(value)
        for value in (self.request_hash, self.result_hash):
            hash_value(value)
        parse_capability_datetime(self.acquired_at)
        if (self.environment not in ('TEST', 'RESEARCH') or self.version != 'w02-external-absorption-v1'
                or not isinstance(self.decisions, tuple) or len(self.decisions) > 16
                or len({d.source_id for d in self.decisions}) != len(self.decisions)):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_INVALID')

    def to_dict(self):
        return {**self.__dict__, 'decisions': [d.to_dict() for d in self.decisions]}

    @classmethod
    def from_dict(cls, value):
        data = exact(value, set(cls.__dataclass_fields__))
        if not isinstance(data['decisions'], list):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_INVALID')
        return cls(**{**data, 'decisions': tuple(AbsorptionDecision.from_dict(x) for x in data['decisions'])})

    def validate_result(self, result):
        if ((self.request_id, self.request_hash, self.result_hash, self.subject_id, self.environment)
                != (result.capability_request_id, result.request_hash, digest(result.to_dict()),
                    result.subject_id, result.environment)
                or len(self.decisions) != len(result.candidates)
                or any((d.source_id, d.source_version, d.content_hash, d.roots)
                       != (c.source_id, c.source_version, c.content_hash, c.roots)
                       for d, c in zip(self.decisions, result.candidates))):
            raise ExternalCapabilityError('EXTERNAL_ABSORPTION_BINDING')
