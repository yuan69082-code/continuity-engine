"""Permission-scoped view of original SubjectState; never a second state store."""
from dataclasses import replace
import json

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.context_routing import ContextSourceBatch
from continuity_engine.domain.errors import ContextCompositionSourceError
from .context_router_service import SubjectStateContextSource, ContextSourceValidation
from .context_material_resolvers import ExactContextPayload, SubjectStateMaterialResolver


class EntryStateSource(SubjectStateContextSource):
    def __init__(self, repository, *, environment, entry):
        super().__init__(repository, environment=environment)
        self.entry = entry

    def retrieve(self, query):
        return self._retrieve(query)

    def _retrieve(self, query, section=None):
        batch = super().retrieve(query)
        operation = self.entry.ledger._load_operation_input(query.request_id)
        if not query.request_id.startswith('native:') and (operation is None or operation.entry_record is None):
            return batch
        state, document = self.entry.scoped_state(query.request_id, section=section)
        version = 'entry:' + query.request_id + ':revision:' + str(state.revision)
        return ContextSourceBatch(self.source_id, self.partition, version,
            tuple(c if c.content_hash == digest(document[c.stable_id.rsplit(':', 1)[-1]]) else
                  replace(c, version=version, content_hash=digest(document[c.stable_id.rsplit(':', 1)[-1]]))
                  for c in batch.candidates if section is None or c.stable_id.rsplit(':', 1)[-1] == section))

    def revalidate(self, query, candidate, source_version):
        batch = self._retrieve(query, candidate.stable_id.rsplit(':', 1)[-1])
        current = next((c for c in batch.candidates if c.stable_id == candidate.stable_id), None)
        return ContextSourceValidation(current == candidate and batch.source_version == source_version,
            'ENTRY_STATE_CURRENT' if current == candidate else 'ENTRY_STATE_CHANGED', batch.source_version,
            current.version if current else 'missing', current.content_hash if current else candidate.content_hash)


class EntryStateResolver(SubjectStateMaterialResolver):
    def __init__(self, repository, *, environment, entry):
        super().__init__(repository, environment=environment)
        self.entry = entry

    def resolve(self, reference):
        if not reference.version.startswith('entry:'):
            return super().resolve(reference)
        request_id, revision = reference.version[6:].rsplit(':revision:', 1)
        section = reference.stable_id.rsplit(':', 1)[-1]
        state, document = self.entry.scoped_state(request_id, section=section)
        if (reference.subject_id != state.subject_id or reference.environment != self._environment
                or section not in document or str(state.revision) != revision
                or digest(document[section]) != reference.content_hash):
            raise ContextCompositionSourceError('ENTRY_STATE_CHANGED')
        protected = section in {'identity', 'continuity', 'relationship'}
        return ExactContextPayload(self.source_id, self.partition, reference.stable_id, state.subject_id,
            self._environment, reference.version, reference.content_hash, state.temporal.updated_at,
            json.dumps(document[section], ensure_ascii=False, sort_keys=True, separators=(',', ':')),
            1.0, (f'subject-state:{state.subject_id}:revision:{state.revision}:{section}',),
            protected, section if protected else None)
