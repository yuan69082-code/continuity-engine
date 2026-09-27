"""Isolated simulated environment, not a second Engine state/result authority.

The durable device document is the Fake external app/body itself. E5-A owns
Engine requests/results; the app atomically changes its state and native receipt.
"""
from dataclasses import asdict, replace
from datetime import timedelta
import json
from pathlib import Path

from continuity_engine.domain.action_capability import ActionReceipt, InternalActionRequest, ReceiptQuery
from continuity_engine.domain.action_planning import ActionChoice, digest
from continuity_engine.domain.device_operation import DeviceCommand, DeviceObservation
from continuity_engine.domain.environment_access import (Ability, Attachment, AttachmentKind, AttachmentUse,
    BodyKind, DiscoveryState, EnvironmentAccessError, HistoryScope, SensationSource)
from continuity_engine.domain.execution import WorldCapability, BlastRadius, ExecutionError
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.services.action_planning_service import ActionPlanningService
from continuity_engine.services.continuity_core_service import _CurrentConstraints
from continuity_engine.services.device_operation_service import DeviceOperationService
from continuity_engine.services.environment_access_service import EnvironmentAccessService, SensorObservation
from continuity_engine.services.execution_service import ExecutionService
from continuity_engine.storage.json_environment_repository import JsonEnvironmentRepository
from continuity_engine.storage.json_execution_outbox import JsonExecutionOutbox
from .p08_action_fixture import _validate_fixture_root, TestChoiceProducer
from .p17_execution_fixture import P17Fixture


class SimulatedDeviceStore(JsonExecutionOutbox):
    def __init__(self, root, subject):
        _validate_fixture_root(root)
        super().__init__(root, subject_id=subject, environment="TEST")
        self.path = Path(root) / "simulated-device.json"

    def empty(self):
        return dict(subject_id=self.subject_id, environment="TEST", revision=0, page_id="page:editor",
            focus_id="focus:editor", status="READY", view=dict(controls=["control:edit", "control:save", "control:send"],
            draft="", saved="", sent="", send_count=0, position=0, scroll=0), history=[], facts=[], credits=0, effects=[])

    def load(self):
        self._safe()
        if not self.path.exists():
            return self.empty()
        try:
            e = json.loads(self.path.read_text(encoding="utf-8")); d = e["document"]
            if set(e) != {"document", "hash"} or e["hash"] != digest(d) or set(d) != set(self.empty()):
                raise ValueError()
            if (d["subject_id"], d["environment"]) != (self.subject_id, "TEST"):
                raise ValueError()
            ids = []; credits = 0; effects = []
            for row in d["facts"]:
                receipt = ActionReceipt.from_dict(row["receipt"])
                if digest(row["output"]) != receipt.output_hash or receipt.subject_id != self.subject_id:
                    raise ValueError()
                ids.append(receipt.capability_request_id); credits += receipt.test_credits
                if receipt.effect_count:
                    effects.append(receipt.capability_request_id)
            if len(ids) != len(set(ids)) or credits != d["credits"] or effects != d["effects"]:
                raise ValueError()
            return d
        except Exception:
            raise ExecutionError("SIMULATED_DEVICE_CORRUPT") from None


class SimulatedDevicePort:
    def __init__(self, root, *, subject, clock):
        self.store = SimulatedDeviceStore(root, subject)
        self.subject_id, self.environment, self.world, self.version = subject, "TEST", "TEST", "v1"
        self.adapter_id = "w04-simulated-device"
        self.clock = clock
        self.mode = "success"
        self.execute_calls = 0
        self.query_calls = 0
        self.before_action = None
        self.result_hook = None

    @property
    def credits(self):
        return self.store.load()["credits"]

    @property
    def effect_count(self):
        return len(self.store.load()["effects"])

    def change(self, **values):
        with self.store.transaction() as d:
            d.update(values); self.store.save(d)

    def observation(self, use, document):
        now = self.clock()
        return DeviceObservation("observation:" + digest([asdict(use), document["revision"],
            format_contract_datetime(now)])[7:], use, format_contract_datetime(now),
            format_contract_datetime(now + timedelta(seconds=30)), document["page_id"], document["focus_id"],
            document["revision"], document["status"], json.loads(json.dumps(document["view"])))

    def observe(self, use):
        return self.observation(use, self.store.load())

    def query(self, request):
        self.query_calls += 1
        if self.mode in {"unknown", "send_only"}:
            return ReceiptQuery.UNKNOWN
        for row in self.store.load()["facts"]:
            receipt = ActionReceipt.from_dict(row["receipt"])
            if receipt.capability_request_id == request.capability_request_id:
                receipt.validate_request(request)
                return receipt
        return ReceiptQuery.NOT_EXECUTED

    def _records(self, command, d):
        scope = command.history_scope()
        from continuity_engine.domain.capability import parse_capability_datetime
        begin = parse_capability_datetime(scope.from_at) if scope.from_at else None
        end = parse_capability_datetime(scope.until_at) if scope.until_at else None
        selected = []
        for row in d["history"]:
            if any(row.get(k) != v for k, v in (("software_id", scope.software_id),
                    ("device_id", scope.device_id), ("session_id", scope.session_id), ("object_id", scope.object_id))):
                continue
            at = parse_capability_datetime(row["occurred_at"])
            if (not row["readable"] or (scope.source_ids and row["source_id"] not in scope.source_ids)
                    or (begin and at < begin) or (end and at > end)
                    or self.clock() >= parse_capability_datetime(row["expires_at"])):
                continue
            selected.append({**json.loads(json.dumps(row)), "content_hash": digest(row["content"])})
            if len(selected) == scope.limit:
                break
        return selected

    def projected_document(self, request, document):
        command = DeviceCommand.from_dict(request.step.input_payload)
        d = json.loads(json.dumps(document)); view = d["view"]
        op = command.operation
        success = self.mode != "failure"
        records = []
        if success:
            if op in {"locate", "click", "type", "save", "send"} and command.target not in view["controls"]:
                raise EnvironmentAccessError("DEVICE_TARGET_MISSING")
            if op == "click":
                view["last_clicked"] = command.target
            elif op == "type":
                view["draft"] = command.text
            elif op == "save":
                view["saved"] = view["draft"]
            elif op == "send":
                view["sent"] = view["draft"]; view["send_count"] += 1
            elif op == "scroll":
                view["scroll"] += command.amount
            elif op == "body.act":
                view["position"] += command.amount
            elif op == "query":
                records = self._records(command, d)
        effect = int(success and op not in {"locate", "query"})
        # save() increments this exact external revision once.
        after = self.observation(command.observation.use, {**d, "revision": d["revision"] + 1})
        result = dict(outcome=command.expected_outcome if success else "FAILED",
            before=command.observation.to_dict(), after=after.to_dict(), records=records,
            authority="SIMULATED_RESULT_OBSERVATION", business_complete=success and op in {"save", "send", "body.act"})
        payload = dict(request_id=request.capability_request_id, request_hash=request.request_hash,
            world="TEST", asset=request.step.target, kind="device_observation",
            content=json.dumps(result, ensure_ascii=False, sort_keys=True))
        receipt = ActionReceipt("receipt:" + request.idempotency_key[7:], request.capability_request_id,
            request.request_hash, self.adapter_id, self.subject_id, "TEST", request.step_id,
            "SUCCEEDED" if success else "FAILED_TERMINAL", effect, effect,
            format_contract_datetime(self.clock()), digest(payload))
        if effect:
            d["effects"].append(request.capability_request_id)
        d["credits"] += effect
        d["facts"].append(dict(receipt=receipt.to_dict(), output=payload))
        return d, receipt

    def projected_size(self, request, document=None):
        if document is None:
            document, _ = self.projected_document(request, self.store.load())
        return len(json.dumps({"document": document, "hash": digest(document)}, ensure_ascii=False).encode("utf-8"))

    def execute(self, request, command, guard):
        self.execute_calls += 1
        if self.before_action:
            self.before_action()
        with self.store.transaction() as d:
            fact = self.query(request)
            if isinstance(fact, ActionReceipt):
                return fact
            if fact is not ReceiptQuery.NOT_EXECUTED:
                raise EnvironmentAccessError("DEVICE_RESULT_UNKNOWN")
            guard()
            # Compare again under the same native simulation transaction.
            if self.observation(command.observation.use, d).state_hash != command.observation.state_hash:
                raise EnvironmentAccessError("DEVICE_REOBSERVE_REQUIRED")
            if self.mode == "before_failure":
                raise OSError("SYNTHETIC_DEVICE_IO")
            d, receipt = self.projected_document(request, d)
            self.store.save(d)
            if self.mode == "lost_response":
                raise OSError("SYNTHETIC_DEVICE_RESPONSE_LOST")
            if self.mode == "unobservable_after":
                self.mode = "send_only"
                raise OSError("SYNTHETIC_DEVICE_RESULT_UNOBSERVABLE")
            return receipt

    def read_result(self, request):
        value = next(row["output"] for row in self.store.load()["facts"]
                     if row["receipt"]["capability_request_id"] == request.capability_request_id)
        return self.result_hook(value) if self.result_hook else value

    def history_current(self, request, command):
        if self.store.load()["status"] != "READY":
            return False
        result = json.loads(self.read_result(request)["content"])
        return result["records"] == self._records(command, self.store.load())


class W04DeviceFixture(P17Fixture):
    def __init__(self, root, *, runtime=None, manager=None, include_body=True):
        super().__init__(root, mode="silence", runtime=runtime, manager=manager)
        self.allowed = True; self.online = True; self.history_allowed = True
        self.repo = JsonEnvironmentRepository(self.runtime.data_root,
            subject_id=self.state.subject_id, environment="TEST")
        self.access = EnvironmentAccessService(self.repo, clock=self.runtime.clock.now,
            authorize=lambda item, **kw: self.allowed, connected=lambda item: self.online,
            authorize_view=lambda *args, **kw: self.allowed)
        self.fake = SimulatedDevicePort(self.runtime.data_root / "worlds" / "w04-device",
            subject=self.state.subject_id, clock=self.runtime.clock.now)
        self.device = DeviceOperationService(access=self.access, port=self.fake,
            clock=self.runtime.clock.now, subject_states=self.runtime.subject_states,
            authorize_history=lambda scope, **kw: self.history_allowed)
        self.routes = tuple(WorldCapability("device." + op, "v1", self.state.subject_id, "TEST", "TEST",
            "body:a" if op == "body.act" else "software:a", self.fake.adapter_id, "credential:p17:test",
            cost=0 if op in {"locate", "query"} else 1, max_output_bytes=32768)
            for op in ("locate", "click", "type", "scroll", "save", "send", "query", "body.act"))
        self.boundary.authorize = lambda route, request, **kw: self.boundary.allowed and request.step.target == route.asset
        self.execution = ExecutionService(self.outbox, routes=self.routes, adapters={self.fake.adapter_id: self.device},
            boundary=self.boundary, broker=self.broker, limits=BlastRadius(requests=32, credits=32, messages=32, storage_bytes=1000000))
        if not self.repo.load()["attachments"]:
            for body in ((False, True) if include_body else (False,)):
                item = self.attachment(body=body)
                self.repo.register(item, expected_revision=self.repo.load()["revision"])
        self.reopen()

    def attachment(self, *, body=False, generation=1):
        now = self.runtime.clock.now(); until = format_contract_datetime(now + timedelta(hours=1))
        ops = ("body.act",) if body else ("locate", "click", "type", "scroll", "save", "send", "query")
        abilities = tuple(Ability("device." + op, "OUTPUT", None, None, None, None,
            format_contract_datetime(now), until) for op in ops)
        if body:
            abilities += (Ability("sensor.position", "INPUT", "unit:meter", "frame:body", -100, 100,
                format_contract_datetime(now), until),)
        return Attachment("body:attachment" if body else "ui:attachment", self.state.subject_id, "TEST",
            AttachmentKind.BODY if body else AttachmentKind.TOOL_EGRESS, DiscoveryState.CONNECTED,
            "host:a", "channel:a", "software:a", "body:a" if body else "device:a", "account:a", "session:a",
            BodyKind.SIMULATED if body else BodyKind.NONE, generation, ("device.act", "body.sense"),
            ("device:read",), abilities, format_contract_datetime(now - timedelta(minutes=1)), until, "permission:w04")

    def use(self, *, body=False, purpose="device.act"):
        item = next(a for a in self.repo.load()["attachments"] if a["attachment_id"] == ("body:attachment" if body else "ui:attachment"))
        return AttachmentUse(**{k: item[k] for k in ("attachment_id", "subject_id", "environment", "generation",
            "host_id", "channel_id", "software_id", "device_id", "account_id", "session_id")}, purpose=purpose, scope="device:read")

    def command(self, operation, *, text=None, amount=None, target=None, history=None):
        use = self.use(body=operation == "body.act")
        target = target or {"save": "control:save", "send": "control:send", "body.act": "actuator:position"}.get(operation, "control:edit")
        return DeviceCommand("w04-device-v1", operation, target, text, amount, history, self.device.observe(use))

    def prepare(self, command, *, decision="device:choice", reserve=True, capability=None):
        step = self.device.step(command, capability=capability)
        snapshot = self.last_context.composition.snapshot
        now = self.runtime.clock.now()
        choice = ActionChoice(decision, "p08-test-thinking-v1", self.state.subject_id, "TEST",
            snapshot.snapshot_hash, snapshot.source_revision, tuple(x.fragment_id for x in snapshot.fragments),
            "ACTION_INTENT", (step,), format_contract_datetime(now), format_contract_datetime(now+timedelta(minutes=2)))
        producer = TestChoiceProducer(); producer.register(choice)
        planner = ActionPlanningService(coordination=self.core.coordination, action_gate=self.core.action_gate,
            producer=producer, constraints=_CurrentConstraints(self.core, self.last_context),
            capabilities=self.core.capabilities, clock=self.runtime.clock.now, subject_id=self.core.subject_id, environment="TEST")
        binding = planner.capabilities[step.capability]
        request = InternalActionRequest(choice, step.step_id, None, binding.adapter.adapter_id, binding.canonical_hash())
        self.constraints.confirmed_ids.add(request.idempotency_key)
        if reserve:
            self.core.coordination.ensure_action_request(request)
        self.execution.prepare(planner, choice, self.last_context.composition)
        return request, lambda retry=False: planner.run(choice, self.last_context.composition, retry=retry)

    def submit_device(self, command, request=None):
        """Normal raw-message C1 with a TEST structured intent, not a result."""
        from .p17_execution_fixture import _Confirmation
        delegate = self.core.policy.delegate
        fixture = self
        class IntentPolicy:
            producer_id = delegate.producer_id
            def choose(self, *args):
                choice = delegate.choose(*args)
                if choice is None:
                    return None
                return replace(choice, steps=(fixture.device.step(command),), requires_planning=False)
        self.mode = "direct"
        self.core.policy = _Confirmation(IntentPolicy(), self)
        return self.submit(request)

    def scope(self, *, query_id="query:history", **changes):
        return HistoryScope(**{**dict(query_id=query_id, subject_id=self.state.subject_id, environment="TEST",
            object_id="object:continuity", software_id="software:a", device_id="device:a", session_id="session:a",
            from_at=None, until_at=None, source_ids=(), permission_ref="permission:history", mode="EXTERNAL",
            subject_willing=True, user_requested=False, limit=4), **changes})

    def sensor(self, value=None):
        if value is None:
            value = self.fake.store.load()["view"]["position"]
        return SensorObservation("sensor:" + digest([value, self.fake.store.load()["revision"]])[7:], self.state.subject_id,
            "TEST", "body:a", self.use(body=True).generation, "sensor.position", value, "unit:meter",
            format_contract_datetime(self.runtime.clock.now()), SensationSource.BODY_OBSERVATION)


def recovery_phase(root, phase):
    """Separate TEST processes reopen the original request, not a replacement."""
    from .sandbox import P01SandboxManager
    from .persistence import atomic_write_json, read_json
    root = _validate_fixture_root(Path(root)); manifest = root / "w04-recovery.json"
    if phase == "effect":
        f = W04DeviceFixture(root); f.submit()
        request, run = f.prepare(f.command("body.act", amount=3))
        f.fake.mode = "lost_response"
        result = run(); f.execution.retain_pending(result)
        assert result.results[0].status.value == "UNKNOWN" and f.fake.effect_count == 1
        atomic_write_json(manifest, dict(sandbox_id=f.runtime.descriptor.sandbox_id,
            message=f.last_request, request_id=request.capability_request_id, revision=f.state.revision))
        return dict(phase=phase, status="UNKNOWN", effects=1, credits=1, revision=f.state.revision)
    saved = read_json(manifest)
    manager = P01SandboxManager(root / "s", formal_data_roots=(root / "formal-canary",))
    f = W04DeviceFixture(root, manager=manager, runtime=manager.open_runtime(saved["sandbox_id"]))
    f.submit(saved["message"])
    request = f.execution.request(saved["request_id"])
    planner = f.restore_dispatch(request)
    result = planner.run(request.choice, f.last_context.composition, retry=True)
    f.execution.collect(result)
    assert result.results[0].status.value == "SUCCEEDED"
    assert (f.fake.execute_calls, f.fake.effect_count, f.fake.credits, f.state.revision) == (0, 1, 1, saved["revision"])
    return dict(phase=phase, status="SUCCEEDED", effects=1, credits=1, new_dispatches=0,
        revision=f.state.revision, receipt_hash=result.results[0].receipt.canonical_hash())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True); parser.add_argument("--phase", choices=("effect", "resume", "replay"), required=True)
    args = parser.parse_args()
    print(json.dumps(recovery_phase(args.root, args.phase), ensure_ascii=False))
