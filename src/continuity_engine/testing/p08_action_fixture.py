"""Versioned TEST-only P08 producer/constraints/Fake Adapter. No transports."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from continuity_engine.domain.action import ActionType, PermissionCheck
from continuity_engine.domain.action_planning import ActionChoice, ActionSpecification, OptionalActionPlanner, digest
from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest
from continuity_engine.domain.errors import CapabilityConflictError, CapabilityValidationError
from continuity_engine.services.action_planning_service import (
    ActionPlanningService, ActionCapabilityBinding, ReceiptQuery,
)
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.capability_coordination_service import CapabilityCoordinationService
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from .p06_context_fixture import run_p06_golden_scenario
from .persistence import atomic_write_json, read_json, assert_no_link_components, assert_descendant

P08_FIXTURE_VERSION = "p08-direct-planner-golden-v1"
P08_TIME = datetime(2026, 9, 4, 8, tzinfo=timezone.utc)


class FakeActionAdapter:
    """Atomic receipt IS the synthetic effect. This is not production exactly-once.

    Facts are independent Adapter receipts, not a second Engine request/retry ledger.
    Engine execution/attempt state is exclusively in its existing capability ledger.
    """
    adapter_id = "p08-fake-adapter-v1"

    def __init__(self, root: Path, *, clock=None):
        temp_root = Path(tempfile.gettempdir()).resolve()
        root = root.absolute()
        assert_no_link_components(root, stop_at=temp_root)
        assert_descendant(root.resolve(), temp_root)
        self.path = root / "p08-fake-receipts.json"
        self.execute_calls = 0
        self.query_calls = 0
        self.mode = "success"
        self.clock = clock
        if not self.path.exists():
            atomic_write_json(self.path, {"version": P08_FIXTURE_VERSION, "facts": [], "hash": digest([])})

    def receipts(self) -> tuple[ActionReceipt, ...]:
        data = read_json(self.path)
        if set(data) != {"version", "facts", "hash"} or data["version"] != P08_FIXTURE_VERSION or data["hash"] != digest(data["facts"]):
            raise CapabilityValidationError("Fake receipt store is invalid")
        facts = tuple(ActionReceipt.from_dict(x) for x in data["facts"])
        if len({x.capability_request_id for x in facts}) != len(facts):
            raise CapabilityValidationError("duplicate Fake receipt identity")
        return facts

    @property
    def effect_count(self):
        return sum(x.effect_count for x in self.receipts())

    @property
    def credits(self):
        return sum(x.test_credits for x in self.receipts())

    def query(self, request: InternalActionRequest):
        self.query_calls += 1
        for fact in self.receipts():
            if fact.capability_request_id == request.capability_request_id:
                fact.validate_request(request)
                return fact
        return ReceiptQuery.UNKNOWN if self.mode == "unknown" else ReceiptQuery.NOT_EXECUTED

    def execute(self, request: InternalActionRequest):
        self.execute_calls += 1
        existing = self.query(request)
        if isinstance(existing, ActionReceipt):
            return existing
        if existing is ReceiptQuery.UNKNOWN:
            raise CapabilityValidationError("cannot execute unknown Fake effect")
        if self.mode == "before_failure":
            raise RuntimeError("synthetic pre-execution failure")
        success = self.mode != "terminal"
        effects = int(success and request.capability_type not in {"silence", "action.stop", "test.lookup", "memory.lookup"})
        fact = ActionReceipt(
            "receipt:" + request.idempotency_key[7:], request.capability_request_id,
            request.request_hash, self.adapter_id, request.subject_id, request.choice.environment,
            request.step_id, "SUCCEEDED" if success else "FAILED_TERMINAL", effects, effects,
            (self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
             if self.clock is not None else "2026-09-04T08:00:00Z"),
            digest([request.step.argument_hash, success]),
        )
        facts = [x.to_dict() for x in self.receipts()] + [fact.to_dict()]
        atomic_write_json(self.path, {"version": P08_FIXTURE_VERSION, "facts": facts, "hash": digest(facts)})
        if self.mode == "lost_response":
            raise RuntimeError("synthetic response loss after atomic effect/receipt")
        return fact


class TestChoiceProducer:
    producer_id = "p08-test-thinking-v1"

    def __init__(self):
        self.choices: dict[str, ActionChoice] = {}

    def register(self, choice: ActionChoice):
        if choice.decision_id in self.choices and self.choices[choice.decision_id] != choice:
            raise CapabilityConflictError("test producer identity conflict")
        self.choices[choice.decision_id] = choice

    def resolve(self, decision_id):
        if decision_id not in self.choices:
            raise CapabilityValidationError("unregistered Thinking choice")
        return self.choices[decision_id]


class TestActionConstraints:
    def __init__(self, composition):
        self.context_hash = composition.canonical_hash()
        self.confirmed_ids = set()
        self.recovery_ready = True
        self.reality_ready = True

    def validate_context(self, context):
        return context.canonical_hash() == self.context_hash

    def confirmed(self, request):
        return request.idempotency_key in self.confirmed_ids

    def recoverable(self, request):
        return self.recovery_ready

    def reality_allowed(self, request):
        return self.reality_ready


class TestActionPermissions:
    def __init__(self):
        self.allowed = True
        self.calls = 0

    def check(self, permission, **kwargs):
        self.calls += 1
        return PermissionCheck(permission, True, self.allowed, False, False, False, True, "test permission")


class P08Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.p06 = run_p06_golden_scenario(root / "sources")
        self.context = self.p06.composition
        self.producer = TestChoiceProducer()
        self.constraints = TestActionConstraints(self.context)
        self.permissions = TestActionPermissions()
        self.adapter = FakeActionAdapter(root)
        self.ledger = JsonIntegrationResultLedger(root)
        self.ledger.initialize_empty()

    def bindings(self):
        return tuple(ActionCapabilityBinding(name, self.adapter, kind, permission, cost, atomic) for
                     name, kind, permission, cost, atomic in (
                         ("expression.emit", ActionType.CONTACT_USER, "expression:emit", 1, True),
                         ("contact.send", ActionType.CONTACT_USER, "user:contact", 1, True),
                         ("silence", ActionType.NO_ACTION, "action:silence", 0, True),
                         ("action.stop", ActionType.DEFER, "action:stop", 0, True),
                         ("test.lookup", ActionType.REQUEST_MEMORY, "test:lookup", 1, True),
                         ("test.write", ActionType.USE_TOOL, "test:write", 1, True),
                         ("test.complex", ActionType.USE_TOOL, "test:complex", 2, False),
                     ))

    def service(self, *, planner_enabled=True, limits=None, fault=None):
        return ActionPlanningService(
            coordination=CapabilityCoordinationService(self.ledger),
            action_gate=ActionService(self.permissions, None), producer=self.producer,
            constraints=self.constraints, capabilities=self.bindings(), clock=lambda: P08_TIME,
            subject_id=self.context.snapshot.subject_id, environment="TEST",
            planner=OptionalActionPlanner(enabled=planner_enabled), limits=limits, fault=fault,
        )

    def choice(self, identity="choice-one", capabilities=("contact.send",), trigger="ACTION_INTENT",
               requires_planning=False):
        snapshot = self.context.snapshot
        steps = tuple(ActionSpecification(f"step-{i}", capability, "test-target", digest(f"argument-{i}"),
                      (f"step-{i-1}",) if i else ()) for i, capability in enumerate(capabilities))
        choice = ActionChoice(identity, self.producer.producer_id, snapshot.subject_id, "TEST",
                              snapshot.snapshot_hash, snapshot.source_revision,
                              (snapshot.fragments[0].fragment_id,), trigger, steps,
                              "2026-09-04T07:00:00Z", "2026-09-05T07:00:00Z", requires_planning)
        self.producer.register(choice)
        plan = OptionalActionPlanner().plan(choice, capability_requires_plan=any(
            not x.atomic for x in self.bindings() if x.capability in capabilities))
        for step in steps:
            request = self.request(choice, step.step_id, plan.plan_id if plan else None)
            self.constraints.confirmed_ids.add(request.idempotency_key)
        return choice

    def request(self, choice, step_id=None, plan_id=None):
        step = next(x for x in choice.steps if x.step_id == (step_id or choice.steps[0].step_id))
        binding = next(x for x in self.bindings() if x.capability == step.capability)
        return InternalActionRequest(choice, step.step_id, plan_id, binding.adapter.adapter_id,
                                     binding.canonical_hash())
