"""Versioned P09 fixtures; every interaction uses the normal local Engine app."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from continuity_engine.domain.action import ActionType
from continuity_engine.domain.context_composition import ContextAuthority
from continuity_engine.domain.contradiction import ClaimProjection, ClaimPolarity, ClaimEvidenceType, ClaimDomain
from continuity_engine.domain.thinking import ThinkingResult
from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.interfaces.local_integration_app import build_local_integration_app
from continuity_engine.services.action_planning_service import ActionCapabilityBinding
from continuity_engine.services.context_router_service import EnginePrivateContextPermissionPolicy, ContextPermissionDecision
from continuity_engine.services.continuity_core_runtime import build_continuity_core, ContinuityCorePermissionPolicy
from continuity_engine.services.continuity_core_service import ContinuityCoreGates
from .sandbox import P01SandboxManager
from .models import StateFixture
from .interaction import _build_request, SandboxContractValidator, SandboxFirstRoundResultFactory
from .p08_action_fixture import FakeActionAdapter


P09_FIXTURE_VERSION = "p09-c1-golden-v1"
P09_TIME = datetime(2026, 9, 4, 8, tzinfo=timezone.utc)


class CoreConstraints:
    def __init__(self):
        self.context_allowed = True
        self.confirmation_allowed = True
        self.recovery_ready = True
        self.reality_ready = True
        self.confirmed_ids = set()

    def validate_context(self, context):
        return self.context_allowed

    def confirmed(self, request):
        # Explicit fixture confirmation binds the exact request key.
        return self.confirmation_allowed and request.idempotency_key in self.confirmed_ids

    def recoverable(self, request):
        return self.recovery_ready

    def reality_allowed(self, request):
        return self.reality_ready


class CorePermissions(ContinuityCorePermissionPolicy):
    def __init__(self):
        self.allowed = True
        self.calls = 0
        self.references_allowed = True

    def authorize_source(self, request, source_id, partition):
        self.calls += 1
        return ContextPermissionDecision(self.allowed, "SOURCE_AUTHORIZED" if self.allowed else "PERMISSION_DENIED", "p09-test-v1")

    def authorize_reference(self, request, reference):
        if not self.references_allowed:
            return ContextPermissionDecision(False, "REFERENCE_REVOKED", "p09-test-v1")
        return super().authorize_reference(request, reference)


class CoreClaims:
    def project(self, fragment):
        if fragment.authority is ContextAuthority.CONFIRMED_STATE and fragment.stable_source_id.endswith(":relationship"):
            return ClaimProjection("relationship.status", json.loads(fragment.content)["current_status"],
                                   ClaimPolarity.AFFIRMS, ClaimEvidenceType.ANALYTICAL,
                                   ClaimDomain.COGNITIVE, "relationship.current")
        return None


class CoreThinkingProvider:
    provider_id = "p09-context-thinking-fixture-v1"

    def __init__(self, mode="direct"):
        self.mode = mode
        self.calls = 0
        self.inputs = []

    def think(self, perception, budget):
        self.calls += 1
        self.inputs.append(perception)
        core = perception.continuity_context
        sources = ([f.stable_source_id for f in core.composition.snapshot.fragments] if core else [])
        return ThinkingResult.create(
            provider_id=self.provider_id, result_summary="C1 sources: " + ",".join(sources),
            rationale_summary="Bounded composed sources retain their original authority.",
            generated_new_thought=True, update_subject_state=False,
            request_more_memory=self.mode in {"information", "complex"},
            additional_memory_query="continuity" if self.mode in {"information", "complex"} else None,
            should_wait=self.mode == "silence", suggest_future_user_contact=self.mode == "complex",
            token_budget=budget,
        )


class ConfirmedFixturePolicy:
    """Test confirmation is explicit and recorded by exact idempotency identity."""
    def __init__(self, constraints, bindings):
        from continuity_engine.services.continuity_core_service import CoreDecisionPolicy
        self.delegate = CoreDecisionPolicy()
        self.producer_id = self.delegate.producer_id
        self.constraints, self.bindings = constraints, bindings

    def choose(self, operation, context, thinking, action):
        from continuity_engine.domain.action_capability import InternalActionRequest
        from continuity_engine.domain.action_planning import OptionalActionPlanner
        choice = self.delegate.choose(operation, context, thinking, action)
        if choice is not None:
            plan = OptionalActionPlanner().plan(choice)
            for step in choice.steps:
                b = next(b for b in self.bindings if b.capability == step.capability)
                r = InternalActionRequest(choice, step.step_id, plan.plan_id if plan else None,
                                          b.adapter.adapter_id, b.canonical_hash())
                self.constraints.confirmed_ids.add(r.idempotency_key)
        return choice


class P09Fixture:
    def __init__(self, root: Path, *, runtime=None, manager=None, mode="direct", gates=None,
                 thinking_mode=IntegrationThinkingMode.DETERMINISTIC, **core_options):
        self.root = root
        self.manager = manager or P01SandboxManager(root / "s", formal_data_roots=(root / "formal-canary",))
        self.runtime = runtime or self.manager.create_sandbox(frozen_at=P09_TIME)
        if runtime is None:
            self.runtime.apply_fixture(StateFixture(P09_FIXTURE_VERSION, ("continuity",), ("concise",),
                "testing continuity", ("synthetic genesis",), ("continuity",), ("synthetic fixture",)))
        self.mode, self.gates, self.core_options = mode, gates or ContinuityCoreGates(), core_options
        self.thinking_mode = thinking_mode
        self.constraints = CoreConstraints()
        self.permission = CorePermissions()
        self.reopen()
        if runtime is None:
            from .c1_snapshot import initialize_profile
            initialize_profile(self.runtime)

    def reopen(self):
        self.runtime = self.manager.open_runtime(self.runtime.descriptor.sandbox_id, branch_id=self.runtime.branch_id)
        self.adapter = FakeActionAdapter(self.runtime.data_root / "c1-receipts", clock=self.runtime.clock.now)
        self.provider = CoreThinkingProvider(self.mode)
        bindings = tuple(ActionCapabilityBinding(name, self.adapter, kind, permission, cost) for name,kind,permission,cost in (
            ("expression.emit", ActionType.CONTACT_USER, "expression:emit", 1),
            ("silence", ActionType.NO_ACTION, "action:silence", 0),
            ("memory.lookup", ActionType.REQUEST_MEMORY, "memory:request", 1),
            ("contact.send", ActionType.CONTACT_USER, "user:contact", 1)))
        def factory(**kwargs):
            self.core = build_continuity_core(**kwargs, environment="TEST", constraints=self.constraints,
                capabilities=bindings, claim_resolver=CoreClaims(), permission_policy=self.permission,
                gates=self.gates, policy=ConfirmedFixturePolicy(self.constraints, bindings), **self.core_options)
            return self.core
        self.app = build_local_integration_app(self.runtime.data_root, clock=self.runtime.clock.now,
            thinking_mode=self.thinking_mode, capability_thinking_provider_id="p09-model-capability-fixture-v1",
            thinking_provider=(self.provider if self.thinking_mode is IntegrationThinkingMode.DETERMINISTIC else None),
            continuity_core_factory=factory, contract_validator=SandboxContractValidator(),
            result_factory=SandboxFirstRoundResultFactory(), available_permissions=(
                "subject_state:update", "memory:request", "user:contact", "expression:emit", "action:silence", "test:lookup"))
        return self.app

    def request(self):
        return _build_request(self.runtime)

    def submit(self, request=None):
        return self.app.adapter.submit(request or self.request())

    def context(self, request):
        return self.app.ledger.load_operation(request["requestId"]).domain_progress.perception.continuity_context

    def event(self, event_id, *, content="continuity synthetic event", occurred_at=None,
              classification=None, references=(), mutations=()):
        from continuity_engine.domain.events import Event, EventClassification, EventSourceKind, StateSection
        now = self.runtime.clock.now()
        event = Event.create(event_id=event_id, occurred_at=occurred_at or now,
            observed_at=now, recorded_at=now, source="p09.synthetic-event",
            source_kind=EventSourceKind.TEST, event_type="c1_fixture",
            classification=classification or EventClassification.FACT, content=content,
            impact_scope=list(dict.fromkeys([StateSection.CONTINUITY,
                *(StateSection(m.field_path.split(".")[0]) for m in mutations)])), mutations=list(mutations),
            references=list(references), reason="Explicit C1 isolated event fixture.")
        return self.runtime.subject_states.apply_event(self.runtime.descriptor.subject_id, event)
