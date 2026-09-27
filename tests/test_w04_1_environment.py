"""W04-1 attachment metadata at the original ingress, action and recall gates."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from continuity_engine.domain.environment_access import (
    Ability, Attachment, AttachmentKind, AttachmentUse, BodyKind,
    DiscoveryState, EnvironmentAccessError, HistoryScope, SensationSource,
)
from continuity_engine.domain.integration_results import format_contract_datetime
from continuity_engine.domain.events import EventClassification, StateMutation, ChangeOperation
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.services.environment_access_service import EnvironmentAccessService, SensorObservation
from continuity_engine.services.scoped_history_service import ScopedHistoryService
from continuity_engine.storage.json_environment_repository import JsonEnvironmentRepository
from continuity_engine.testing.p09_core_fixture import P09Fixture
from continuity_engine.testing.p17_execution_fixture import P17Fixture
from continuity_engine.testing.persistence import tree_inventory_hash


class W04EnvironmentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="w04-1-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.f = P09Fixture(self.root)
        self.subject = self.f.runtime.descriptor.subject_id
        self.repo = JsonEnvironmentRepository(self.f.runtime.data_root, subject_id=self.subject, environment="TEST")
        self.permissions = True
        self.online = True
        self.service = EnvironmentAccessService(self.repo, clock=self.f.runtime.clock.now,
            authorize=lambda item, **kw: self.permissions,
            connected=lambda item: self.online,
            authorize_view=lambda subject, environment, **kw: self.permissions)

    def attachment(self, *, name="entry:a", kind=AttachmentKind.MESSAGE_INGRESS,
                   state=DiscoveryState.CONNECTED, generation=1, host="host:a", enabled=True,
                   body_kind=BodyKind.NONE, device="device:a", purposes=("message.receive",),
                   scopes=("history:read",), abilities=(), account="account:a"):
        now = self.f.runtime.clock.now()
        return Attachment(name, self.subject, "TEST", kind, state, host, "channel:a",
            "software:a", device, account, "session:a", body_kind, generation,
            purposes, scopes, abilities,
            format_contract_datetime(now-timedelta(hours=1)),
            format_contract_datetime(now+timedelta(hours=1)),
            "permission:w04" if state is DiscoveryState.CONNECTED else None, enabled)

    @staticmethod
    def use(item, *, purpose="message.receive", scope=None):
        return AttachmentUse(item.attachment_id, item.subject_id, item.environment,
            item.generation, item.host_id, item.channel_id, item.software_id,
            item.device_id, item.account_id, item.session_id, purpose, scope)

    def register(self, item):
        self.repo.register(item, expected_revision=self.repo.load()["revision"])
        return self.use(item)

    def test_four_states_and_current_availability_are_distinct(self):
        heard = self.attachment(name="heard:a", state=DiscoveryState.HEARD_OF)
        found = self.attachment(name="found:a", state=DiscoveryState.DISCOVERED)
        ready = self.attachment()
        for item in (heard, found, ready): self.register(item)
        rows = {r["attachment_id"]: r for r in self.service.snapshot(subject_id=self.subject,environment="TEST")}
        self.assertEqual([rows[x.attachment_id]["current_status"] for x in (heard,found,ready)],
                         ["NOT_CONNECTED", "NOT_CONNECTED", "CURRENTLY_AVAILABLE"])
        self.online = False
        self.assertEqual(rows[ready.attachment_id]["discovery"], "CONNECTED")
        self.assertEqual(self.service.snapshot(subject_id=self.subject,environment="TEST")[-1]["current_status"], "DISCONNECTED")
        with self.assertRaisesRegex(EnvironmentAccessError, "W04_DISCONNECTED"):
            self.service.require(self.use(ready), kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_formal_ingress_checks_attachment_before_any_operation_write(self):
        item = self.attachment()
        use = self.register(item)
        self.f.app.adapter.service._environment_access = self.service
        request = self.f.request()
        before = tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(Exception):
            self.f.app.adapter.service.submit(request, access_use=replace(use, account_id="account:other"))
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root), before)
        self.assertIsNone(self.f.app.ledger.load_operation(request["requestId"]))
        self.assertEqual(self.f.app.adapter.service.submit(request, access_use=use).status, "completed")
        result = self.f.app.adapter.service.submit(request, access_use=use)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(self.f.app.ledger.list_operations()), 1)

    def test_enabled_bound_entry_requires_trusted_use_even_for_same_formal_payload(self):
        item=self.attachment();self.register(item)
        self.f.app.adapter.service._environment_access=self.service
        request=self.f.request();before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(Exception):self.f.app.adapter.submit(request)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)
        self.assertIsNone(self.f.app.ledger.load_operation(request["requestId"]))

    def test_cross_environment_attachment_cannot_enter_test_engine(self):
        other=JsonEnvironmentRepository(self.f.runtime.data_root,subject_id=self.subject,environment="RESEARCH")
        old=self.attachment()
        other_item=replace(old,environment="RESEARCH")
        other.register(other_item,expected_revision=0)
        gate=EnvironmentAccessService(other,clock=self.f.runtime.clock.now,
            authorize=lambda item,**kw:True,connected=lambda item:True)
        self.f.app.adapter.service._environment_access=gate
        request=self.f.request();before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(Exception):self.f.app.adapter.service.submit(request,access_use=self.use(other_item))
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)

    def test_revocation_expiry_and_current_permission_stop_new_ingress(self):
        item = self.attachment(); use = self.register(item)
        self.f.app.adapter.service._environment_access = self.service
        self.permissions = False
        before = tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(Exception): self.f.app.adapter.service.submit(self.f.request(), access_use=use)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root), before)
        self.permissions = True
        self.repo.disable(item.attachment_id, expected_revision=self.repo.load()["revision"])
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_REVOKED"):
            self.service.require(use,kinds={AttachmentKind.MESSAGE_INGRESS})
        later = self.attachment(name="entry:expiry")
        later_use = self.register(later)
        self.f.runtime.clock.advance(timedelta(hours=2))
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_EXPIRED"):
            self.service.require(later_use,kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_same_account_name_and_wrong_subject_are_not_identity(self):
        item = self.attachment(); use = self.register(item)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_USE_BINDING"):
            self.service.require(replace(use, device_id="device:other"), kinds={AttachmentKind.MESSAGE_INGRESS})
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_USE_BOUNDARY"):
            self.service.require(replace(use, subject_id="subject:other"), kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_model_api_is_not_an_engine_message_ingress(self):
        item=self.attachment(name="model:a",kind=AttachmentKind.MODEL_API)
        use=self.register(item)
        self.f.app.adapter.service._environment_access=self.service
        before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaises(Exception):self.f.app.adapter.service.submit(self.f.request(),access_use=use)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)

    def test_alternative_route_skips_disconnected_and_keeps_grant_checks(self):
        first=self.attachment(name="entry:offline")
        second=self.attachment(name="entry:online")
        self.register(first);self.register(second)
        self.repo.disable(first.attachment_id,expected_revision=self.repo.load()["revision"])
        selected,rejected=self.service.select((self.use(first),self.use(second)),
            kinds={AttachmentKind.MESSAGE_INGRESS})
        self.assertEqual(selected.attachment_id,second.attachment_id)
        self.assertEqual(rejected[0][0],first.attachment_id)
        self.permissions=False
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_NO_CURRENT_ROUTE"):
            self.service.select((self.use(first),self.use(second)),kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_current_check_does_not_reuse_permission_or_connection_result(self):
        item=self.attachment();use=self.register(item)
        self.assertEqual(self.service.require(use,kinds={AttachmentKind.MESSAGE_INGRESS}),item)
        self.permissions=False
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_PERMISSION_DENIED"):
            self.service.require(use,kinds={AttachmentKind.MESSAGE_INGRESS})
        self.permissions=True
        self.online=False
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_DISCONNECTED"):
            self.service.require(use,kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_read_only_view_requires_current_subject_and_permission(self):
        self.register(self.attachment())
        before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_VIEW_BOUNDARY"):
            self.service.snapshot(subject_id="subject:other",environment="TEST")
        self.permissions=False
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_VIEW_PERMISSION_DENIED"):
            self.service.snapshot(subject_id=self.subject,environment="TEST")
        self.permissions=True
        self.assertEqual(len(self.service.snapshot(subject_id=self.subject,environment="TEST")),1)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)

    def test_isolated_handoff_fences_old_host_and_restart_keeps_fence(self):
        old = self.attachment(); use = self.register(old)
        old_body = self.attachment(name="body:old-host", kind=AttachmentKind.BODY,
            body_kind=BodyKind.SIMULATED, purposes=("body.act",))
        old_body_use = self.register(old_body)
        inventory = ("subject-state", "event", "memory", "learning", "items", "e5a", "runtime")
        prepared = self.service.prepare_migration(kind="SAME_SUBJECT_TRANSFER", subject_id=self.subject,
            source_host="host:a", target_host="host:b", source_time_ref="clock:trusted",
            available=inventory, required=inventory)
        self.assertEqual(prepared.status,"READY_FOR_ISOLATED_HANDOFF")
        changed = self.service.handoff_isolated(prepared, expected_revision=self.repo.load()["revision"])
        self.assertEqual(changed["generation"],2)
        reopened = EnvironmentAccessService(JsonEnvironmentRepository(self.f.runtime.data_root,
            subject_id=self.subject, environment="TEST"), clock=self.f.runtime.clock.now,
            authorize=lambda item, **kw: True, connected=lambda item: True,
            authorize_view=lambda subject,environment,**kw: True)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_OLD_HOST_FENCED"):
            reopened.require(use,kinds={AttachmentKind.MESSAGE_INGRESS})
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_OLD_HOST_FENCED"):
            reopened.require(replace(old_body_use,purpose="body.act"),kinds={AttachmentKind.BODY})
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_OLD_HOST_FENCED"):
            reopened.repository.register(self.attachment(name="entry:old-after-handoff"),
                expected_revision=changed["revision"])
        new = self.attachment(name="entry:b",generation=2,host="host:b")
        reopened.repository.register(new, expected_revision=changed["revision"])
        self.assertEqual(reopened.require(self.use(new),kinds={AttachmentKind.MESSAGE_INGRESS}),new)

    def test_migration_kinds_missing_inventory_and_production_not_ready(self):
        self.register(self.attachment())
        prepared = self.service.prepare_migration(kind="SAME_SUBJECT_TRANSFER",subject_id=self.subject,
            source_host="host:a",target_host="host:b",source_time_ref="clock:trusted",
            available=("subject-state",),required=("subject-state","e5a"))
        self.assertEqual((prepared.status,prepared.missing),("DEPENDENCY_MISSING",("e5a",)))
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_HANDOFF_NOT_READY"):
            self.service.handoff_isolated(prepared,expected_revision=self.repo.load()["revision"])
        for kind in ("FIRST_IMPORT","NEW_SUBJECT"):
            result=self.service.prepare_migration(kind=kind,subject_id=self.subject,source_host=None,
                target_host="host:b",source_time_ref="clock:trusted",available=(),required=())
            self.assertEqual(result.status,"NOT_READY_PRODUCTION")
        switch=self.service.prepare_migration(kind="ENTRY_SWITCH",subject_id=self.subject,source_host="host:a",
            target_host="host:b",source_time_ref=None,available=(),required=())
        self.assertEqual(switch.status,"ENTRY_ONLY")

    def test_handoff_preparation_cannot_cross_subject_or_environment(self):
        self.register(self.attachment())
        inventory = ("subject-state", "event", "e5a")
        prepared = self.service.prepare_migration(kind="SAME_SUBJECT_TRANSFER", subject_id=self.subject,
            source_host="host:a", target_host="host:b", source_time_ref="clock:trusted",
            available=inventory, required=inventory)
        for subject_id, environment in (("subject:other", "TEST"), (self.subject, "RESEARCH")):
            with self.subTest(subject_id=subject_id, environment=environment):
                other = JsonEnvironmentRepository(self.f.runtime.data_root,
                    subject_id=subject_id, environment=environment)
                other.register(replace(self.attachment(name="entry:other"),
                    subject_id=subject_id, environment=environment), expected_revision=0)
                service = EnvironmentAccessService(other, clock=self.f.runtime.clock.now,
                    authorize=lambda item, **kw: True, connected=lambda item: True)
                before = other.path.read_bytes()
                original = self.repo.path.read_bytes()
                with self.assertRaisesRegex(EnvironmentAccessError, "W04_HANDOFF_BINDING"):
                    service.handoff_isolated(prepared, expected_revision=other.load()["revision"])
                self.assertEqual(other.path.read_bytes(), before)
                self.assertEqual(self.repo.path.read_bytes(), original)

    def test_migration_preparation_status_cannot_contradict_kind_or_inventory(self):
        self.register(self.attachment())
        prepared = self.service.prepare_migration(kind="SAME_SUBJECT_TRANSFER", subject_id=self.subject,
            source_host="host:a", target_host="host:b", source_time_ref="clock:trusted",
            available=("subject-state",), required=("subject-state",))
        before = self.repo.path.read_bytes()
        for changes in ({"kind": "FIRST_IMPORT"},
                        {"required": ("subject-state", "e5a"), "missing": ("e5a",)}):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(EnvironmentAccessError, "W04_MIGRATION_STATUS"):
                    replace(prepared, **changes)
                self.assertEqual(self.repo.path.read_bytes(), before)

    def test_sensor_contract_rejects_non_finite_bool_and_wrong_type(self):
        now = self.f.runtime.clock.now()
        ability = Ability("sensor.temperature", "INPUT", "unit:celsius", None, 0, 100,
            format_contract_datetime(now), format_contract_datetime(now + timedelta(minutes=5)))
        body = self.attachment(name="body:measure", kind=AttachmentKind.BODY,
            body_kind=BodyKind.SIMULATED, purposes=("body.sense",), abilities=(ability,))
        use = replace(self.register(body), purpose="body.sense")
        observation = SensorObservation("observation:measure", self.subject, "TEST", body.device_id,
            body.generation, ability.name, 0, ability.unit, format_contract_datetime(now),
            SensationSource.BODY_OBSERVATION)
        before = self.repo.path.read_bytes()
        self.assertEqual(self.service.validate_sensor(use, observation).value, 0)
        self.assertIsNone(self.service.validate_sensor(use, replace(observation, value=None)).value)
        for value in (float("nan"), float("inf"), -float("inf"), True, "0", []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(EnvironmentAccessError, "W04_SENSOR_VALUE_INVALID"):
                    self.service.validate_sensor(use, replace(observation, value=value))
                self.assertEqual(self.repo.path.read_bytes(), before)

    def test_body_none_unknown_zero_and_source_separation(self):
        self.assertEqual(self.service.body_state(subject_id=self.subject,environment="TEST")["kind"],"NONE")
        now=self.f.runtime.clock.now()
        ability=Ability("sensor.temperature","INPUT","unit:celsius","frame:body",0,100,
            format_contract_datetime(now),format_contract_datetime(now+timedelta(minutes=5)),0)
        body=self.attachment(name="body:a",kind=AttachmentKind.BODY,body_kind=BodyKind.SIMULATED,
                             purposes=("body.sense",),abilities=(ability,))
        use=self.register(body)
        self.assertEqual(self.service.body_state(subject_id=self.subject,environment="TEST")["abilities"][0]["value"],0)
        observation=SensorObservation("observation:a",self.subject,"TEST","device:a",1,
            "sensor.temperature",0,"unit:celsius",format_contract_datetime(now),SensationSource.BODY_OBSERVATION)
        self.assertEqual(self.service.validate_sensor(replace(use,purpose="body.sense"),observation),observation)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_SENSOR_SOURCE_INVALID"):
            self.service.validate_sensor(replace(use,purpose="body.sense"),replace(observation,source=SensationSource.DREAM_SIMULATION))
        unknown=replace(ability,value=None)
        self.assertIsNone(unknown.value)
        self.online=False
        self.assertEqual(self.service.body_state(subject_id=self.subject,environment="TEST")["status"],"DISCONNECTED")

    def test_sensor_missing_ability_wrong_generation_and_expired_sample_rejected(self):
        now=self.f.runtime.clock.now()
        ability=Ability("sensor.touch","INPUT","unit:force","frame:body",0,10,
            format_contract_datetime(now),format_contract_datetime(now+timedelta(minutes=1)))
        body=self.attachment(name="body:sense",kind=AttachmentKind.BODY,body_kind=BodyKind.SIMULATED,
            purposes=("body.sense",),abilities=(ability,))
        use=replace(self.register(body),purpose="body.sense")
        obs=SensorObservation("observation:touch",self.subject,"TEST",body.device_id,1,
            ability.name,0,ability.unit,format_contract_datetime(now),SensationSource.BODY_OBSERVATION)
        self.assertEqual(self.service.validate_sensor(use,obs).value,0)
        for changed in (replace(obs,generation=2),replace(obs,ability_name="sensor:unknown")):
            with self.assertRaises(EnvironmentAccessError):self.service.validate_sensor(use,changed)
        self.f.runtime.clock.advance(timedelta(minutes=2))
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_SENSOR_EXPIRED"):
            self.service.validate_sensor(use,obs)

    def test_corrupt_store_and_revision_conflict_fail_closed(self):
        item=self.attachment(); self.register(item)
        original=self.repo.path.read_bytes()
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_REVISION_CONFLICT"):
            self.repo.disable(item.attachment_id,expected_revision=0)
        self.assertEqual(self.repo.path.read_bytes(),original)
        self.repo.path.write_text("{bad",encoding="utf-8")
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_STORE_CORRUPT"):
            self.service.snapshot(subject_id=self.subject,environment="TEST")

    def test_revocation_during_current_permission_callback_is_seen(self):
        item=self.attachment();use=self.register(item)
        def revoke(record,**kwargs):
            self.repo.disable(record.attachment_id,expected_revision=self.repo.load()["revision"])
            return True
        service=EnvironmentAccessService(self.repo,clock=self.f.runtime.clock.now,
            authorize=revoke,connected=lambda row: True)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_CHANGED_DURING_CHECK"):
            service.require(use,kinds={AttachmentKind.MESSAGE_INGRESS})

    def test_scoped_history_uses_original_router_composer_and_is_read_only(self):
        self.f.event("w04-history", content="continuity synthetic older discussion")
        request=self.f.request(); self.f.submit(request)
        perception=self.f.app.ledger.load_operation(request["requestId"]).domain_progress.perception
        scope=HistoryScope("query:a",self.subject,"TEST","continuity",None,None,None,
            None,None,(),"permission:history","LOCAL",False,False)
        history=ScopedHistoryService(self.f.core,authorize_scope=lambda scope,**kw: True)
        before=tree_inventory_hash(self.f.runtime.data_root)
        result=history.query(scope,perception)
        self.assertEqual(result["status"],"AVAILABLE")
        self.assertTrue(any("w04-history" in row["stable_id"] for row in result["references"]))
        self.assertEqual((result["model_calls"],result["external_calls"]),(0,0))
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_HISTORY_PERMISSION_DENIED"):
            ScopedHistoryService(self.f.core,authorize_scope=lambda scope,**kw: False).query(scope,perception)
        limited=history.query(replace(scope,session_id="session:other"),perception)
        self.assertEqual(limited["reason"],"VERIFIED_SOURCE_SCOPE_NOT_AVAILABLE")

    def test_history_current_source_permission_and_scope_are_checked(self):
        self.f.event("w04-source",content="continuity synthetic older discussion")
        request=self.f.request();self.f.submit(request)
        perception=self.f.app.ledger.load_operation(request["requestId"]).domain_progress.perception
        scope=HistoryScope("query:scoped",self.subject,"TEST","continuity",None,None,"session:ok",
            None,None,(),"permission:history","LOCAL",False,False)
        service=ScopedHistoryService(self.f.core,authorize_scope=lambda scope,**kw: True,
            source_scope=lambda fragment:{"session_id":"session:ok"})
        self.assertEqual(service.query(scope,perception)["status"],"AVAILABLE")
        self.assertEqual(service.query(replace(scope,session_id="session:other"),perception)["status"],"NO_MATCH")
        self.f.permission.allowed=False
        self.assertEqual(service.query(scope,perception)["status"],"BLOCKED")

    def test_history_permission_change_during_read_rejects_before_return(self):
        self.f.event("w04-late",content="continuity synthetic older discussion")
        request=self.f.request();self.f.submit(request)
        perception=self.f.app.ledger.load_operation(request["requestId"]).domain_progress.perception
        scope=HistoryScope("query:late",self.subject,"TEST","continuity",None,None,None,
            None,None,(),"permission:history","LOCAL",False,False)
        calls=[0]
        def permission(scope,**kwargs):
            calls[0]+=1
            return calls[0]==1
        service=ScopedHistoryService(self.f.core,authorize_scope=permission)
        before=tree_inventory_hash(self.f.runtime.data_root)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_HISTORY_CURRENT_ACCESS_CHANGED"):
            service.query(scope,perception)
        self.assertEqual(tree_inventory_hash(self.f.runtime.data_root),before)

    def test_history_old_revision_cannot_be_reused_after_new_state(self):
        request=self.f.request();self.f.submit(request)
        perception=self.f.app.ledger.load_operation(request["requestId"]).domain_progress.perception
        self.f.event("newer-state",content="continuity changed after query creation",
            classification=EventClassification.STATE_CHANGE,
            mutations=(StateMutation("continuity.current_focus",ChangeOperation.SET,
                ["new focus"],"Isolated later state change"),))
        scope=HistoryScope("query:old",self.subject,"TEST","continuity",None,None,None,
            None,None,(),"permission:history","LOCAL",False,False)
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_HISTORY_REVISION"):
            ScopedHistoryService(self.f.core,authorize_scope=lambda scope,**kw:True).query(scope,perception)

    def test_deep_history_needs_willingness_and_future_route(self):
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_HISTORY_INTENT_REQUIRED"):
            HistoryScope("query:deep",self.subject,"TEST","topic:a",None,None,None,
                None,None,(),"permission:history","DEEP_ARCHIVE",False,False)


class W04ActionBindingTests(unittest.TestCase):
    def test_expired_output_ability_rejects_existing_execution_before_effect_or_cost(self):
        tmp = tempfile.TemporaryDirectory(prefix="wa-"); self.addCleanup(tmp.cleanup)
        f = P17Fixture(Path(tmp.name)); route = f.routes[0]
        repo = JsonEnvironmentRepository(f.runtime.data_root, subject_id=route.subject_id, environment="TEST")
        now = f.runtime.clock.now()
        ability = Ability(route.capability_ref, "OUTPUT", None, None, None, None,
            format_contract_datetime(now - timedelta(minutes=1)), format_contract_datetime(now))
        item = Attachment("body:expired-output", route.subject_id, "TEST", AttachmentKind.BODY,
            DiscoveryState.CONNECTED, "host:action", "channel:action", None, route.asset, None, None,
            BodyKind.SIMULATED, 1, ("body.act",), (), (ability,),
            format_contract_datetime(now - timedelta(minutes=2)),
            format_contract_datetime(now + timedelta(hours=1)), "permission:action")
        repo.register(item, expected_revision=0)
        service = EnvironmentAccessService(repo, clock=f.runtime.clock.now,
            authorize=lambda item, **kw: True, connected=lambda item: True)
        f.execution.environment_access = service
        f.execution.access_uses[route.capability_ref] = AttachmentUse(item.attachment_id, item.subject_id,
            item.environment, item.generation, item.host_id, item.channel_id, item.software_id,
            item.device_id, item.account_id, item.session_id, "body.act")
        with self.assertRaises(IntegrationExecutionError) as raised:
            f.submit()
        self.assertIsInstance(raised.exception.__cause__, EnvironmentAccessError)
        self.assertEqual(str(raised.exception.__cause__), "W04_ACTION_ABILITY_EXPIRED")
        self.assertEqual((f.fake.effect_count, f.fake.credits), (0, 0))

    def test_current_output_ability_executes_through_existing_execution(self):
        tmp = tempfile.TemporaryDirectory(prefix="wa-"); self.addCleanup(tmp.cleanup)
        f = P17Fixture(Path(tmp.name)); route = f.routes[0]
        repo = JsonEnvironmentRepository(f.runtime.data_root, subject_id=route.subject_id, environment="TEST")
        now = f.runtime.clock.now()
        ability = Ability(route.capability_ref, "OUTPUT", None, None, None, None,
            format_contract_datetime(now - timedelta(minutes=1)),
            format_contract_datetime(now + timedelta(minutes=1)))
        item = Attachment("body:current-output", route.subject_id, "TEST", AttachmentKind.BODY,
            DiscoveryState.CONNECTED, "host:action", "channel:action", None, route.asset, None, None,
            BodyKind.SIMULATED, 1, ("body.act",), (), (ability,),
            format_contract_datetime(now - timedelta(minutes=2)),
            format_contract_datetime(now + timedelta(hours=1)), "permission:action")
        repo.register(item, expected_revision=0)
        f.execution.environment_access = EnvironmentAccessService(repo, clock=f.runtime.clock.now,
            authorize=lambda item, **kw: True, connected=lambda item: True)
        f.execution.access_uses[route.capability_ref] = AttachmentUse(item.attachment_id, item.subject_id,
            item.environment, item.generation, item.host_id, item.channel_id, item.software_id,
            item.device_id, item.account_id, item.session_id, "body.act")
        self.assertEqual(f.submit().status, "completed")
        self.assertEqual((f.fake.effect_count, f.fake.credits), (1, 1))

    def test_body_action_uses_existing_execution_and_fences_changed_attachment(self):
        tmp=tempfile.TemporaryDirectory(prefix="w04-1-action-");self.addCleanup(tmp.cleanup)
        f=P17Fixture(Path(tmp.name))
        route=f.routes[0]
        repo=JsonEnvironmentRepository(f.runtime.data_root,subject_id=route.subject_id,environment="TEST")
        now=f.runtime.clock.now()
        item=Attachment("body:action",route.subject_id,"TEST",AttachmentKind.BODY,
            DiscoveryState.CONNECTED,"host:action","channel:action",None,route.asset,None,None,
            BodyKind.SIMULATED,1,("body.act",),(),
            (Ability(route.capability_ref,"OUTPUT",None,None,None,None,None,None),),
            format_contract_datetime(now-timedelta(minutes=1)),format_contract_datetime(now+timedelta(hours=1)),
            "permission:action")
        repo.register(item,expected_revision=0)
        service=EnvironmentAccessService(repo,clock=f.runtime.clock.now,
            authorize=lambda item,**kw: True,connected=lambda item: True)
        use=AttachmentUse(item.attachment_id,item.subject_id,item.environment,item.generation,
            item.host_id,item.channel_id,item.software_id,item.device_id,item.account_id,
            item.session_id,"body.act")
        f.execution.environment_access=service
        f.execution.access_uses[route.capability_ref]=use
        self.assertEqual(f.submit().status,"completed")
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
        self.assertEqual(f.submit(f.last_request).status,"completed")
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))
        repo.disable(item.attachment_id,expected_revision=repo.load()["revision"])
        with self.assertRaisesRegex(EnvironmentAccessError,"W04_REVOKED"):
            service.require_action(use,route,f.core.last_action.requests[0])
        self.assertEqual((f.fake.effect_count,f.fake.credits),(1,1))

    def test_revocation_inside_resource_check_prevents_world_effect(self):
        tmp=tempfile.TemporaryDirectory(prefix="w04-1-action-revoke-");self.addCleanup(tmp.cleanup)
        f=P17Fixture(Path(tmp.name));route=f.routes[0]
        repo=JsonEnvironmentRepository(f.runtime.data_root,subject_id=route.subject_id,environment="TEST")
        now=f.runtime.clock.now()
        item=Attachment("body:revoke",route.subject_id,"TEST",AttachmentKind.BODY,
            DiscoveryState.CONNECTED,"host:a","channel:a",None,route.asset,None,None,
            BodyKind.SIMULATED,1,("body.act",),(),
            (Ability(route.capability_ref,"OUTPUT",None,None,None,None,None,None),),
            format_contract_datetime(now-timedelta(minutes=1)),format_contract_datetime(now+timedelta(hours=1)),
            "permission:action")
        repo.register(item,expected_revision=0)
        service=EnvironmentAccessService(repo,clock=f.runtime.clock.now,
            authorize=lambda item,**kw:True,connected=lambda item:True)
        f.execution.environment_access=service
        f.execution.access_uses[route.capability_ref]=AttachmentUse(item.attachment_id,item.subject_id,
            item.environment,item.generation,item.host_id,item.channel_id,item.software_id,
            item.device_id,item.account_id,item.session_id,"body.act")
        f.boundary.hook=lambda: repo.disable(item.attachment_id,expected_revision=repo.load()["revision"])
        with self.assertRaises(Exception):f.submit()
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))

    def test_revocation_inside_final_reality_callback_prevents_world_effect(self):
        tmp=tempfile.TemporaryDirectory(prefix="w04-1-action-last-gate-");self.addCleanup(tmp.cleanup)
        f=P17Fixture(Path(tmp.name));route=f.routes[0]
        repo=JsonEnvironmentRepository(f.runtime.data_root,subject_id=route.subject_id,environment="TEST")
        now=f.runtime.clock.now()
        item=Attachment("body:last-gate",route.subject_id,"TEST",AttachmentKind.BODY,
            DiscoveryState.CONNECTED,"host:a","channel:a",None,route.asset,None,None,
            BodyKind.SIMULATED,1,("body.act",),(),
            (Ability(route.capability_ref,"OUTPUT",None,None,None,None,None,None),),
            format_contract_datetime(now-timedelta(minutes=1)),format_contract_datetime(now+timedelta(hours=1)),
            "permission:action")
        repo.register(item,expected_revision=0)
        service=EnvironmentAccessService(repo,clock=f.runtime.clock.now,
            authorize=lambda item,**kw:True,connected=lambda item:True)
        f.execution.environment_access=service
        f.execution.access_uses[route.capability_ref]=AttachmentUse(item.attachment_id,item.subject_id,
            item.environment,item.generation,item.host_id,item.channel_id,item.software_id,
            item.device_id,item.account_id,item.session_id,"body.act")
        original=f.boundary.authorize
        def revoke_during_authorize(route,request,*,purpose):
            if repo.load()["attachments"][0]["enabled"]:
                repo.disable(item.attachment_id,expected_revision=repo.load()["revision"])
            return original(route,request,purpose=purpose)
        f.boundary.authorize=revoke_during_authorize
        with self.assertRaises(Exception): f.submit()
        self.assertEqual((f.fake.effect_count,f.fake.credits),(0,0))


if __name__ == "__main__": unittest.main()
