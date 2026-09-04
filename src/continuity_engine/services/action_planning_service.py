"""P08 bounded local Direct/Planner orchestration on the ONE E5-A ledger.

No production wiring, scheduler, Adapter transport, or state update capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Callable

from continuity_engine.domain.action import ActionIntent, ActionType, ResourceLimits, RiskLevel
from continuity_engine.domain.action_capability import InternalActionRequest, InternalActionResult, ActionReceipt, ReceiptQuery
from continuity_engine.domain.action_planning import ActionChoice, OptionalActionPlanner, digest, identifier
from continuity_engine.domain.capability import CapabilityStatus, parse_capability_datetime
from continuity_engine.domain.context_composition import ContextCompositionResult, CompositionStatus
from continuity_engine.domain.errors import CapabilityValidationError
from continuity_engine.domain.integration_results import format_contract_datetime
from .action_service import ActionService
from .capability_coordination_service import CapabilityCoordinationService


class LocalActionAdapter(Protocol):
    adapter_id: str
    def query(self, request: InternalActionRequest) -> ActionReceipt | ReceiptQuery: ...
    def execute(self, request: InternalActionRequest) -> ActionReceipt: ...


class ActionChoiceProducer(Protocol):
    producer_id: str
    def resolve(self, decision_id: str) -> ActionChoice: ...


class LocalActionConstraints(Protocol):
    def validate_context(self, context: ContextCompositionResult) -> bool: ...
    def confirmed(self, request: InternalActionRequest) -> bool: ...
    def recoverable(self, request: InternalActionRequest) -> bool: ...
    def reality_allowed(self, request: InternalActionRequest) -> bool: ...


@dataclass(frozen=True)
class ActionCapabilityBinding:
    capability: str
    adapter: LocalActionAdapter
    action_type: ActionType
    permission: str
    cost: int = 1
    atomic: bool = True
    version: str = "v1"

    def __post_init__(self) -> None:
        identifier(self.capability)
        identifier(self.permission)
        identifier(self.adapter.adapter_id)
        identifier(self.version)
        if self.capability == "model.generate" or self.action_type is ActionType.UPDATE_STATE:
            raise CapabilityValidationError("P08 cannot take over Thinking or Evolution")
        if type(self.cost) is not int or self.cost < 0 or type(self.atomic) is not bool:
            raise CapabilityValidationError("invalid capability policy")

    def canonical_hash(self) -> str:
        return digest([self.capability, self.adapter.adapter_id, self.version,
                       self.action_type.value, self.permission, self.cost, self.atomic])


@dataclass(frozen=True)
class ActionRunResult:
    decision_id: str
    plan: object | None
    requests: tuple[InternalActionRequest, ...]
    results: tuple[InternalActionResult | None, ...]

    @property
    def status(self) -> str:
        if all(x is not None and x.status is CapabilityStatus.SUCCEEDED for x in self.results):
            return "COMPLETED"
        if any(x is not None and x.status.failed_terminally for x in self.results):
            return "FAILED"
        return "WAITING_CAPABILITY"

    def to_dict(self) -> dict:
        return {"decision_id": self.decision_id, "status": self.status,
                "plan_id": self.plan.plan_id if self.plan else None,
                "requests": [x.to_dict() for x in self.requests],
                "results": [x.to_dict() if x else None for x in self.results],
                "direct_state_write_allowed": False, "evolution_commit_allowed": False}

    def canonical_hash(self) -> str:
        return digest(self.to_dict())


class ActionPlanningService:
    def __init__(self, *, coordination: CapabilityCoordinationService, action_gate: ActionService,
                 producer: ActionChoiceProducer, constraints: LocalActionConstraints,
                 capabilities: tuple[ActionCapabilityBinding, ...], clock: Callable[[], datetime],
                 subject_id: str, environment: str, planner: OptionalActionPlanner | None = None,
                 limits: ResourceLimits | None = None, fault: Callable[[str], None] | None = None):
        if environment not in {"TEST", "RESEARCH"}:
            raise CapabilityValidationError("P08 local runtime boundary")
        self.coordination = coordination
        self.action_gate = action_gate
        self.producer, self.constraints = producer, constraints
        self.capabilities = {item.capability: item for item in capabilities}
        if len(self.capabilities) != len(capabilities):
            raise CapabilityValidationError("duplicate capability binding")
        self.clock, self.subject_id, self.environment = clock, subject_id, environment
        self.planner = planner or OptionalActionPlanner()
        self.limits = limits or ResourceLimits()
        self.fault = fault or (lambda point: None)

    def _validate_input(self, choice, context) -> ActionChoice:
        if not isinstance(choice, ActionChoice) or not isinstance(context, ContextCompositionResult):
            raise CapabilityValidationError("structured trusted choice and P06 COMPLETE context required")
        checked = ContextCompositionResult.from_dict(context.to_dict())
        if checked.status is not CompositionStatus.COMPLETE:
            raise CapabilityValidationError("P06_CONTEXT_NOT_COMPLETE")
        snapshot, trace = checked.snapshot, checked.trace
        assert snapshot is not None
        if (snapshot.subject_id, snapshot.environment, snapshot.source_revision,
            snapshot.route_plan_hash, snapshot.manifest_hash) != (
            trace.subject_id, trace.environment, trace.source_revision,
            trace.route_plan_hash, trace.manifest_hash):
            raise CapabilityValidationError("P06_TRACE_BOUNDARY_MISMATCH")
        if (choice.subject_id, choice.environment, choice.snapshot_hash, choice.source_revision) != (
            self.subject_id, self.environment, snapshot.snapshot_hash, snapshot.source_revision):
            raise CapabilityValidationError("CHOICE_CONTEXT_BOUNDARY_MISMATCH")
        if (snapshot.subject_id, snapshot.environment) != (self.subject_id, self.environment):
            raise CapabilityValidationError("CONTEXT_RUNTIME_BOUNDARY_MISMATCH")
        if not set(choice.source_fragment_ids) <= {x.fragment_id for x in snapshot.fragments}:
            raise CapabilityValidationError("CHOICE_SOURCE_MISSING")
        if choice.producer_id != self.producer.producer_id or self.producer.resolve(choice.decision_id) != choice:
            raise CapabilityValidationError("UNVERIFIED_THINKING_CHOICE")
        # This verifies immutable provenance/recovery ownership, not permission
        # to execute now. Current Context validity is checked at new-work gates.
        for step in choice.steps:
            if step.capability not in self.capabilities:
                raise CapabilityValidationError("CAPABILITY_UNAVAILABLE")
        return ActionChoice.from_dict(choice.to_dict())

    def run(self, choice: ActionChoice, context: ContextCompositionResult, *, retry: bool = False) -> ActionRunResult:
        choice = self._validate_input(choice, context)
        plan = self.planner.plan(choice, capability_requires_plan=any(
            not self.capabilities[x.capability].atomic for x in choice.steps))
        requests = tuple(InternalActionRequest(choice, x.step_id, plan.plan_id if plan else None,
                         self.capabilities[x.capability].adapter.adapter_id,
                         self.capabilities[x.capability].canonical_hash())
                         for x in choice.steps)
        # Reserve all identities before any side effect, so partial plans cannot change on restart.
        for request in requests:
            self.coordination.ensure_action_request(
                request, allow_create=self.constraints.validate_context(context))
        self.fault("after_requests")
        results: dict[str, InternalActionResult | None] = {}
        for request in requests:
            if any(results.get(dep) is None or results[dep].status is not CapabilityStatus.SUCCEEDED
                   for dep in request.step.dependencies):
                results[request.step_id] = None
                continue
            results[request.step_id] = self._resume(request, context=context, retry=retry)
        return ActionRunResult(choice.decision_id, plan, requests, tuple(results[x.step_id] for x in requests))

    def _save(self, result: InternalActionResult, adapter) -> InternalActionResult:
        self.coordination.accept_action_result(result, received_at=result.completed_at, receipt_verifier=adapter)
        self.fault("after_result")
        return result

    def _resume(self, request: InternalActionRequest, *, context: ContextCompositionResult,
                retry: bool) -> InternalActionResult:
        binding = self.capabilities[request.capability_type]
        attempts = self.coordination.action_attempts(request, receipt_verifier=binding.adapter)
        if attempts and (attempts[-1].result.status is CapabilityStatus.SUCCEEDED
                         or attempts[-1].result.status.failed_terminally):
            return attempts[-1].result
        now = format_contract_datetime(self.clock())
        # Query even after a crash between request reservation and execute/result persistence.
        try:
            fact = binding.adapter.query(request)
        except Exception:
            # Query failure must not authorize execution or a local terminal stop.
            return self._save(InternalActionResult(request, CapabilityStatus.UNKNOWN,
                              "EXECUTION_UNCONFIRMED", now), binding.adapter)
        if isinstance(fact, ActionReceipt):
            fact.validate_request(request)
            if fact.adapter_id != binding.adapter.adapter_id:
                raise CapabilityValidationError("ADAPTER_RECEIPT_BINDING_MISMATCH")
            return self._save(InternalActionResult(request, CapabilityStatus(fact.status),
                              "VERIFIED_RECEIPT", now, fact, ("RECEIPT_RECOVERY",)), binding.adapter)
        if fact is not ReceiptQuery.NOT_EXECUTED:
            return self._save(InternalActionResult(request, CapabilityStatus.UNKNOWN,
                              "EXECUTION_UNCONFIRMED", now), binding.adapter)
        if attempts and not retry:
            return attempts[-1].result
        if not self.constraints.validate_context(context):
            raise CapabilityValidationError("CONTEXT_CHANGED_BEFORE_ACTION")
        reason, gates = self._gate(request, binding, now)
        if reason:
            status = CapabilityStatus.EXPIRED if reason == "CHOICE_EXPIRED" else CapabilityStatus.UNKNOWN
            return self._save(InternalActionResult(request, status, reason, now, gate_reasons=gates), binding.adapter)
        self._save(InternalActionResult(request, CapabilityStatus.PROPOSED, "READY_TO_EXECUTE", now,
                                       gate_reasons=gates), binding.adapter)
        self.fault("before_adapter")
        try:
            receipt = binding.adapter.execute(request)
        except Exception:
            return self._save(InternalActionResult(request, CapabilityStatus.UNKNOWN,
                              "ADAPTER_RESPONSE_UNKNOWN", now, gate_reasons=gates), binding.adapter)
        self.fault("after_adapter_before_result")
        if not isinstance(receipt, ActionReceipt) or receipt.adapter_id != binding.adapter.adapter_id:
            raise CapabilityValidationError("INVALID_ADAPTER_RECEIPT")
        receipt.validate_request(request)
        return self._save(InternalActionResult(request, CapabilityStatus(receipt.status), "VERIFIED_RECEIPT",
                          format_contract_datetime(self.clock()), receipt, gates), binding.adapter)

    def _gate(self, request, binding, now) -> tuple[str | None, tuple[str, ...]]:
        if parse_capability_datetime(now) >= parse_capability_datetime(request.choice.expires_at):
            return "CHOICE_EXPIRED", ("CHOICE_EXPIRED",)
        if len(request.choice.steps) > self.limits.maximum_plan_steps or sum(
            self.capabilities[x.capability].cost for x in request.choice.steps
        ) > self.limits.maximum_estimated_cost:
            return "RESOURCE_EXHAUSTED", ("RESOURCE_EXHAUSTED",)
        intent = ActionIntent(
            intent_id=request.operation_id, action_type=binding.action_type,
            source_thought="sealed-p08-choice", reason="structured-thinking-decision",
            target=request.step.target, expected_effect="local-test-only",
            confidence=1.0, risk_level=RiskLevel.LOW,
            required_permissions=[binding.permission], estimated_resource_cost=binding.cost,
            created_at=parse_capability_datetime(now),
        )
        decision = self.action_gate.assess_local_action(
            intent, subject_id=request.subject_id, environment=request.choice.environment,
            limits=self.limits, confirmed=self.constraints.confirmed(request),
        )
        if not decision.approved:
            return decision.rejection_reason, (decision.rejection_reason,)
        if not self.constraints.recoverable(request):
            return "RECOVERABILITY_NOT_READY", ("ACTION_GATE_PASSED", "RECOVERABILITY_NOT_READY")
        if not self.constraints.reality_allowed(request):
            return "REALITY_BOUNDARY_DENIED", ("ACTION_GATE_PASSED", "REALITY_BOUNDARY_DENIED")
        return None, ("CAPABILITY_RESOLVED", "ACTION_GATE_PASSED", "PERMISSION_CONFIRMED",
                      "RESOURCE_PASSED", "RECOVERABILITY_PASSED", "REALITY_BOUNDARY_PASSED")
