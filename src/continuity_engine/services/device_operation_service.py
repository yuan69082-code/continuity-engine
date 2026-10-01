"""Thin controlled device bridge. No Subject state, request store, or worker."""
from dataclasses import asdict, replace
from datetime import timedelta
import json

from continuity_engine.domain.action_capability import ActionReceipt, ReceiptQuery
from continuity_engine.domain.action_planning import ActionSpecification, digest
from continuity_engine.domain.capability import parse_capability_datetime
from continuity_engine.domain.device_operation import DeviceCommand, DeviceObservation
from continuity_engine.domain.environment_access import AttachmentKind, EnvironmentAccessError, SensationSource
from continuity_engine.domain.perception import PerceivedPlatformFact
from continuity_engine.services.perception_service import PerceptionService


class DeviceOperationService:
    def __init__(self, *, access, port, clock, subject_states, authorize_history,
                 sensor_max_age=timedelta(seconds=30), connection_guard=None):
        self.access, self.port, self.clock = access, port, clock
        self.subject_states, self.authorize_history = subject_states, authorize_history
        self.subject_id, self.environment = port.subject_id, port.environment
        self.adapter_id, self.world, self.version = port.adapter_id, port.world, port.version
        self.execution = None
        self.connection_guard = connection_guard
        if not isinstance(sensor_max_age, timedelta) or sensor_max_age.total_seconds() <= 0:
            raise EnvironmentAccessError("DEVICE_SENSOR_TIME_POLICY")
        self.sensor_max_age = sensor_max_age

    @staticmethod
    def _call(code, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            raise EnvironmentAccessError(code) from None

    def _active(self, use):
        if (use.subject_id, use.environment) != (self.subject_id, self.environment):
            raise EnvironmentAccessError("DEVICE_SUBJECT_BOUNDARY")
        self.subject_states.require_active(self.subject_id, self.environment)

    def observe(self, use):
        self._active(use)
        if use.scope is None:
            raise EnvironmentAccessError("DEVICE_READ_SCOPE_REQUIRED")
        self.access.require(use, kinds={AttachmentKind.TOOL_EGRESS, AttachmentKind.BODY})
        if self.connection_guard is not None:
            self.connection_guard.observe(use)
        observation = self._call("DEVICE_OBSERVATION_UNAVAILABLE", self.port.observe, use)
        if not isinstance(observation, DeviceObservation) or observation.use != use:
            raise EnvironmentAccessError("DEVICE_OBSERVATION_BINDING")
        if self.execution is not None:
            self.execution.validate_input_material(observation.to_dict())
        self.access.require(use, kinds={AttachmentKind.TOOL_EGRESS, AttachmentKind.BODY})
        self._active(use)
        if self.connection_guard is not None:
            self.connection_guard.observe(use)
        return DeviceObservation.from_dict(observation.to_dict())

    def step(self, command, *, step_id="step-0", dependencies=(), capability=None):
        command = DeviceCommand.from_dict(command.to_dict())
        use = command.observation.use
        target = use.device_id if command.operation == "body.act" else use.software_id
        return ActionSpecification(step_id, capability or command.capability, target, command.hash,
                                   dependencies, command.to_dict())

    def command(self, request):
        command = DeviceCommand.from_dict(request.step.input_payload)
        use = command.observation.use
        target = use.device_id if command.operation == "body.act" else use.software_id
        if not command.accepts_capability(request.capability_type) or (
                command.hash, target, use.subject_id, use.environment, request.adapter_id) != (
                request.step.argument_hash, request.step.target, request.subject_id, request.choice.environment, self.adapter_id):
            raise EnvironmentAccessError("DEVICE_REQUEST_BINDING")
        return command

    def _history_allowed(self, command):
        if command.operation != "query":
            return
        if self._call("DEVICE_HISTORY_PERMISSION_UNAVAILABLE", self.authorize_history,
                      command.history_scope(), at=self.clock()) is not True:
            raise EnvironmentAccessError("DEVICE_HISTORY_PERMISSION_DENIED")

    def current(self, request, *, purpose):
        try:
            self._current(request, purpose=purpose)
        except EnvironmentAccessError as exc:
            stale = {"W04_REVOKED", "W04_EXPIRED", "W04_OLD_HOST_FENCED", "W04_DISCONNECTED",
                "W04_NOT_CONNECTED", "W04_PERMISSION_DENIED", "W04_SCOPE_DENIED", "W04_ABILITY_EXPIRED",
                "DEVICE_HISTORY_PERMISSION_DENIED", "DEVICE_HISTORY_SOURCE_CHANGED",
                "ENTRY_BINDING_EXPIRED", "ENTRY_BOUND_CONTEXT_CHANGED", "ENTRY_READ_DENIED",
                "ENTRY_CONTACT_TRANSFER_DENIED", "ENTRY_DELIVERY_SOURCE_DENIED", "ENTRY_DELIVERY_BINDING_STALE"}
            if purpose == "consume" and str(exc) in stale:
                from continuity_engine.domain.execution import ExecutionError
                raise ExecutionError("DEVICE_SOURCE_NOT_CURRENT") from None
            raise

    def _current(self, request, *, purpose):
        command = self.command(request)
        use = command.observation.use
        self._active(use)
        if self.execution is None:
            raise EnvironmentAccessError("DEVICE_EXECUTION_NOT_BOUND")
        route = self.execution.routes[request.capability_type]
        self.access.require_action(use, route, request)
        self._history_allowed(command)
        if command.entry_delivery is not None:
            entry = getattr(self.execution.core, 'entry_continuity', None)
            if entry is None:
                raise EnvironmentAccessError('ENTRY_CONTINUITY_NOT_READY')
            # Execution needs permission before observing the destination and
            # again after the last callback. Consumption does not observe or
            # send: its one full entry check belongs after those callbacks.
            if purpose == 'execute':
                entry.delivery_current(request, command, purpose=purpose)
        if self.connection_guard is not None:
            self.connection_guard(request, purpose=purpose)
        if purpose == "execute":
            now = self.clock()
            observation = command.observation
            if not parse_capability_datetime(observation.observed_at) <= now < parse_capability_datetime(observation.expires_at):
                raise EnvironmentAccessError("DEVICE_OBSERVATION_EXPIRED")
            current = self.observe(use)
            if current.status != "READY":
                raise EnvironmentAccessError("DEVICE_" + current.status)
            if current.state_hash != observation.state_hash:
                raise EnvironmentAccessError("DEVICE_REOBSERVE_REQUIRED")
        elif purpose == "consume" and command.operation == "query":
            if self._call("DEVICE_HISTORY_CURRENT_UNAVAILABLE", self.port.history_current, request, command) is not True:
                raise EnvironmentAccessError("DEVICE_HISTORY_SOURCE_CHANGED")
        self.access.require_action(use, route, request)
        self._active(use)
        if self.connection_guard is not None:
            self.connection_guard(request, purpose=purpose)
        if command.entry_delivery is not None:
            # Observation and connection callbacks may change entry permissions
            # while the page itself remains identical. Check them last inside
            # the original port-held final dispatch guard as well.
            entry.delivery_current(request, command, purpose=purpose)

    def query(self, request):
        command = self.command(request)
        fact = self._call("DEVICE_QUERY_UNAVAILABLE", self.port.query, request)
        if isinstance(fact, ActionReceipt):
            fact.validate_request(request)
            payload = self._call("DEVICE_RESULT_UNAVAILABLE", self.port.read_result, request)
            self._validate_result(request, command, fact, payload)
            return fact
        return ReceiptQuery.NOT_EXECUTED if fact is ReceiptQuery.NOT_EXECUTED else ReceiptQuery.UNKNOWN

    def execute(self, request):
        fact = self.query(request)
        if isinstance(fact, ActionReceipt):
            return fact
        if fact is not ReceiptQuery.NOT_EXECUTED:
            raise EnvironmentAccessError("DEVICE_RESULT_UNKNOWN")
        self.current(request, purpose="execute")
        # Port holds its device transaction during this final gate and compares
        # the actual page/connection before the native simulated operation.
        def guard():
            self.execution.current(request, self.execution.routes[request.capability_type], "execute")
        receipt = self._call("DEVICE_DELIVERY_UNKNOWN", self.port.execute, request, self.command(request), guard)
        verified = self.query(request)
        if not isinstance(verified, ActionReceipt) or verified != receipt:
            raise EnvironmentAccessError("DEVICE_RESULT_UNKNOWN")
        return verified

    def _validate_result(self, request, command, fact, payload):
        if self.execution is None:
            raise EnvironmentAccessError("DEVICE_EXECUTION_NOT_BOUND")
        self.execution.validate_input_material(fact.to_dict())
        self.execution.validate_input_material(payload)
        if digest(payload) != fact.output_hash or payload.get("request_hash") != request.request_hash:
            raise EnvironmentAccessError("DEVICE_RESULT_BINDING")
        try:
            result = json.loads(payload["content"])
            before = DeviceObservation.from_dict(result["before"])
            after = DeviceObservation.from_dict(result["after"])
        except Exception:
            raise EnvironmentAccessError("DEVICE_RESULT_SHAPE") from None
        if before != command.observation or after.use != before.use or after.status != "READY":
            raise EnvironmentAccessError("DEVICE_RESULT_OBSERVATION")
        if (after.revision != before.revision + 1 or
                parse_capability_datetime(after.observed_at) < parse_capability_datetime(before.observed_at)
                or set(result) != {"outcome", "before", "after", "records", "authority", "business_complete"}
                or result["authority"] != "SIMULATED_RESULT_OBSERVATION"
                or type(result["business_complete"]) is not bool):
            raise EnvironmentAccessError("DEVICE_RESULT_SHAPE")
        if fact.status == "SUCCEEDED":
            if result["outcome"] != command.expected_outcome:
                raise EnvironmentAccessError("DEVICE_RESULT_NOT_BUSINESS_SUCCESS")
            business = command.operation in {"save", "send", "body.act", 'message.send.api', 'message.send.ui'}
            if (result["business_complete"] != business or fact.effect_count != int(command.operation not in {"locate", "query"})):
                raise EnvironmentAccessError("DEVICE_RESULT_EFFECT_BINDING")
            if command.operation == "type" and after.view.get("draft") != command.text:
                raise EnvironmentAccessError("DEVICE_TYPE_NOT_VERIFIED")
            if command.operation == "click" and after.view.get("last_clicked") != command.target:
                raise EnvironmentAccessError("DEVICE_CLICK_NOT_VERIFIED")
            if command.operation == "scroll" and after.view.get("scroll") != before.view.get("scroll", 0) + command.amount:
                raise EnvironmentAccessError("DEVICE_SCROLL_NOT_VERIFIED")
            if command.operation == "locate" and command.target not in after.view.get("controls", []):
                raise EnvironmentAccessError("DEVICE_LOCATION_NOT_VERIFIED")
            if command.operation == "save" and after.view.get("saved") != before.view.get("draft"):
                raise EnvironmentAccessError("DEVICE_SAVE_NOT_VERIFIED")
            if command.operation == "send" and (after.view.get("sent") != before.view.get("draft")
                    or after.view.get("send_count") != before.view.get("send_count", 0) + 1):
                raise EnvironmentAccessError("DEVICE_SEND_NOT_VERIFIED")
            if command.operation == "body.act" and after.view.get("position") != before.view.get("position", 0) + command.amount:
                raise EnvironmentAccessError("DEVICE_BODY_RESULT_NOT_VERIFIED")
            if command.entry_delivery is not None:
                if (after.view.get('sent') != command.text or after.view.get('send_count') != before.view.get('send_count', 0) + 1
                        or after.view.get('recipient') != command.entry_delivery['entry_id']):
                    raise EnvironmentAccessError('DEVICE_ENTRY_SEND_NOT_VERIFIED')
                if command.operation == 'message.send.ui' and (
                        after.view.get('draft') != command.text or after.view.get('last_clicked') != command.target):
                    raise EnvironmentAccessError('DEVICE_ENTRY_UI_NOT_VERIFIED')
        elif result["outcome"] != "FAILED" or result["business_complete"] or fact.effect_count:
            raise EnvironmentAccessError("DEVICE_FAILURE_MISLABELLED")
        records = result["records"]
        if not isinstance(records, list) or (command.operation != "query" and records):
            raise EnvironmentAccessError("DEVICE_HISTORY_RESULT")
        if command.operation == "query":
            scope = command.history_scope()
            if len(records) > scope.limit:
                raise EnvironmentAccessError("DEVICE_HISTORY_RESULT_LIMIT")
            seen = set()
            for row in records:
                if not isinstance(row, dict) or any(row.get(k) != v for k, v in (
                        ("software_id", scope.software_id), ("device_id", scope.device_id),
                        ("session_id", scope.session_id), ("object_id", scope.object_id))):
                    raise EnvironmentAccessError("DEVICE_HISTORY_RESULT_SCOPE")
                from continuity_engine.domain.action_planning import identifier
                for key in ("source_id", "root_id", "version"):
                    identifier(row.get(key))
                identity = (row["source_id"], row["version"])
                if identity in seen or row.get("readable") is not True or row.get("content_hash") != digest(row.get("content")):
                    raise EnvironmentAccessError("DEVICE_HISTORY_RESULT_BINDING")
                seen.add(identity)
                at = parse_capability_datetime(row["occurred_at"])
                if (scope.source_ids and row["source_id"] not in scope.source_ids
                        or scope.from_at and at < parse_capability_datetime(scope.from_at)
                        or scope.until_at and at > parse_capability_datetime(scope.until_at)
                        or parse_capability_datetime(row["expires_at"]) <= parse_capability_datetime(fact.completed_at)):
                    raise EnvironmentAccessError("DEVICE_HISTORY_RESULT_TIME")

    def read_result(self, request):
        fact = self.query(request)
        if not isinstance(fact, ActionReceipt):
            raise EnvironmentAccessError("DEVICE_RESULT_UNKNOWN")
        return self._call("DEVICE_RESULT_UNAVAILABLE", self.port.read_result, request)

    def inspect(self, request_id):
        """Minimal read-only view; querying a fact never resumes an operation."""
        request = self.execution.request(request_id)
        self.execution.current(request, self.execution.route_for(request), "consume")
        fact = self.query(request)
        result = {"request_id": request_id, "status": fact.value if isinstance(fact, ReceiptQuery) else fact.status}
        if isinstance(fact, ActionReceipt):
            result.update(receipt_hash=fact.canonical_hash(), result=json.loads(self.read_result(request)["content"]))
        self.execution.current(request, self.execution.route_for(request), "consume")
        return result

    def perceive_sensor(self, use, observation, context):
        """Validated hardware observation → original Perception, no state writes."""
        self._active(use)
        self.access.validate_sensor(use, observation)
        if (context.subject_state.subject_id != use.subject_id or context.subject_state.revision !=
                self.subject_states.load(use.subject_id).revision):
            raise EnvironmentAccessError("DEVICE_SENSOR_CONTEXT")
        now = self.clock()
        observed = parse_capability_datetime(observation.observed_at)
        if now - observed >= self.sensor_max_age:
            raise EnvironmentAccessError("DEVICE_SENSOR_EXPIRED")
        item = self.access.require(use, kinds={AttachmentKind.BODY})
        ability = next(a for a in item.abilities if a.name == observation.ability_name)
        if ability.sampled_at is None or observed < parse_capability_datetime(ability.sampled_at):
            raise EnvironmentAccessError("DEVICE_SENSOR_EXPIRED")
        content = json.dumps({**asdict(observation), "source": SensationSource.BODY_OBSERVATION.value,
            "simulation": "TEST_SIMULATED", "coordinate": ability.coordinate,
            "authority": "OBSERVATION_NOT_SUBJECT_STATE"}, ensure_ascii=False, sort_keys=True)
        if self.execution is not None:
            self.execution.validate_input_material(content)
        fact = PerceivedPlatformFact(observation.observation_id, "body:" + observation.observation_id,
            "SIMULATED_BODY_OBSERVATION", observation.observation_id, use.session_id or use.attachment_id,
            observation.observation_id, digest([item.fingerprint, content]), content, observed, now)
        result = PerceptionService().perceive(replace(context, current_time=now,
            external_facts=(*context.external_facts, fact)), perception_id="perception:" + observation.observation_id)
        self.access.validate_sensor(use, observation)
        self._active(use)
        if self.subject_states.load(use.subject_id).revision != context.subject_state.revision:
            raise EnvironmentAccessError("DEVICE_SENSOR_CONTEXT_CHANGED")
        return result

    def history_context(self, request_id, perception):
        """Consume a scoped UI query via original result source, Router, Composer."""
        request = self.execution.request(request_id)
        command = self.command(request)
        if command.operation != "query":
            raise EnvironmentAccessError("DEVICE_HISTORY_QUERY_REQUIRED")
        self.inspect(request_id)
        core = self.execution.core
        if (perception.subject_id != self.subject_id or
                perception.source_revision != self.subject_states.load(self.subject_id).revision):
            raise EnvironmentAccessError("DEVICE_HISTORY_CONTEXT")
        from continuity_engine.domain.context_routing import ContextRouteStatus, RetrievalBudget
        from .execution_context_source import history_context_request_id
        routed = core.router.route(perception, request_id=history_context_request_id(request_id),
            environment=self.environment, budget=RetrievalBudget(total_candidate_limit=30),
            recall_terms=(command.history_scope().object_id,))
        if routed.trace.route_status is not ContextRouteStatus.COMPLETE:
            raise EnvironmentAccessError("DEVICE_HISTORY_ROUTING_BLOCKED")
        composed = core.composer.compose(routed, budget=core.context_budget)
        if composed.snapshot is None or not composed.snapshot.consumable or not any(
                f.stable_source_id == "execution:" + request_id for f in composed.snapshot.fragments):
            raise EnvironmentAccessError("DEVICE_HISTORY_CONTEXT_NOT_READY")
        self.inspect(request_id)
        if self.subject_states.load(self.subject_id).revision != perception.source_revision:
            raise EnvironmentAccessError("DEVICE_HISTORY_CONTEXT_CHANGED")
        return composed
