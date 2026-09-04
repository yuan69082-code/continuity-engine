"""Internal E5-A variant. Deliberately NOT an external Capability v1 document."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .action_planning import ActionChoice, digest, exact, hash_value, identifier
from .capability import CapabilityStatus, parse_capability_datetime
from .errors import CapabilityValidationError

INTERNAL_ACTION_VERSION = "engine-internal-action/v1"


class ReceiptQuery(str, Enum):
    """Typed Adapter query outcome; UNKNOWN is never proof of non-execution."""
    NOT_EXECUTED = "NOT_EXECUTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InternalActionRequest:
    choice: ActionChoice
    step_id: str
    plan_id: str | None
    adapter_id: str
    policy_hash: str

    def __post_init__(self) -> None:
        identifier(self.adapter_id)
        hash_value(self.policy_hash)
        if not isinstance(self.choice, ActionChoice) or self.step_id not in {x.step_id for x in self.choice.steps}:
            raise CapabilityValidationError("request recovery step is not in its choice")
        expected = "plan:" + self.choice.canonical_hash()[7:]
        if self.plan_id is not None and self.plan_id != expected:
            raise CapabilityValidationError("request plan identity mismatch")
        if self.choice.complex and self.plan_id is None:
            raise CapabilityValidationError("complex request requires plan")

    @property
    def step(self):
        return next(x for x in self.choice.steps if x.step_id == self.step_id)

    @property
    def operation_id(self) -> str:
        # Content deliberately excluded: reuse of identity with changed content conflicts.
        return "action-op:" + digest([self.choice.subject_id, self.choice.environment,
                                      self.choice.producer_id, self.choice.decision_id, self.step_id])[7:]

    @property
    def capability_request_id(self) -> str:
        return "action-cap:" + digest(self.operation_id)[7:]

    @property
    def request_id(self) -> str:
        return self.operation_id

    @property
    def request_hash(self) -> str:
        return digest([self.choice.canonical_hash(), self.step_id, self.plan_id,
                       self.adapter_id, self.policy_hash])

    @property
    def subject_id(self) -> str:
        return self.choice.subject_id

    @property
    def binding_id(self) -> str:
        return "internal:" + self.choice.producer_id

    @property
    def binding_version(self) -> int:
        return 1

    @property
    def capability_type(self) -> str:
        return self.step.capability

    @property
    def idempotency_key(self) -> str:
        return digest([self.capability_request_id, self.request_hash])

    def to_dict(self) -> dict:
        return {"internalVersion": INTERNAL_ACTION_VERSION, "choice": self.choice.to_dict(),
                "stepId": self.step_id, "planId": self.plan_id,
                "adapterId": self.adapter_id, "policyHash": self.policy_hash,
                "operationId": self.operation_id, "capabilityRequestId": self.capability_request_id,
                "requestHash": self.request_hash, "idempotencyKey": self.idempotency_key}

    @classmethod
    def from_dict(cls, value: dict) -> InternalActionRequest:
        data = exact(value, {"internalVersion", "choice", "stepId", "planId", "operationId",
                             "capabilityRequestId", "requestHash", "idempotencyKey", "adapterId", "policyHash"})
        result = cls(ActionChoice.from_dict(data["choice"]), data["stepId"], data["planId"],
                     data["adapterId"], data["policyHash"])
        if data != result.to_dict():
            raise CapabilityValidationError("internal request identity/hash mismatch")
        return result


@dataclass(frozen=True)
class ActionReceipt:
    """Adapter-reported fact; independent query verification is still required."""
    receipt_id: str
    capability_request_id: str
    request_hash: str
    adapter_id: str
    subject_id: str
    environment: str
    step_id: str
    status: str
    effect_count: int
    test_credits: int
    completed_at: str
    output_hash: str

    def __post_init__(self) -> None:
        for value in (self.receipt_id, self.capability_request_id, self.adapter_id, self.subject_id, self.step_id):
            identifier(value)
        for value in (self.request_hash, self.output_hash):
            hash_value(value)
        if self.environment not in {"TEST", "RESEARCH"} or self.status not in {"SUCCEEDED", "FAILED_TERMINAL"}:
            raise CapabilityValidationError("invalid receipt boundary/status")
        if type(self.effect_count) is not int or type(self.test_credits) is not int:
            raise CapabilityValidationError("invalid receipt counters")
        if self.effect_count not in {0, 1} or self.test_credits != self.effect_count:
            raise CapabilityValidationError("invalid synthetic usage")
        if self.status != "SUCCEEDED" and self.effect_count:
            raise CapabilityValidationError("failed receipt cannot claim successful test effect")
        parse_capability_datetime(self.completed_at)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> ActionReceipt:
        return cls(**exact(value, set(cls.__dataclass_fields__)))

    def canonical_hash(self) -> str:
        return digest(self.to_dict())

    def validate_request(self, request: InternalActionRequest) -> None:
        if self.adapter_id != request.adapter_id:
            raise CapabilityValidationError("receipt Adapter binding mismatch")
        if (self.capability_request_id, self.request_hash, self.subject_id, self.environment, self.step_id) != (
            request.capability_request_id, request.request_hash, request.subject_id,
            request.choice.environment, request.step_id,
        ):
            raise CapabilityValidationError("receipt recovery target mismatch")
        if parse_capability_datetime(self.completed_at) < parse_capability_datetime(request.choice.created_at):
            raise CapabilityValidationError("receipt precedes choice")


@dataclass(frozen=True)
class InternalActionResult:
    request: InternalActionRequest
    status: CapabilityStatus
    reason: str
    completed_at: str
    receipt: ActionReceipt | None = None
    gate_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.request, InternalActionRequest):
            raise CapabilityValidationError("internal result requires internal request")
        try:
            object.__setattr__(self, "status", CapabilityStatus(self.status))
        except (TypeError, ValueError) as exc:
            raise CapabilityValidationError("INTERNAL_ACTION_STATUS_UNSUPPORTED") from exc
        if self.status not in {CapabilityStatus.PROPOSED, CapabilityStatus.UNKNOWN,
                               CapabilityStatus.SUCCEEDED, CapabilityStatus.FAILED_TERMINAL,
                               CapabilityStatus.EXPIRED}:
            raise CapabilityValidationError("INTERNAL_ACTION_STATUS_UNSUPPORTED")
        identifier(self.reason)
        for reason in self.gate_reasons:
            identifier(reason)
        if parse_capability_datetime(self.completed_at) < parse_capability_datetime(self.request.choice.created_at):
            raise CapabilityValidationError("result precedes request")
        execution_result = self.status in {CapabilityStatus.SUCCEEDED, CapabilityStatus.FAILED_TERMINAL}
        if execution_result:
            if not isinstance(self.receipt, ActionReceipt) or self.reason != "VERIFIED_RECEIPT":
                raise CapabilityValidationError("EXECUTION_RESULT_REQUIRES_RECEIPT")
            self.receipt.validate_request(self.request)
            if self.receipt.status != self.status.value or parse_capability_datetime(self.receipt.completed_at) > parse_capability_datetime(self.completed_at):
                raise CapabilityValidationError("receipt status/time mismatch")
        elif self.receipt is not None:
            raise CapabilityValidationError("NON_EXECUTION_RESULT_CANNOT_CARRY_RECEIPT")
        if self.status is CapabilityStatus.EXPIRED:
            if (self.reason != "CHOICE_EXPIRED" or self.gate_reasons != ("CHOICE_EXPIRED",)
                    or parse_capability_datetime(self.completed_at) < parse_capability_datetime(self.request.choice.expires_at)):
                raise CapabilityValidationError("INVALID_LOCAL_EXPIRY_DECISION")
        elif self.status is CapabilityStatus.PROPOSED:
            if self.reason != "READY_TO_EXECUTE":
                raise CapabilityValidationError("INVALID_ACTION_PROPOSAL")
        elif self.status is CapabilityStatus.UNKNOWN:
            if self.reason in {"VERIFIED_RECEIPT", "CHOICE_EXPIRED", "READY_TO_EXECUTE"}:
                raise CapabilityValidationError("UNKNOWN_CANNOT_ASSERT_TERMINAL_EVIDENCE")

    @property
    def capability_result_id(self) -> str:
        return "action-result:" + digest(self.to_dict())[7:]

    @property
    def capability_request_id(self):
        return self.request.capability_request_id

    @property
    def operation_id(self):
        return self.request.operation_id

    @property
    def request_id(self):
        return self.request.request_id

    @property
    def request_hash(self):
        return self.request.request_hash

    @property
    def subject_id(self):
        return self.request.subject_id

    @property
    def binding_id(self):
        return self.request.binding_id

    @property
    def binding_version(self):
        return self.request.binding_version

    @property
    def capability_type(self):
        return self.request.capability_type

    def to_dict(self) -> dict:
        return {"internalVersion": INTERNAL_ACTION_VERSION, "request": self.request.to_dict(),
                "status": self.status.value, "reason": self.reason, "completedAt": self.completed_at,
                "receipt": self.receipt.to_dict() if self.receipt else None,
                "gateReasons": list(self.gate_reasons)}

    @classmethod
    def from_dict(cls, value: dict) -> InternalActionResult:
        data = exact(value, {"internalVersion", "request", "status", "reason", "completedAt", "receipt", "gateReasons"})
        if data["internalVersion"] != INTERNAL_ACTION_VERSION or not isinstance(data["gateReasons"], list):
            raise CapabilityValidationError("invalid internal result version/trace")
        return cls(InternalActionRequest.from_dict(data["request"]), data["status"], data["reason"],
                   data["completedAt"], ActionReceipt.from_dict(data["receipt"]) if data["receipt"] is not None else None,
                   tuple(data["gateReasons"]))


@dataclass(frozen=True)
class InternalActionAttempt:
    result_hash: str
    received_at: str
    result: InternalActionResult

    def __post_init__(self) -> None:
        # Same invariants at persistence append as at construction/reload.
        InternalActionResult.from_dict(self.result.to_dict())
        if self.result_hash != digest(self.result.to_dict()):
            raise CapabilityValidationError("internal attempt hash mismatch")
        if parse_capability_datetime(self.received_at) < parse_capability_datetime(self.result.completed_at):
            raise CapabilityValidationError("attempt received before completion")

    def to_dict(self) -> dict:
        return {"resultHash": self.result_hash, "receivedAt": self.received_at, "result": self.result.to_dict()}

    @classmethod
    def from_dict(cls, value: dict) -> InternalActionAttempt:
        data = exact(value, {"resultHash", "receivedAt", "result"})
        return cls(data["resultHash"], data["receivedAt"], InternalActionResult.from_dict(data["result"]))
