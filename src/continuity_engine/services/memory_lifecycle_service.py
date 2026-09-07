"""Explicit Memory lifecycle coordination; no timers, SubjectState or effect writes."""
from dataclasses import dataclass

from continuity_engine.domain.errors import MemoryValidationError, MemoryNotFoundError
from continuity_engine.domain.memory import MemoryLifecycle, MemoryStatus, _utc
from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand, LifecycleAction, lifecycle_result


class TimelineMemorySources:
    """Current raw Event and Memory versions from existing authorities, no copies."""
    def __init__(self, timeline, memory, subject_id):
        self.timeline,self.memory,self.subject_id=timeline,memory,subject_id

    def __call__(self, memory):
        from continuity_engine.domain.timeline import TimelineEventStatus
        if memory.subject_id!=self.subject_id or memory.environment!=self.memory.environment: return None
        entries={e.event.event_id:e for e in self.timeline.rebuild(self.subject_id).entries}
        result={}
        def visit(m,seen):
            if m.memory_id in seen or m.source_message_ids: return False
            for identifier in m.source_event_ids:
                entry=entries.get(identifier)
                if entry is None or entry.status is not TimelineEventStatus.ACTIVE: return False
                result['event:'+identifier]=entry.event.canonical_hash()
            for identifier in m.source_memory_ids:
                try: parent=self.memory.load_memory(self.subject_id,identifier)
                except MemoryNotFoundError: return False
                if not parent.is_available: return False
                result['memory:'+identifier]=parent.canonical_hash()
                if not visit(parent,seen|{m.memory_id}): return False
            return True
        return result if visit(memory,set()) and result else None


@dataclass(frozen=True)
class LifecycleResult:
    memory_id: str
    revision: int
    content_hash: str
    lifecycle: str
    retrieval_weight: float
    replay: bool
    reason_code: str


class MemoryLifecycleService:
    def __init__(self, repository, *, subject_id, environment, permissions, clock,
                 source_snapshot, confirmation_verifier=None, allow_test_delete=False):
        if environment != repository.environment or environment not in ('ENGINE','TEST','RESEARCH'):
            raise MemoryValidationError('lifecycle repository environment mismatch')
        if allow_test_delete and environment != 'TEST':
            raise MemoryValidationError('production deletion NOT_READY')
        self.repository=repository
        self.subject_id=subject_id
        self.environment=environment
        self.permissions=permissions
        self.clock=clock
        self.source_snapshot=source_snapshot
        self.confirmation_verifier=confirmation_verifier
        self.allow_test_delete=allow_test_delete

    def _authorize(self, permission_id, revision, scope, capability):
        permission=self.permissions.get_permission(self.subject_id,permission_id)
        if (permission.subject_id!=self.subject_id or permission.revision!=revision
                or not permission.allows(capability,scope)):
            raise MemoryValidationError('current lifecycle permission denied')

    def submit(self, command):
        if not isinstance(command,MemoryLifecycleCommand):
            raise MemoryValidationError('typed lifecycle command required')
        # Revalidate mutable/forged inputs before any repository access.
        command=MemoryLifecycleCommand.from_dict(command.to_dict())
        if command.subject_id!=self.subject_id or command.environment!=self.environment:
            raise MemoryValidationError('lifecycle subject/environment mismatch')
        if command.action is LifecycleAction.DELETE and not self.allow_test_delete:
            raise MemoryValidationError('production deletion NOT_READY')

        def evaluate(memory,*,replay):
            now=_utc(self.clock(),'trusted lifecycle clock')
            self._authorize(command.permission_id,command.permission_revision,command.scope,
                            'memory.lifecycle.'+command.action.value)
            if self.confirmation_verifier is None or self.confirmation_verifier(command) is not True:
                raise MemoryValidationError('explicit command-bound confirmation required')
            if replay:
                # Recovery reports facts, never reinstates the old memory payload.
                return None
            if not command.issued_at <= now < command.expires_at:
                raise MemoryValidationError('lifecycle command expired or from the future')
            if command.action in (LifecycleAction.RESTORE,LifecycleAction.DECAY,LifecycleAction.DOWNWEIGHT):
                actual=self.source_snapshot(memory)
                if (actual is None or dict(command.source_hashes)!=actual
                        or not self.repository.current_usable(self.subject_id,memory.memory_id,include_self=False)):
                    raise MemoryValidationError('source invalid, unavailable or version/hash changed')
            # Source/confirmation ports can take time or expose a permission change.
            # Recheck immediately before building the new persisted version.
            now=_utc(self.clock(),'commit lifecycle clock')
            self._authorize(command.permission_id,command.permission_revision,command.scope,
                            'memory.lifecycle.'+command.action.value)
            if not command.issued_at <= now < command.expires_at:
                raise MemoryValidationError('lifecycle command expired before commit')
            return lifecycle_result(memory,command,now),now
        memory,replay=self.repository.apply_lifecycle(command,evaluate)
        return LifecycleResult(memory.memory_id,memory.revision,memory.canonical_hash(),
            memory.effective_lifecycle.value,memory.effective_weight,replay,
            'CURRENT_TOMBSTONE' if memory.effective_lifecycle is MemoryLifecycle.DELETED else 'LIFECYCLE_RECEIPT')

    def trace(self, memory_id, *, permission_id, permission_revision):
        memory=self.repository.load_memory(self.subject_id,memory_id)
        self._authorize(permission_id,permission_revision,memory.scope,'memory.lifecycle.trace')
        return {'memory_id':memory_id,'subject_id':memory.subject_id,'environment':memory.environment,
                'revision':memory.revision,'hash':memory.canonical_hash(),
                'lifecycle':memory.effective_lifecycle.value,'validity':memory.status.value,
                'temperature':memory.temperature.value,'roots':tuple(memory.root_evidence_ids),
                'lineage_ids':tuple(r.lineage_id for r in self.repository.list_lineage(self.subject_id)
                                    if r.target_memory_id==memory_id),
                'physical_erasure':'NOT_READY'}

    def recall_history(self, *, cue, limit, permission_id, permission_revision):
        if not isinstance(cue,str) or not cue.strip() or isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=5:
            raise MemoryValidationError('historical recall requires a non-empty cue and limit 1..5')
        terms=set(cue.casefold().split())
        matches=[]
        for memory in self.repository.list_memories(self.subject_id,include_inactive=True):
            if (memory.status is not MemoryStatus.ACTIVE or memory.effective_lifecycle
                    not in (MemoryLifecycle.INACTIVE,MemoryLifecycle.ARCHIVED)):
                continue
            words=set(memory.content.casefold().split()) | {t.casefold() for t in memory.tags}
            score=len(terms & words)/len(terms)
            # All cue terms must match, with two terms minimum; no semantic guess.
            if len(terms)<2 or score<1: continue
            self._authorize(permission_id,permission_revision,memory.scope,'memory.lifecycle.recall')
            sources = self.source_snapshot(memory)
            if sources is None:
                continue
            self._current_history(memory, permission_id, permission_revision)
            matches.append((memory, sources))
        selected=sorted(matches,key=lambda x:(-x[0].occurred_at.timestamp(),x[0].memory_id))[:limit]
        # A later lookup may invalidate an earlier candidate. Recheck sources,
        # then current permission and the target itself after every external call.
        for memory,sources in selected:
            if self.source_snapshot(memory) != sources:
                raise MemoryValidationError('historical recall source changed during lookup')
            self._current_history(memory,permission_id,permission_revision)
        for memory,_ in selected:
            self._current_history(memory,permission_id,permission_revision)
        return tuple({'memory_id':m.memory_id,'content':m.content,'revision':m.revision,'hash':m.canonical_hash(),
                      'lifecycle':m.effective_lifecycle.value,'root_evidence_ids':tuple(m.root_evidence_ids),
                      'reason_code':'EXACT_STRONG_CUE_HISTORY_ONLY','restored':False}
                     for m,_ in selected)

    def _current_history(self, memory, permission_id, permission_revision):
        self._authorize(permission_id,permission_revision,memory.scope,'memory.lifecycle.recall')
        current=self.repository.load_memory(self.subject_id,memory.memory_id)
        if (current.canonical_hash()!=memory.canonical_hash() or current.status is not MemoryStatus.ACTIVE
                or current.effective_lifecycle not in (MemoryLifecycle.INACTIVE,MemoryLifecycle.ARCHIVED)
                or not self.repository.current_usable(self.subject_id,memory.memory_id,include_self=False)):
            raise MemoryValidationError('historical recall target or source is no longer current')
