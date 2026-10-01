"""Current W04 attachment checks around existing ingress and E5-A execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from continuity_engine.domain.action_planning import identifier
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.environment_access import (
    Attachment, AttachmentKind, AttachmentUse, BodyKind, DiscoveryState,
    EnvironmentAccessError, MigrationPreparation, SensationSource,
)


def _time(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise EnvironmentAccessError("W04_CLOCK_INVALID")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class SensorObservation:
    observation_id: str
    subject_id: str
    environment: str
    body_id: str
    generation: int
    ability_name: str
    value: float | None
    unit: str | None
    observed_at: str
    source: SensationSource

    def __post_init__(self):
        for value in (self.observation_id, self.subject_id, self.body_id, self.ability_name):
            identifier(value)
        if not isinstance(self.source, SensationSource):
            raise EnvironmentAccessError("W04_SENSATION_SOURCE")
        if self.value is not None and (type(self.value) not in (int, float) or not isfinite(self.value)):
            raise EnvironmentAccessError("W04_SENSOR_VALUE_INVALID")
        parse_capability_datetime(self.observed_at)


class EnvironmentAccessService:
    """Attachment metadata is a gate, never a grant or historical fact source."""

    def __init__(self, repository, *, clock, authorize, connected, authorize_view=None):
        self.repository = repository
        self.clock = clock
        self.authorize = authorize
        self.connected = connected
        self.authorize_view = authorize_view

    def _now(self):
        return _time(self.clock())

    def _available(self, attachment, *, purpose, scope=None, document=None):
        document = self.repository.load() if document is None else document
        current = next((row for row in document["attachments"]
                        if row["attachment_id"] == attachment.attachment_id), None)
        if current != attachment.to_dict():
            return "CHANGED_DURING_CHECK"
        if attachment.state is not DiscoveryState.CONNECTED:
            return "NOT_CONNECTED"
        if not attachment.enabled:
            return "REVOKED"
        if (attachment.host_id, attachment.generation) != (document["active_host"], document["generation"]):
            return "OLD_HOST_FENCED"
        now = self._now()
        if now < parse_capability_datetime(attachment.valid_from) or now >= parse_capability_datetime(attachment.expires_at):
            return "EXPIRED"
        if purpose not in attachment.purposes or (scope is not None and scope not in attachment.read_scopes):
            return "SCOPE_DENIED"
        try:
            if self.connected(attachment) is not True:
                return "DISCONNECTED"
            if self.authorize(attachment, purpose=purpose, scope=scope, at=now) is not True:
                return "PERMISSION_DENIED"
        except Exception:
            raise EnvironmentAccessError("W04_CURRENT_PORT_UNAVAILABLE") from None
        latest = self.repository.load()
        if ((latest["active_host"], latest["generation"]) != (attachment.host_id, attachment.generation)
                or latest.get('entry_bindings') != document.get('entry_bindings')
                or latest.get('contact_pauses') != document.get('contact_pauses')
                or next((row for row in latest["attachments"]
                         if row["attachment_id"] == attachment.attachment_id), None) != attachment.to_dict()):
            return "CHANGED_DURING_CHECK"
        return "CURRENTLY_AVAILABLE"

    def require(self, use: AttachmentUse, *, kinds):
        if not isinstance(use, AttachmentUse):
            raise EnvironmentAccessError("W04_USE_REQUIRED")
        if (use.subject_id, use.environment) != (self.repository.subject_id, self.repository.environment):
            raise EnvironmentAccessError("W04_USE_BOUNDARY")
        return self._require_from_document(use, kinds=kinds, document=self.repository.load())

    def _require_from_document(self, use: AttachmentUse, *, kinds, document):
        """One check can reuse its already read pre-callback document.

        _available still rereads current bytes after every external callback.
        Even a stale/forged document cannot pass that exact attachment binding.
        No authorization result survives this invocation.
        """
        if not isinstance(use, AttachmentUse):
            raise EnvironmentAccessError("W04_USE_REQUIRED")
        if (use.subject_id, use.environment) != (self.repository.subject_id, self.repository.environment):
            raise EnvironmentAccessError("W04_USE_BOUNDARY")
        # Repository has verified the complete document. Construct the selected
        # value only; _available rechecks it against current bytes after ports.
        row=next((row for row in document["attachments"] if row['attachment_id']==use.attachment_id),None)
        item=Attachment.from_dict(row) if row is not None else None
        if item is None or item.kind not in kinds:
            raise EnvironmentAccessError("W04_ATTACHMENT_MISSING")
        if (item.subject_id, item.environment, item.generation, item.host_id, item.channel_id,
                item.software_id, item.device_id, item.account_id, item.session_id) != (
                use.subject_id, use.environment, use.generation, use.host_id, use.channel_id,
                use.software_id, use.device_id, use.account_id, use.session_id):
            raise EnvironmentAccessError("W04_USE_BINDING")
        reason = self._available(item, purpose=use.purpose, scope=use.scope, document=document)
        if reason != "CURRENTLY_AVAILABLE":
            raise EnvironmentAccessError("W04_" + reason)
        return item

    def require_ingress(self, use, *, subject_id, environment, conversation_id):
        if not isinstance(use, AttachmentUse) or (use.subject_id, use.environment) != (subject_id, environment):
            raise EnvironmentAccessError("W04_INGRESS_BINDING")
        item = self.require(use, kinds={AttachmentKind.MESSAGE_INGRESS, AttachmentKind.ENGINE_INTEGRATION})
        identifier(conversation_id)
        # A session may contain multiple conversations. The formal v1 message
        # carries conversation identity, while the trusted attachment supplies
        # account/device/session binding; W04-4 will join topic continuity.
        return item

    def require_action(self, use, route, request):
        if not isinstance(use, AttachmentUse) or (use.subject_id, use.environment) != (route.subject_id, route.environment):
            raise EnvironmentAccessError("W04_ACTION_BINDING")
        item = self.require(use, kinds={AttachmentKind.TOOL_EGRESS, AttachmentKind.BODY})
        if request.subject_id != item.subject_id or request.choice.environment != item.environment:
            raise EnvironmentAccessError("W04_ACTION_BOUNDARY")
        if item.kind is AttachmentKind.BODY and (item.device_id != route.asset or item.body_kind is not BodyKind.SIMULATED):
            raise EnvironmentAccessError("W04_BODY_ACTION_NOT_READY")
        ability = next((a for a in item.abilities
                        if a.name == route.capability_ref and a.direction == "OUTPUT"), None)
        if ability is None:
            raise EnvironmentAccessError("W04_ACTION_ABILITY_MISSING")
        if ability.valid_until is not None and parse_capability_datetime(ability.valid_until) <= self._now():
            raise EnvironmentAccessError("W04_ACTION_ABILITY_EXPIRED")
        if item.kind is AttachmentKind.TOOL_EGRESS and item.software_id != route.asset:
            raise EnvironmentAccessError("W04_TOOL_ROUTE_BINDING")
        return item

    def select(self, uses, *, kinds):
        """Choose a current route; selection itself never executes or grants."""
        rejected = []
        for use in uses:
            try:
                return self.require(use, kinds=kinds), tuple(rejected)
            except EnvironmentAccessError as exc:
                rejected.append((use.attachment_id if isinstance(use, AttachmentUse) else "INVALID", str(exc)))
        raise EnvironmentAccessError("W04_NO_CURRENT_ROUTE")

    def snapshot(self, *, subject_id, environment):
        """Read-only current status; never grants an ability by listing it."""
        if (subject_id, environment) != (self.repository.subject_id, self.repository.environment):
            raise EnvironmentAccessError("W04_VIEW_BOUNDARY")
        if self.authorize_view is None:
            raise EnvironmentAccessError("W04_VIEW_PERMISSION_UNAVAILABLE")
        try:
            allowed = self.authorize_view(subject_id, environment, at=self._now())
        except Exception:
            raise EnvironmentAccessError("W04_VIEW_PERMISSION_UNAVAILABLE") from None
        if allowed is not True:
            raise EnvironmentAccessError("W04_VIEW_PERMISSION_DENIED")
        result = []
        for row in self.repository.load()["attachments"]:
            item = Attachment.from_dict(row)
            reason = (self._available(item, purpose=item.purposes[0]) if item.purposes
                      else "SCOPE_DENIED")
            result.append({"attachment_id": item.attachment_id, "kind": item.kind.value,
                           "body_kind": item.body_kind.value, "discovery": item.state.value,
                           "current_status": reason, "subject_id": item.subject_id,
                           "environment": item.environment, "host_id": item.host_id,
                           "channel_id": item.channel_id, "device_id": item.device_id,
                           "account_id": item.account_id, "session_id": item.session_id,
                           "generation": item.generation, "purposes": item.purposes,
                           "read_scopes": item.read_scopes,
                           "abilities": tuple(a.to_dict() for a in item.abilities)})
        try:
            still_allowed = self.authorize_view(subject_id, environment, at=self._now())
        except Exception:
            raise EnvironmentAccessError("W04_VIEW_PERMISSION_UNAVAILABLE") from None
        if still_allowed is not True:
            raise EnvironmentAccessError("W04_VIEW_PERMISSION_CHANGED")
        return tuple(result)

    def body_state(self, *, subject_id, environment):
        bodies = [row for row in self.snapshot(subject_id=subject_id, environment=environment)
                  if row["kind"] == AttachmentKind.BODY.value]
        current = [row for row in bodies if row["current_status"] == "CURRENTLY_AVAILABLE"]
        if len(current) > 1:
            raise EnvironmentAccessError("W04_BODY_AMBIGUOUS")
        if not bodies:
            return {"kind": BodyKind.NONE.value, "status": "NO_BODY", "abilities": ()}
        row = current[0] if current else bodies[-1]
        return {"kind": row["body_kind"], "status": row["current_status"],
                "device_id": row["device_id"], "generation": row["generation"],
                "abilities": row["abilities"]}

    def validate_sensor(self, use, observation: SensorObservation):
        item = self.require(use, kinds={AttachmentKind.BODY})
        if item.body_kind is not BodyKind.SIMULATED or observation.source is not SensationSource.BODY_OBSERVATION:
            raise EnvironmentAccessError("W04_SENSOR_SOURCE_INVALID")
        if (observation.subject_id, observation.environment, observation.body_id, observation.generation) != (
                item.subject_id, item.environment, item.device_id, item.generation):
            raise EnvironmentAccessError("W04_SENSOR_BINDING")
        ability = next((a for a in item.abilities if a.name == observation.ability_name and a.direction == "INPUT"), None)
        if ability is None or observation.unit != ability.unit:
            raise EnvironmentAccessError("W04_SENSOR_ABILITY")
        if observation.value is not None and ((ability.lower is not None and observation.value < ability.lower)
                                              or (ability.upper is not None and observation.value > ability.upper)):
            raise EnvironmentAccessError("W04_SENSOR_RANGE")
        if parse_capability_datetime(observation.observed_at) > self._now():
            raise EnvironmentAccessError("W04_SENSOR_FUTURE")
        if ability.valid_until is not None and parse_capability_datetime(ability.valid_until) <= self._now():
            raise EnvironmentAccessError("W04_SENSOR_EXPIRED")
        return observation

    def prepare_migration(self, *, kind, subject_id, source_host, target_host, source_time_ref,
                          available, required):
        document = self.repository.load()
        if subject_id != self.repository.subject_id:
            raise EnvironmentAccessError("W04_MIGRATION_SUBJECT")
        if kind == "SAME_SUBJECT_TRANSFER" and source_host != document["active_host"]:
            raise EnvironmentAccessError("W04_MIGRATION_OLD_HOST")
        available, required = tuple(available), tuple(required)
        for value in (*available, *required):
            identifier(value)
        missing = tuple(sorted(set(required) - set(available)))
        status = "DEPENDENCY_MISSING" if missing else ("ENTRY_ONLY" if kind == "ENTRY_SWITCH"
                 else "READY_FOR_ISOLATED_HANDOFF" if kind == "SAME_SUBJECT_TRANSFER"
                 else "NOT_READY_PRODUCTION")
        return MigrationPreparation(kind, subject_id, self.repository.environment, source_host,
                                    target_host, source_time_ref, available, required, missing,
                                    document["generation"] if kind == "SAME_SUBJECT_TRANSFER" else None, status)

    def handoff_isolated(self, preparation, *, expected_revision):
        if not isinstance(preparation, MigrationPreparation) or preparation.status != "READY_FOR_ISOLATED_HANDOFF":
            raise EnvironmentAccessError("W04_HANDOFF_NOT_READY")
        if (preparation.subject_id, preparation.environment) != (self.repository.subject_id, self.repository.environment):
            raise EnvironmentAccessError("W04_HANDOFF_BINDING")
        if preparation.kind != "SAME_SUBJECT_TRANSFER" or preparation.missing:
            raise EnvironmentAccessError("W04_HANDOFF_NOT_READY")
        now = self.repository.load()
        if preparation.source_generation != now["generation"] or preparation.source_host != now["active_host"]:
            raise EnvironmentAccessError("W04_HANDOFF_STALE")
        return self.repository.handoff_test(preparation.source_host, preparation.target_host,
                                            expected_revision=expected_revision)
