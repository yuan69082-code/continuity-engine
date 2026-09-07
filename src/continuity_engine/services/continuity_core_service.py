"""P09 composition at the normal Engine interaction checkpoints.

All durable input stays in the original operation/ThinkSession records. Actions
use P08 and the existing E5-A ledger. Dependencies are host-neutral ports.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Protocol

from continuity_engine.domain.action_planning import ActionChoice, ActionSpecification, digest
from continuity_engine.domain.action_capability import InternalActionRequest
from continuity_engine.domain.capability import CapabilityStatus
from continuity_engine.domain.continuity_core import ContinuityCoreContext
from continuity_engine.domain.context_composition import ContextBudget, CompositionStatus, ContextAuthority
from continuity_engine.domain.context_routing import RetrievalBudget
from continuity_engine.domain.errors import CapabilityValidationError, MemoryNotFoundError
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.domain.memory import (
    MemoryRecord, MemoryKind, MemoryEvidenceType, MemoryTimeRange, MemoryStatus,
    MemoryLineageType,
)
from continuity_engine.domain.timeline import TimelineEventStatus

from .action_planning_service import ActionPlanningService


class CoreActionPolicy(Protocol):
    producer_id: str
    def choose(self, operation, context, thinking, action) -> ActionChoice | None: ...


class CoreDecisionPolicy:
    """Translate an approved Engine decision, never interpret commands in text."""
    producer_id = "c1-engine-decision-v1"

    def choose(self, operation, context, thinking, action):
        if not action.decision.approved:
            return None
        result = thinking.session.result
        if result is None or result.update_subject_state:
            return None  # The original UPDATE_STATE gate/Evolution retains ownership.
        capabilities = []
        if result.request_more_memory:
            capabilities.append("memory.lookup")
        if result.suggest_future_user_contact:
            capabilities.append("contact.send")
        if not capabilities:
            capabilities = ["silence" if result.should_wait else "expression.emit"]
        steps = tuple(ActionSpecification(
            f"step-{i}", capability, "engine.local",
            digest([result.result_id, capability]), (f"step-{i-1}",) if i else (),
        ) for i, capability in enumerate(capabilities))
        snapshot = context.composition.snapshot
        at = action.decision.created_at
        return ActionChoice(
            "c1:" + digest(operation.operation_id)[7:], self.producer_id,
            operation.subject_id, snapshot.environment, snapshot.snapshot_hash,
            snapshot.source_revision, tuple(f.fragment_id for f in snapshot.fragments),
            "INFORMATION_NEED" if result.request_more_memory else "ACTION_INTENT",
            steps, format_contract_datetime(at), format_contract_datetime(at + timedelta(minutes=10)),
        )


@dataclass(frozen=True)
class ContinuityCoreGates:
    enabled: bool = True
    memory: bool = True
    contradictions: bool = True
    actions: bool = True
    emotion_decay: bool = True

    def __post_init__(self):
        if any(type(v) is not bool for v in self.__dict__.values()):
            raise ValueError("C1 gates must be booleans")


class _BoundProducer:
    def __init__(self, policy, operation, context, thinking, action):
        self.producer_id = policy.producer_id
        self.policy, self.inputs = policy, (operation, context, thinking, action)

    def resolve(self, decision_id):
        choice = self.policy.choose(*self.inputs)
        if choice is None or choice.decision_id != decision_id:
            raise CapabilityValidationError("C1_DECISION_BINDING_INVALID")
        return choice


class _CurrentConstraints:
    def __init__(self, core, context):
        self.core, self.context = core, context

    def validate_context(self, composition):
        return (composition == self.context.composition and self.core.current(self.context)
                and self.core.constraints.validate_context(composition))

    def confirmed(self, request):
        return self.core.constraints.confirmed(request)

    def recoverable(self, request):
        return self.core.constraints.recoverable(request)

    def reality_allowed(self, request):
        return self.core.constraints.reality_allowed(request)


class ContinuityCoreService:
    def __init__(self, *, subject_id, environment, router, composer, detector,
                 timeline, memory_repository, consolidation, subject_states,
                 coordination, action_gate, constraints, capabilities, clock,
                 permission_policy, policy=None, gates=None, retrieval_budget=None,
                 context_budget=None, context_ttl=timedelta(minutes=10), planner=None, limits=None, fault=None):
        if environment not in {"TEST", "RESEARCH"}:
            raise ValueError("P09 requires a TEST/RESEARCH boundary")
        self.subject_id, self.environment = subject_id, environment
        self.router, self.composer, self.detector = router, composer, detector
        self.timeline, self.memory, self.consolidation = timeline, memory_repository, consolidation
        self.subject_states, self.coordination, self.action_gate = subject_states, coordination, action_gate
        self.constraints, self.capabilities, self.clock = constraints, tuple(capabilities), clock
        self.permission = permission_policy
        self.policy = policy or CoreDecisionPolicy()
        self.gates = gates or ContinuityCoreGates()
        self.retrieval_budget = retrieval_budget or RetrievalBudget()
        self.context_budget = context_budget or ContextBudget(token_limit=768)
        if not isinstance(context_ttl, timedelta) or context_ttl.total_seconds() <= 0:
            raise ValueError("C1 context TTL must be positive")
        self.context_ttl = context_ttl
        self.planner, self.limits, self.fault = planner, limits, fault
        self.last_trace = None
        self.last_action = None

    @property
    def enabled(self):
        return self.gates.enabled

    def memory_lifecycle(self, permissions, *, confirmation_verifier=None, allow_test_delete=False):
        """Explicit host-neutral maintenance entry on this Core's existing Memory."""
        from .memory_lifecycle_service import MemoryLifecycleService, TimelineMemorySources
        if not self.enabled or not self.gates.memory:
            raise ValueError('C1 memory feature gate is disabled')
        return MemoryLifecycleService(self.memory,subject_id=self.subject_id,environment=self.environment,
            permissions=permissions,clock=self.clock,
            source_snapshot=TimelineMemorySources(self.timeline,self.memory,self.subject_id),
            confirmation_verifier=confirmation_verifier,allow_test_delete=allow_test_delete)

    def _consolidate_events(self):
        # Event history is the authoritative source; no chat-history reader exists.
        projection = self.timeline.rebuild(self.subject_id)
        by_id = {e.event.event_id: e for e in projection.entries}
        known = {m.memory_id for m in self.memory.list_memories(self.subject_id,include_inactive=True)}
        pending = [entry for entry in sorted(projection.entries,
            key=lambda e: (e.event.recorded_at, e.event.event_id))
            if entry.status is TimelineEventStatus.ACTIVE and "memory:" + entry.event.event_id not in known]
        for entry in pending[:64]:
            event = entry.event
            self.consolidation.consolidate(MemoryRecord(
                memory_id="memory:" + event.event_id, subject_id=self.subject_id,
                environment=self.environment, kind=MemoryKind.EPISODIC,
                evidence_type=MemoryEvidenceType.EXPERIENTIAL,
                content=event.classification.value + ": " + event.content,
                root_evidence_ids=["event:" + event.event_id], source_event_ids=[event.event_id],
                occurred_at=event.occurred_at, observed_at=event.observed_at,
                recorded_at=event.recorded_at, consolidated_at=self.clock(),
                # This is an episode, not a claim that every event says the same
                # thing. P07 compares trusted propositions across episode scopes.
                confidence=0.8, importance=0.6, activation=0.0, scope="c1.event:" + event.event_id,
                time_range=MemoryTimeRange(event.occurred_at, event.occurred_at),
                consolidation_id="c1-consolidation:" + event.event_id,
                tags=[event.classification.value],
            ))
        for memory in self.memory.list_memories(self.subject_id,include_inactive=True):
            if memory.status is not MemoryStatus.ACTIVE or memory.effective_lifecycle.value == 'deleted':
                continue
            for event_id in memory.source_event_ids:
                entry = by_id.get(event_id)
                if entry is None or entry.status is TimelineEventStatus.ACTIVE:
                    continue
                signals = entry.revoked_by or entry.corrected_by
                if signals:
                    self.consolidation.propagate_signal(
                        self.subject_id, lineage_id="c1-lineage:" + digest([memory.memory_id, signals])[7:],
                        target_memory_id=memory.memory_id,
                        signal=(MemoryLineageType.REVOCATION if entry.revoked_by else MemoryLineageType.CORRECTION),
                        source_event_id=signals[-1], root_evidence_ids=["event:" + signals[-1]],
                    )
        memories = [m for m in self.memory.list_memories(self.subject_id) if m.status is MemoryStatus.ACTIVE]
        sources = sorted(memories, key=lambda m: (m.occurred_at, m.memory_id))[-8:]
        if len(sources) >= 2:
            sid = "c1-summary:" + digest([(m.memory_id, m.revision) for m in sources])[7:]
            try:
                self.memory.load_summary(self.subject_id, sid)
            except MemoryNotFoundError:
                self.consolidation.generate_summary(self.subject_id, summary_id=sid,
                    summary_type="c1.recent", scope="c1.event", confidence=0.8,
                    source_memory_ids=[m.memory_id for m in sources])
        return max(0, len(pending) - 64)

    def prepare(self, perception, operation):
        if not self.enabled:
            return perception
        if perception.subject_id != self.subject_id or operation.subject_id != self.subject_id:
            raise CapabilityValidationError("C1_SUBJECT_BOUNDARY_INVALID")
        if perception.continuity_context is not None:
            perception.continuity_context.validate_perception(perception)
            return perception
        pending_events = self._consolidate_events() if self.gates.memory else 0
        route = self.router.route(perception, request_id=operation.request_id,
                                  environment=self.environment, budget=self.retrieval_budget)
        composition = self.composer.compose(route, budget=self.context_budget)
        if composition.status is not CompositionStatus.COMPLETE:
            raise CapabilityValidationError("C1_CONTEXT_NOT_CONSUMABLE")
        if not self.gates.contradictions:
            # Explicit fallback: no resolver or repository access, all claims unassessed.
            from .contradiction_detector_service import ContradictionDetectorService
            class Unassessed:
                def project(self, fragment):
                    return None
            detection = ContradictionDetectorService(Unassessed(), clock=self.clock).detect(composition)
        else:
            detection = self.detector.detect(composition)
        emotion = (self.subject_states.load(self.subject_id).emotion_state.effective_at(perception.perceived_at)
                   if self.gates.emotion_decay else {"status": "FEATURE_GATED"})
        context = ContinuityCoreContext(digest(perception.to_dict()), route, composition, detection,
                                        emotion, self.gates.actions, pending_events)
        enriched = replace(perception, continuity_context=context)
        context.validate_perception(enriched)
        self._trace(context)
        return enriched

    def _trace(self, context):
        self.last_trace = {"version": "c1-trace-v1", "subject_id": self.subject_id,
            "environment": self.environment, "snapshot_hash": context.composition.snapshot.snapshot_hash,
            "route": context.route.trace.to_dict(), "composition": context.composition.trace.to_dict(),
            "contradictions": context.contradictions.trace.to_dict(),
            "consolidation_pending_events": context.pending_event_count,
            "direct_state_write_allowed": False}

    def current(self, context):
        """Re-resolve the exact selected sources before NEW work; never rewrite them."""
        snapshot = context.composition.snapshot
        if (snapshot.subject_id, snapshot.environment) != (self.subject_id, self.environment):
            return False
        if self.clock() >= snapshot.composed_at + self.context_ttl:
            return False
        if not self.constraints.validate_context(context.composition):
            return False
        if self.subject_states.load(self.subject_id).revision != snapshot.source_revision:
            return False
        # Memory/Summary versions alone do not prove their Event ancestors are
        # still valid. Recheck roots even when P05 did not retrieve raw Timeline.
        event_roots = {root[6:] for fragment in snapshot.fragments
            if fragment.authority in {ContextAuthority.CONFIRMED_MEMORY, ContextAuthority.DERIVED_SUMMARY}
            for root in fragment.provenance_roots if root.startswith("event:")}
        if event_roots:
            active_events = {e.event.event_id for e in self.timeline.rebuild(self.subject_id).entries
                             if e.status is TimelineEventStatus.ACTIVE}
            if not event_roots <= active_events:
                return False
        for ref in context.route.manifest.candidates:
            decision = self.permission.authorize_source(context.route.plan.request, ref.source_id, ref.partition)
            if not decision.allowed:
                return False
            authorize_reference = getattr(self.permission, "authorize_reference", None)
            if not callable(authorize_reference) or not authorize_reference(context.route.plan.request, ref).allowed:
                return False
        checked = self.composer.compose(context.route, budget=snapshot.budget)
        return (checked.status is CompositionStatus.COMPLETE
                and checked.snapshot.fragments == snapshot.fragments
                and checked.snapshot.missing_notices == snapshot.missing_notices)

    def before_thinking(self, perception):
        context = perception.continuity_context
        if context is None or not self.enabled:
            raise CapabilityValidationError("C1_CONTEXT_REQUIRED")
        context.validate_perception(perception)
        if not self.current(context):
            raise CapabilityValidationError("C1_CONTEXT_STALE_OR_UNAUTHORIZED")
        self._trace(context)

    def after_action(self, operation, thinking, action, *, replay=False, retry=False):
        context = operation.domain_progress.perception.continuity_context
        snapshot = thinking.session.perception_snapshot
        if (snapshot is None or snapshot != operation.domain_progress.perception
                or thinking.perception != snapshot):
            raise CapabilityValidationError("C1_THINKING_INPUT_BINDING_INVALID")
        existing = self.coordination.action_requests_by_decision("c1:" + digest(operation.operation_id)[7:])
        if context is None:
            if existing:
                raise CapabilityValidationError("C1_ACTION_HISTORY_WITHOUT_CONTEXT")
            return None
        context.validate_perception(operation.domain_progress.perception)
        self._trace(context)
        if not self.enabled:
            raise CapabilityValidationError("C1_PENDING_FEATURE_DISABLED")
        if not context.actions_enabled:
            if existing:
                raise CapabilityValidationError("C1_ACTION_HISTORY_WITH_DISABLED_INPUT")
            return None
        if not self.gates.actions:
            raise CapabilityValidationError("C1_PENDING_ACTIONS_DISABLED")
        producer = _BoundProducer(self.policy, operation, context, thinking, action)
        choice = self.policy.choose(operation, context, thinking, action)
        if choice is None:
            if existing:
                raise CapabilityValidationError("C1_ACTION_HISTORY_WITHOUT_DECISION")
            return None
        if any(item.choice != choice for item in existing):
            raise CapabilityValidationError("C1_ACTION_HISTORY_INPUT_MISMATCH")
        service = ActionPlanningService(
            coordination=self.coordination, action_gate=self.action_gate, producer=producer,
            constraints=_CurrentConstraints(self, context), capabilities=self.capabilities,
            clock=self.clock, subject_id=self.subject_id, environment=self.environment,
            planner=self.planner, limits=self.limits, fault=self.fault,
        )
        if replay:
            plan = service.planner.plan(choice, capability_requires_plan=any(
                not service.capabilities[s.capability].atomic for s in choice.steps))
            for step in choice.steps:
                binding = service.capabilities[step.capability]
                request = InternalActionRequest(choice, step.step_id, plan.plan_id if plan else None,
                                                binding.adapter.adapter_id, binding.canonical_hash())
                attempts = self.coordination.action_attempts(request, receipt_verifier=binding.adapter)
                if not attempts or attempts[-1].result.status is not CapabilityStatus.SUCCEEDED:
                    raise CapabilityValidationError("C1_COMPLETED_ACTION_FACT_MISSING")
            return None
        self.last_action = service.run(choice, context.composition, retry=retry)
        if self.last_action.status != "COMPLETED":
            raise CapabilityValidationError("C1_ACTION_" + self.last_action.status)
        return self.last_action
