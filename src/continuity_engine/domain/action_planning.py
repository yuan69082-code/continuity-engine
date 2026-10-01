"""P08 internal choices and plan structure; never execution authority or state writes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from contextvars import ContextVar
import re

from .capability import parse_capability_datetime
from .errors import CapabilityValidationError
from .integration_hashing import canonicalize_json, sha256_hash


_DIGEST_READS = ContextVar('action_value_digest_reads', default=None)


def _digest_key(value):
    """Exact typed content, never object identity or a cached authorization."""
    kind=type(value)
    if kind is dict:
        if any(type(key) is not str for key in value):raise TypeError()
        return ('object',tuple(sorted((key,_digest_key(item)) for key,item in value.items())))
    if kind in (list,tuple):return ('array',tuple(_digest_key(item) for item in value))
    if kind in (str,int,bool,type(None)):return (kind,value)
    if kind is float:return (kind,value.hex())
    raise TypeError()


@contextmanager
def verified_digest_reads():
    """Optional one-preparation pure-value memo. No persistence or grants."""
    token=_DIGEST_READS.set({})
    try:yield
    finally:_DIGEST_READS.reset(token)


def digest(value: object) -> str:
    memo=_DIGEST_READS.get()
    if memo is None:return sha256_hash(canonicalize_json(value))
    try:key=_digest_key(value)
    except (TypeError,ValueError,RecursionError):return sha256_hash(canonicalize_json(value))
    if key in memo:return memo[key]
    result=sha256_hash(canonicalize_json(value))
    # Bound infrastructure memory without changing any retrieval/work budget.
    if len(memo)<2048:memo[key]=result
    return result


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
    input_payload: dict | None = None

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
        if self.input_payload is not None:
            if self.capability.startswith('tool.'):
                from .temporary_tools import ToolCommand
                command = ToolCommand.from_dict(self.input_payload)
                if command.capability != self.capability or command.hash != self.argument_hash:
                    raise CapabilityValidationError('TOOL_INPUT_BINDING_INVALID')
            elif self.capability.startswith('device.'):
                from .device_operation import DeviceCommand
                command = DeviceCommand.from_dict(self.input_payload)
                if (not command.accepts_capability(self.capability) or command.hash != self.argument_hash
                        or command.to_dict() != self.input_payload):
                    raise CapabilityValidationError('DEVICE_INPUT_BINDING_INVALID')
            else:
                from .external_capabilities import QueryInput
                if not self.capability.startswith('external.') or digest(QueryInput.from_dict(self.input_payload).to_dict())!=self.argument_hash:
                    raise CapabilityValidationError('EXTERNAL_INPUT_BINDING_INVALID')
        elif self.capability.startswith(('device.', 'tool.')):
            raise CapabilityValidationError('DEVICE_INPUT_REQUIRED')

    def to_dict(self) -> dict:
        value={**asdict(self), "dependencies": list(self.dependencies)}
        if self.input_payload is None:value.pop('input_payload')
        return value

    @classmethod
    def from_dict(cls, value: dict) -> ActionSpecification:
        keys={"step_id", "capability", "target", "argument_hash", "dependencies"}
        if isinstance(value,dict) and 'input_payload' in value:keys.add('input_payload')
        data = exact(value, keys)
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
