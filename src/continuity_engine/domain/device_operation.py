"""Bounded internal device inputs. E5-A owns their identity and execution facts."""
from dataclasses import asdict, dataclass
import json
import math

from .action_planning import digest, exact, identifier
from .capability import parse_capability_datetime
from .environment_access import AttachmentUse, EnvironmentAccessError, HistoryScope


@dataclass(frozen=True)
class DeviceObservation:
    observation_id: str
    use: AttachmentUse
    observed_at: str
    expires_at: str
    page_id: str
    focus_id: str
    revision: int
    status: str
    view: dict

    def __post_init__(self):
        for item in (self.observation_id, self.page_id, self.focus_id):
            identifier(item)
        if not isinstance(self.use, AttachmentUse) or type(self.revision) is not int or self.revision < 0:
            raise EnvironmentAccessError("DEVICE_OBSERVATION_BINDING")
        if self.status not in {"READY", "OFFLINE", "LOCKED", "TAKEN_OVER", "UNOBSERVABLE"}:
            raise EnvironmentAccessError("DEVICE_OBSERVATION_STATUS")
        if parse_capability_datetime(self.expires_at) <= parse_capability_datetime(self.observed_at):
            raise EnvironmentAccessError("DEVICE_OBSERVATION_TIME")
        if not isinstance(self.view, dict):
            raise EnvironmentAccessError("DEVICE_OBSERVATION_VIEW")
        try:
            raw = json.dumps(self.view, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise EnvironmentAccessError("DEVICE_OBSERVATION_VIEW") from None
        if len(raw.encode("utf-8")) > 16384:
            raise EnvironmentAccessError("DEVICE_OBSERVATION_LIMIT")

    def to_dict(self):
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, value):
        d = exact(value, set(cls.__dataclass_fields__))
        return cls(**{**d, "use": AttachmentUse(**exact(d["use"], set(AttachmentUse.__dataclass_fields__)))})

    @property
    def state_hash(self):
        return digest([asdict(self.use), self.page_id, self.focus_id, self.revision, self.status, self.view])


@dataclass(frozen=True)
class DeviceCommand:
    version: str
    operation: str
    target: str
    text: str | None
    amount: float | None
    history: dict | None
    observation: DeviceObservation
    entry_delivery: dict | None = None

    def __post_init__(self):
        entry_send = self.operation in {'message.send.api', 'message.send.ui'}
        if (self.version != ('w04-device-v2' if entry_send else 'w04-device-v1') or self.operation not in {
                "locate", "click", "type", "scroll", "save", "send", "query", "body.act",
                'message.send.api', 'message.send.ui'}):
            raise EnvironmentAccessError("DEVICE_COMMAND_KIND")
        identifier(self.target)
        if not isinstance(self.observation, DeviceObservation):
            raise EnvironmentAccessError("DEVICE_COMMAND_OBSERVATION")
        if self.text is not None and (not isinstance(self.text, str) or len(self.text) > 2048):
            raise EnvironmentAccessError("DEVICE_COMMAND_TEXT")
        if (self.operation == "type" or entry_send) != (self.text is not None):
            raise EnvironmentAccessError("DEVICE_COMMAND_TEXT")
        if entry_send:
            link = exact(self.entry_delivery, {'request_id', 'entry_id', 'binding_hash', 'item_id', 'inquiry_id'})
            for key in ('request_id', 'entry_id', 'inquiry_id'):
                identifier(link[key])
            if link['item_id'] is not None:
                identifier(link['item_id'])
            if not isinstance(link['binding_hash'], str) or len(link['binding_hash']) != 71:
                raise EnvironmentAccessError('DEVICE_ENTRY_BINDING')
        elif self.entry_delivery is not None:
            raise EnvironmentAccessError('DEVICE_ENTRY_UNEXPECTED')
        if self.amount is not None and (type(self.amount) not in (int, float) or not math.isfinite(self.amount)):
            raise EnvironmentAccessError("DEVICE_COMMAND_AMOUNT")
        if (self.operation in {"scroll", "body.act"}) != (self.amount is not None):
            raise EnvironmentAccessError("DEVICE_COMMAND_AMOUNT")
        if self.operation == "query":
            scope = self.history_scope()
            use = self.observation.use
            if (scope.subject_id, scope.environment, scope.software_id, scope.device_id, scope.session_id) != (
                    use.subject_id, use.environment, use.software_id, use.device_id, use.session_id):
                raise EnvironmentAccessError("DEVICE_HISTORY_BINDING")
        elif self.history is not None:
            raise EnvironmentAccessError("DEVICE_HISTORY_UNEXPECTED")

    def history_scope(self):
        d = exact(self.history, set(HistoryScope.__dataclass_fields__))
        return HistoryScope(**{**d, "source_ids": tuple(d["source_ids"])})

    def to_dict(self):
        # JSON arrays must have identical types before and after E5-A recovery.
        value = {**asdict(self), "observation": self.observation.to_dict()}
        if self.entry_delivery is None:
            value.pop('entry_delivery')
        return json.loads(json.dumps(value,
                                    ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, value):
        d = exact(value, set(cls.__dataclass_fields__) if 'entry_delivery' in value else set(cls.__dataclass_fields__) - {'entry_delivery'})
        return cls(**{**d, "observation": DeviceObservation.from_dict(d["observation"])})

    @property
    def capability(self):
        return "device." + self.operation

    def accepts_capability(self, value):
        # Optional target-specific route retains the operation's meaning while
        # allowing multiple bodies/devices in the same existing registry.
        use = self.observation.use
        asset = use.device_id if self.operation == "body.act" else use.software_id
        return value in {self.capability, self.capability + ":" + digest(asset)[7:23]}

    @property
    def hash(self):
        return digest(self.to_dict())

    @property
    def expected_outcome(self):
        return {"locate": "LOCATED", "click": "CLICKED", "type": "TYPED", "scroll": "SCROLLED",
                "save": "SAVED", "send": "SENT", "query": "QUERIED", "body.act": "ACTUATED",
                'message.send.api': 'SENT', 'message.send.ui': 'SENT'}[self.operation]
