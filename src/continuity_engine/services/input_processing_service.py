"""Bounded input interpretation and station receipts, using original C1 stores.

No model calls, facts, events, subject mutations or separate request ledger.
Interpretation is explicitly a tentative reading, never a truth assertion.
"""
from __future__ import annotations

import re
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.errors import CapabilityValidationError
from continuity_engine.domain.input_processing import InputDisposition as D, InputProcessingRecord
from continuity_engine.domain.timeline import TimelineEventStatus

_LOCK_GUARD = Lock()
_INPUT_LOCKS = {}


def _interpret_v1(content):
    """Small, declared rule coverage. Preserve ambiguity instead of inferring facts."""
    text = content.strip()
    lower = text.casefold()
    question = bool(re.search(r'[?？]|^(who|what|why|how|when|where)\b', lower))
    quoted = bool(re.search(r'[“”「」]|\bsays?\b|说[：:]|说道', text, re.I))
    other = bool(re.search(r'朋友|他|她|同事|\b(my friend|he|she|they)\b', lower))
    wish = bool(re.search(r'想|希望|打算|\b(want|wish|hope|plan to)\b', lower))
    negative = bool(re.search(r'没有|没|不曾|不是|未|\b(not|never|didn.t|haven.t)\b', lower))
    historical = bool(re.search(r'昨天|以前|曾经|去年|\b(yesterday|last year|previously)\b', lower))
    hypothetical = bool(re.search(r'如果|假如|假设|\b(if|suppose|hypothetically)\b', lower))
    memory = bool(re.search(r'记住|回忆|记得|\b(remember|recall)\b', lower))
    unclear = not bool(text) or bool(re.search(r'也许|可能|好像|\b(maybe|perhaps)\b', lower))
    return {'rule_version': 'w02-bounded-reading-v1',
            'speaker': 'platform_sender', 'about': 'OTHER_REPORTED' if other else (
                'SELF_REPORTED' if re.match(r'我|i\b|my\b', lower) else 'UNRESOLVED'),
            'nature': 'QUOTED' if quoted else 'HYPOTHETICAL' if hypothetical else 'QUESTION' if question else 'DESIRE' if wish else 'CLAIM',
            'negated': negative, 'time_reference': 'HISTORICAL_UNRESOLVED' if historical else 'UNRESOLVED',
            'memory_requested': memory, 'uncertain': unclear or quoted or other or hypothetical,
            'topic_span': [0, min(len(text), 256)], 'content_hash': digest(content),
            'authority': 'INPUT_INTERPRETATION_NOT_FACT'}


def interpret(content):
    """Bounded lexical reading, not a truth/polarity classifier for all Chinese.

    Negation spans describe clauses, not the truth of the whole message. Unknown
    scope stays unknown. Prior persisted v1 readings are verified with v1 below.
    """
    reading = _interpret_v1(content)
    text = content.strip()
    # Quoted content must not determine the sender's subject or negation.
    quoted_spans = list(re.finditer(r'“[^”]*”|「[^」]*」|‘[^’]*’|"[^"\n]*"', text))
    outer = list(text)
    for match in quoted_spans:
        outer[match.start():match.end()] = ' ' * (match.end() - match.start())
    outer = ''.join(outer)
    lead = re.sub(r'^(?:昨天|以前|曾经|去年|今天)[，,\s]*', '', outer).casefold()
    other = bool(re.match(r'(?:我的)?(?:朋友|同事)(?!圈)|(?:他|她|他们|她们)(?=说|想|希望|打算|喜欢|不|没|是|要|会|已经)|(?:my friend|he|she|they)\b', lead))
    own = bool(re.match(r'我(?:们)?(?!和|与)|(?:i|my)\b', lead)) and not other
    about = 'OTHER_REPORTED' if other else 'SELF_REPORTED' if own else 'UNRESOLVED'
    reported = bool(re.search(r'听说|据说|认为|说道|说[：:]|(?:我|朋友|同事|他|她)说', outer))
    unmatched_quote = bool(re.search(r'[“”「」‘’"]', outer))
    quoted = bool(quoted_spans) or unmatched_quote or reading['nature'] == 'QUOTED' or reported
    # Do not match 不 inside 不但/不错/不得不 or 未 inside 未来 etc.
    pattern = r'(?:不曾|没有|没|未|不)(?:喜欢|想|希望|打算|吃|去|做|完成|发生|收到|记住|知道|同意|允许|愿意|需要|要|能|会)|不是(?!不)|\b(?:not|never|didn.t|haven.t)\b'
    spans = [list(m.span()) for m in re.finditer(pattern, outer, re.I)]
    residue = list(outer)
    for start, end in spans:
        residue[start:end] = ' ' * (end-start)
    residue = re.sub(r'不但|不仅|不错|不得了|未来|其他|其它', '', ''.join(residue))
    scope_unknown = (bool(re.search(r'不是不|不得不|不能不|并非不|不无|没|不|未|别', residue))
                     or unmatched_quote or (reported and bool(spans)))
    mixed = bool(re.search(r'[，,；;]|但是|但|而', outer)) and bool(spans)
    negated = None if scope_unknown else bool(spans)
    reading.update(rule_version='w02-bounded-reading-v2', about=about,
        nature='QUOTED' if quoted else reading['nature'], negated=negated,
        negation_spans=spans, negation_scope='UNRESOLVED' if scope_unknown else 'OUTSIDE_QUOTE_CLAUSES',
        uncertain=(not text or bool(re.search(r'也许|可能|好像|\b(maybe|perhaps)\b', text, re.I))
                   or quoted or other or (about == 'UNRESOLVED' and reading['nature'] in {'CLAIM', 'DESIRE'})
                   or scope_unknown or mixed
                   or reading['nature'] == 'HYPOTHETICAL'))
    return reading


def _reading(content, existing=None):
    version = existing.manifest['interpretation'].get('rule_version') if existing else 'w02-bounded-reading-v2'
    if version == 'w02-bounded-reading-v1':
        return _interpret_v1(content)
    if version == 'w02-bounded-reading-v2':
        return interpret(content)
    raise CapabilityValidationError('INPUT_READING_VERSION_UNSUPPORTED')


def _stations(reading, content):
    stations = ['conversation']
    if reading['memory_requested'] or (reading['nature'] == 'CLAIM' and content.strip()):
        stations.append('memory')
    if reading['uncertain']:
        stations.append('verification')
    return stations


class InputProcessingService:
    def __init__(self, source):
        self.source = source
        self.core = None
        # Same-process C1 callers for one existing journal share orchestration.
        # This is neither durable ownership nor a second request ledger.
        key = os.path.normcase(str(source.ledger.operation_path.resolve()))
        with _LOCK_GUARD:
            self.lock = _INPUT_LOCKS.setdefault(key, RLock())
        self.lock_path = Path(tempfile.gettempdir()) / 'continuity-w02-locks' / (digest(key)[7:] + '.lock')

    @contextmanager
    def admission(self):
        """Bounded local admission, reusing P18's OS lock primitive, no work ledger.

        Only a coordination byte in the OS Temp directory; snapshots contain all
        business progress in the original operation journal. Crash releases the
        handle. Do not unlink a shared coordination path during another opener.
        """
        from continuity_engine.storage.json_runtime_repository import file_lock
        from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
        if not self.lock.acquire(timeout=0.25):
            raise CapabilityValidationError('INPUT_ADMISSION_BUSY')
        try:
            lease = file_lock(self.lock_path, wait_seconds=0.25)
            try:
                lease.__enter__()
            except RuntimeBoundaryError as exc:
                if str(exc) == 'RUNTIME_BUSY':
                    raise CapabilityValidationError('INPUT_ADMISSION_BUSY') from None
                raise
            try:
                yield
            finally:
                lease.__exit__(None, None, None)
        finally:
            self.lock.release()

    def prepare(self, perception, operation, save):
        core = self.core
        if len(perception.external_facts) != 1:
            raise CapabilityValidationError('INPUT_SINGLE_MESSAGE_REQUIRED')
        fact = perception.external_facts[0]
        existing = operation.domain_progress.input_processing
        reading = _reading(fact.content, existing)
        stations = _stations(reading, fact.content)
        record = InputProcessingRecord({
            'request_id': operation.request_id, 'operation_id': operation.operation_id,
            'subject_id': operation.subject_id, 'environment': core.environment,
            'perception_hash': digest(perception.to_dict()), 'recorded_at': operation.reserved_at,
            'source': {k: v for k, v in fact.to_dict().items() if k != 'content'},
            'interpretation': reading, 'stations': stations})
        if existing is not None:
            if existing.manifest != record.manifest:
                raise CapabilityValidationError('INPUT_RECOVERY_BINDING_CHANGED')
            record = existing
        else:
            save(record)
        self.source.bind(perception, operation, record)
        self.source.authorize(operation.request_id)
        pending = 0
        failure = None
        if 'memory' in stations:
            prior = record.latest('memory')
            if prior is None or prior.disposition is D.FAILED_WAITING:
                try:
                    if core.gates.memory:
                        pending = core._consolidate_events()
                    refs = self._memory_refs(fact) if core.gates.memory else ()
                except Exception as exc:
                    record = record.append('memory', D.FAILED_WAITING, 'MEMORY_PROCESSING_FAILED')
                    save(record)
                    failure = exc
                else:
                    record = record.append('memory', D.REFERENCE_EXISTING if refs else D.NEEDS_EVIDENCE,
                        'MATCHED_EXISTING_EVENT_MEMORY' if refs else 'MESSAGE_IS_NOT_VERIFIED_EVENT', refs)
                    save(record)
            else:
                self.verify_memory(record, fact)
        elif core.gates.memory:
            # Existing background consolidation is not a claim that this message was remembered.
            pending = core._consolidate_events()
        if 'verification' in stations and record.latest('verification') is None:
            record = record.append('verification', D.NEEDS_EVIDENCE, 'INPUT_INTERPRETATION_UNCERTAIN')
            save(record)
        return record, pending, failure

    def _memory_refs(self, fact):
        entries = self.core.timeline.rebuild(self.core.subject_id).entries
        valid = any(e.status is TimelineEventStatus.ACTIVE and e.event.event_id == fact.source_event_id
                    and e.event.content == fact.content for e in entries)
        if not valid:
            return ()
        memories = self.core.memory.list_memories(self.core.subject_id)
        refs = []
        for m in memories:
            if (m.memory_id == 'memory:' + fact.source_event_id and
                    'event:' + fact.source_event_id in m.root_evidence_ids and m.effective_lifecycle.value == 'active'):
                history = self.core.memory.memory_history(self.core.subject_id, m.memory_id)
                original = next(h for h in history if h.revision == m.revision)
                refs.append(self._memory_ref(original))
        return tuple(refs)

    @staticmethod
    def _memory_ref(memory):
        return 'memory:' + memory.memory_id + '@' + str(memory.revision) + '#' + digest(memory.to_dict())

    def verify_receipts(self, operation, *, partial=False):
        """A journal claim cannot substitute for source-owned fragments/memory facts."""
        progress = operation.domain_progress
        if progress is None or progress.input_processing is None:
            raise CapabilityValidationError('INPUT_VERIFIABLE_CHECKPOINT_REQUIRED')
        record = progress.input_processing
        perception = progress.perception or (progress.input_preparation if partial else None)
        if perception is None:
            raise CapabilityValidationError('INPUT_VERIFIABLE_CHECKPOINT_REQUIRED')
        record.validate_binding(operation, perception)
        fact = perception.external_facts[0]
        if (record.manifest['source'] != {k: v for k, v in fact.to_dict().items() if k != 'content'}
                or record.manifest['interpretation'] != _reading(fact.content, record)
                or record.manifest['stations'] != _stations(_reading(fact.content, record), fact.content)):
            raise CapabilityValidationError('INPUT_MANIFEST_MATERIAL_MISMATCH')
        context = perception.continuity_context
        if context is None and not partial or context is not None and context.input_manifest_hash != record.binding_hash:
            raise CapabilityValidationError('INPUT_CONTEXT_BINDING_INVALID')
        if context is not None:
            context.validate_perception(perception)
        if partial:
            if self.core.subject_states.load(self.core.subject_id).revision != operation.input_revision:
                raise CapabilityValidationError('INPUT_PARTIAL_VERSION_CHANGED')
            if context is not None and not self.core.current(context):
                raise CapabilityValidationError('INPUT_PARTIAL_CONTEXT_STALE')
            self.verify_memory(record, fact)
        for station in record.manifest['stations']:
            receipt = record.latest(station)
            if receipt is None or receipt.disposition is D.FAILED_WAITING:
                if partial:
                    if receipt is not None and (receipt.results or receipt.reason != {
                            'memory': 'MEMORY_PROCESSING_FAILED',
                            'conversation': 'CONTEXT_PREPARATION_FAILED'}.get(station)):
                        raise CapabilityValidationError('INPUT_FAILURE_RECEIPT_INVALID')
                    continue
                raise CapabilityValidationError('INPUT_UNFINISHED_STATION_WITH_CONTEXT')
            if station == 'conversation':
                if context is None:
                    raise CapabilityValidationError('INPUT_CONVERSATION_PROOF_MISSING')
                refs = tuple(f.fragment_id for f in context.composition.snapshot.fragments
                             if f.source_id == self.source.source_id)
                expected = (D.TEMP_USE, 'CURRENT_INPUT_COMPOSED') if refs else (
                    D.NOT_ADOPTED, 'CURRENT_INPUT_NOT_SELECTED_OR_BUDGETED')
                if (receipt.disposition, receipt.reason) != expected or receipt.results != refs:
                    raise CapabilityValidationError('INPUT_CONVERSATION_FACT_MISMATCH')
            elif station == 'memory':
                if receipt.disposition is D.REFERENCE_EXISTING:
                    fact = perception.external_facts[0]
                    history = self.core.memory.memory_history(self.core.subject_id, 'memory:' + fact.source_event_id)
                    refs = {self._memory_ref(m) for m in history if 'event:' + fact.source_event_id in m.root_evidence_ids
                            and m.content.endswith(': ' + fact.content)}
                    if not receipt.results or not set(receipt.results) <= refs or receipt.reason != 'MATCHED_EXISTING_EVENT_MEMORY':
                        raise CapabilityValidationError('INPUT_MEMORY_FACT_MISMATCH')
                elif (receipt.disposition, receipt.reason, receipt.results) != (
                        D.NEEDS_EVIDENCE, 'MESSAGE_IS_NOT_VERIFIED_EVENT', ()):
                    raise CapabilityValidationError('INPUT_MEMORY_DISPOSITION_INVALID')
            elif (receipt.disposition, receipt.reason, receipt.results) != (
                    D.NEEDS_EVIDENCE, 'INPUT_INTERPRETATION_UNCERTAIN', ()):
                raise CapabilityValidationError('INPUT_VERIFICATION_DISPOSITION_INVALID')

    def verify_memory(self, record, fact):
        prior = record.latest('memory')
        if prior and prior.disposition is D.REFERENCE_EXISTING and prior.results != self._memory_refs(fact):
            raise CapabilityValidationError('INPUT_MEMORY_SOURCE_NO_LONGER_CURRENT')

    def finish_context(self, record, context, save):
        refs = tuple(f.fragment_id for f in context.composition.snapshot.fragments if f.source_id == self.source.source_id)
        prior = record.latest('conversation')
        disposition = D.TEMP_USE if refs else D.NOT_ADOPTED
        reason = 'CURRENT_INPUT_COMPOSED' if refs else 'CURRENT_INPUT_NOT_SELECTED_OR_BUDGETED'
        if prior is None or prior.disposition is D.FAILED_WAITING:
            record = record.append('conversation', disposition, reason, refs)
            save(record)
        elif (prior.disposition, prior.reason, prior.results) != (disposition, reason, refs):
            raise CapabilityValidationError('INPUT_CONTEXT_RECEIPT_CHANGED')
        return record
