"""Isolated W02-C root source over P16's real C1/E5-A TEST path."""
from dataclasses import replace
from pathlib import Path

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.external_absorption import ExternalRootProof
from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.services.external_absorption_service import ExternalAbsorptionService, ExternalAbsorptionPolicy
from continuity_engine.testing.p16_provider_fixture import P16Fixture
from continuity_engine.testing.persistence import atomic_write_json, read_json
from .p08_action_fixture import _validate_fixture_root


class FakeRootPort:
    def __init__(self, root):
        self.path = _validate_fixture_root(Path(root)) / 'w02c-fake/roots.json'
        self.read_calls = 0
        if not self.path.exists():
            atomic_write_json(self.path, {'format':'w02c-roots-v1','entries':[], 'hash':digest([])})

    def _entries(self):
        value = read_json(self.path)
        if (set(value) != {'format','entries','hash'} or value['format'] != 'w02c-roots-v1'
                or not isinstance(value['entries'],list) or value['hash'] != digest(value['entries'])):
            raise ExternalCapabilityError('FAKE_ROOTS_CORRUPT')
        return [ExternalRootProof.from_dict(x) for x in value['entries']]

    def _write(self, entries):
        values = [x.to_dict() for x in entries]
        atomic_write_json(self.path, {'format':'w02c-roots-v1','entries':values,'hash':digest(values)})

    def read_root(self, root_id):
        self.read_calls += 1
        return next((x for x in self._entries() if x.root_id == root_id), None) or self._missing()

    @staticmethod
    def _missing():
        raise ExternalCapabilityError('FAKE_ROOT_MISSING')

    def accept_result(self, result, descriptor):
        entries = {x.root_id:x for x in self._entries()}
        for candidate in result.candidates:
            for root in candidate.roots:
                old = entries.get(root)
                if old is None:
                    entries[root] = ExternalRootProof(root, descriptor.connector_id,digest(descriptor.to_dict()),result.subject_id,
                        result.environment, candidate.source_version, candidate.content_hash,
                        (candidate.content_hash,), candidate.observed_at, candidate.expires_at,
                        descriptor.permission, 'ACTIVE')
                elif old.version == candidate.source_version and old.status == 'ACTIVE':
                    hashes = tuple(dict.fromkeys((*old.material_hashes,candidate.content_hash)))
                    entries[root] = replace(old, material_hashes=hashes)
                # A later query cannot undo explicit revocation, deletion or
                # correction of the source authority.
        self._write([entries[k] for k in sorted(entries)])

    def change(self, root_id, **changes):
        entries = self._entries()
        index = next((i for i,x in enumerate(entries) if x.root_id == root_id), None)
        if index is None:
            raise ExternalCapabilityError('FAKE_ROOT_MISSING')
        entries[index] = replace(entries[index], **changes)
        self._write(entries)

    def remove(self, root_id):
        entries = [x for x in self._entries() if x.root_id != root_id]
        self._write(entries)


class W02CFixture:
    def __init__(self, root, *, policy=None, runtime=None, manager=None):
        self.base = P16Fixture(root,runtime=runtime,manager=manager)
        self.roots = FakeRootPort(self.base.runtime.data_root)
        self.absorption = ExternalAbsorptionService(self.roots,policy=policy or ExternalAbsorptionPolicy(2,0.6))
        self.base.external.absorption = self.absorption
        self.absorption.bind(self.base.external)
        self.base.fake.root_sink = self.roots.accept_result
        self.base.core_options['subject_growth'] = True
        self.reopen()

    def reopen(self):
        return self.base.reopen()

    def submit(self, request=None):
        return self.base.submit(request)

    def next_round(self):
        return self.base.next_round()

    @property
    def core(self):return self.base.core
    @property
    def state(self):return self.base.state
    @property
    def external_calls(self):return self.base.external_calls
    @property
    def last_context(self):return self.base.last_context

    def source(self, root_id='external:shared-source:continuity'):
        return self.roots.read_root(root_id)
