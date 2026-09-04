"""P08 internal choices and plan structure; never execution authority or state writes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from .capability import parse_capability_datetime
from .errors import CapabilityValidationError
from .integration_hashing import canonicalize_json, sha256_hash


def digest(value: object) -> str:
    return sha256_hash(canonicalize_json(value))


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise CapabilityValidationError("invalid internal action identity")


def hash_value(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise CapabilityValidationError("invalid internal action hash")


def exact(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise CapabilityValidationError("invalid internal action document shape")
    return value


@dataclass(frozen=True)
class ActionSpecification:
    step_id: str
    capability: str
    target: str
    argument_hash: str
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.step_id, self.capability, self.target):
            identifier(value)
        hash_value(self.argument_hash)
        if not isinstance(self.dependencies, tuple) or len(set(self.dependencies)) != len(self.dependencies):
            raise CapabilityValidationError("duplicate or invalid action dependencies")
        for value in self.dependencies:
            identifier(value)
        if self.step_id in self.dependencies:
            raise CapabilityValidationError("self dependency")
        if self.capability == "model.generate":
            raise CapabilityValidationError("MODEL_GENERATE_REMAINS_THINKING_DIRECT")

    def to_dict(self) -> dict:
        return {**asdict(self), "dependencies": list(self.dependencies)}

    @classmethod
    def from_dict(cls, value: dict) -> ActionSpecification:
        data = exact(value, {"step_id", "capability", "target", "argument_hash", "dependencies"})
        if not isinstance(data["dependencies"], list):
            raise CapabilityValidationError("dependencies must be an array")
        return cls(**{**data, "dependencies": tuple(data["dependencies"])})


@dataclass(frozen=True)
class ActionChoice:
    decision_id: str
    producer_id: str
    subject_id: str
    environment: str
    snapshot_hash: str
    source_revision: int
    source_fragment_ids: tuple[str, ...]
    trigger: str
    steps: tuple[ActionSpecification, ...]
    created_at: str
    expires_at: str
    requires_planning: bool = False

    def __post_init__(self) -> None:
        for value in (self.decision_id, self.producer_id, self.subject_id):
            identifier(value)
        if self.environment not in {"TEST", "RESEARCH"}:
            raise CapabilityValidationError("P08 internal choices require TEST/RESEARCH")
        if self.trigger not in {"INFORMATION_NEED", "ACTION_INTENT"}:
            raise CapabilityValidationError("a structured Thinking need/decision is required")
        hash_value(self.snapshot_hash)
        if type(self.source_revision) is not int or self.source_revision < 0:
            raise CapabilityValidationError("invalid choice revision")
        if type(self.requires_planning) is not bool:
            raise CapabilityValidationError("invalid planning requirement")
        if not self.source_fragment_ids or len(set(self.source_fragment_ids)) != len(self.source_fragment_ids):
            raise CapabilityValidationError("missing or duplicate source fragments")
        for value in self.source_fragment_ids:
            identifier(value)
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= 32:
            raise CapabilityValidationError("choice must have 1..32 bounded steps")
        seen: set[str] = set()
        for step in self.steps:
            if not isinstance(step, ActionSpecification) or step.step_id in seen:
                raise CapabilityValidationError("invalid or duplicate step")
            if not set(step.dependencies) <= seen:
                raise CapabilityValidationError("forward or missing dependency")
            seen.add(step.step_id)
        if parse_capability_datetime(self.expires_at) <= parse_capability_datetime(self.created_at):
            raise CapabilityValidationError("invalid choice lifetime")

    @property
    def complex(self) -> bool:
        return self.requires_planning or len(self.steps) != 1 or bool(self.steps[0].dependencies)

    def to_dict(self) -> dict:
        return {**asdict(self), "source_fragment_ids": list(self.source_fragment_ids),
                "steps": [step.to_dict() for step in self.steps]}

    def canonical_hash(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: dict) -> ActionChoice:
        data = exact(value, set(cls.__dataclass_fields__))
        if not isinstance(data["steps"], list) or not isinstance(data["source_fragment_ids"], list):
            raise CapabilityValidationError("invalid choice arrays")
        return cls(**{**data, "steps": tuple(ActionSpecification.from_dict(x) for x in data["steps"]),
                      "source_fragment_ids": tuple(data["source_fragment_ids"])})


@dataclass(frozen=True)
class AutonomousActionPlan:
    """Rebuildable structure, with no independent execution status or result ledger."""
    plan_id: str
    choice_hash: str
    step_ids: tuple[str, ...]


class OptionalActionPlanner:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def plan(self, choice: ActionChoice, *, capability_requires_plan: bool = False) -> AutonomousActionPlan | None:
        if not choice.complex and not capability_requires_plan:
            return None
        if not self.enabled:
            raise CapabilityValidationError("PLANNER_REQUIRED")
        return AutonomousActionPlan(
            "plan:" + choice.canonical_hash()[7:], choice.canonical_hash(),
            tuple(step.step_id for step in choice.steps),
        )
