import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from continuity_engine.domain.action import (
    ActionContext,
    ActionPlanStatus,
    ActionType,
    PermissionGrant,
    PerceptionActionSummary,
    ResourceLimits,
)
from continuity_engine.domain.permissions import (
    PermissionChangeType,
    PermissionContext,
    PermissionState,
    PermissionStatus,
)
from continuity_engine.domain.thinking import ThinkingDepth, ThinkingResult, TokenBudget
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_permission_repository import (
    JsonPermissionRepository,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository


class PermissionContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 23, 9, 0, tzinfo=timezone.utc)

    def service(self, directory) -> PermissionService:
        return PermissionService(
            JsonPermissionRepository(directory),
            clock=lambda: self.now,
        )

    def create_memory_permission(self, service: PermissionService):
        return service.create_permission(
            "subject-1",
            permission_id="permission-memory",
            permission_type="information_access",
            name="Continuity memory access",
            description="Allows bounded requests to the external memory manager.",
            scope=["memory_manager"],
            capabilities=["memory:request"],
            source="user_authorization",
            reason="The user explicitly authorized continuity memory retrieval.",
        )

    def test_create_and_query_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)

            created = self.create_memory_permission(service)
            restored = service.get_permission("subject-1", "permission-memory")

            self.assertEqual(created.permission.status, PermissionStatus.ACTIVE)
            self.assertEqual(created.permission.revision, 0)
            self.assertEqual(restored.to_dict(), created.permission.to_dict())
            self.assertEqual(service.list_permissions("subject-1"), [restored])
            self.assertEqual(created.record.change_type, PermissionChangeType.GRANTED)
            self.assertIsNone(created.record.before_state)
            self.assertEqual(created.record.after_state, restored.to_dict())
            self.assertEqual(
                created.event.metadata["permission_change_record_id"],
                created.record.record_id,
            )

    def test_revoke_permission_and_trace_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            self.create_memory_permission(service)

            revoked = service.revoke_permission(
                "subject-1",
                "permission-memory",
                reason="The user withdrew memory access.",
                source="user_authorization",
                expected_revision=0,
            )
            history = service.get_history("subject-1", "permission-memory")

            self.assertEqual(revoked.permission.status, PermissionStatus.REVOKED)
            self.assertEqual(revoked.permission.revision, 1)
            self.assertEqual(revoked.permission.revoked_at, self.now)
            self.assertFalse(service.check_capability("subject-1", "memory:request"))
            self.assertEqual(
                {item.change_type for item in history},
                {PermissionChangeType.GRANTED, PermissionChangeType.REVOKED},
            )
            revoke_record = next(
                item for item in history if item.change_type is PermissionChangeType.REVOKED
            )
            self.assertEqual(revoke_record.before_state["status"], "ACTIVE")
            self.assertEqual(revoke_record.after_state["status"], "REVOKED")
            self.assertIn("withdrew", revoke_record.reason)

    def test_limit_permission_updates_scope_capabilities_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)
            self.create_memory_permission(service)

            limited = service.restrict_permission(
                "subject-1",
                "permission-memory",
                scope=["memory_manager:project-only"],
                capabilities=["memory:request"],
                reason="Access is now limited to project memory.",
                source="user_authorization",
                expected_revision=0,
            )
            context = service.get_context("subject-1")

            self.assertEqual(limited.permission.status, PermissionStatus.LIMITED)
            self.assertEqual(limited.permission.revision, 1)
            self.assertTrue(
                service.check_capability(
                    "subject-1",
                    "memory:request",
                    scope="memory_manager:project-only",
                )
            )
            self.assertFalse(
                service.check_capability(
                    "subject-1",
                    "memory:request",
                    scope="memory_manager:all",
                )
            )
            self.assertEqual(context.available_capabilities, ["memory:request"])
            self.assertEqual(len(context.restrictions), 1)
            self.assertIn("LIMITED", context.restrictions[0])
            self.assertEqual(
                PermissionContext.from_dict(context.to_dict()).to_dict(),
                context.to_dict(),
            )

    def test_permission_state_and_history_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = self.service(directory)
            self.create_memory_permission(first)
            first.restrict_permission(
                "subject-1",
                "permission-memory",
                scope=["memory_manager:project-only"],
                reason="Limit memory scope.",
                source="user_authorization",
            )

            restarted = self.service(directory)
            restored = restarted.get_permission("subject-1", "permission-memory")
            history = restarted.get_history("subject-1", "permission-memory")

            self.assertEqual(restored.status, PermissionStatus.LIMITED)
            self.assertEqual(restored.revision, 1)
            self.assertEqual(len(history), 2)
            self.assertEqual(
                PermissionState.from_dict(restored.to_dict()).to_dict(),
                restored.to_dict(),
            )

    def test_missing_capability_check_fails_without_creating_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = self.service(directory)

            self.assertFalse(service.check_capability("subject-1", "tool:use"))
            context = service.get_context("subject-1")
            self.assertEqual(context.current_permissions, [])
            self.assertEqual(context.available_capabilities, [])
            self.assertEqual(service.list_permissions("subject-1"), [])

    def test_action_reads_permission_context_before_immediate_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            permissions = self.service(directory)
            self.create_memory_permission(permissions)
            permission_context = permissions.get_context("subject-1")
            thinking = ThinkingResult.create(
                provider_id="permission-context-test",
                result_summary="More memory would clarify the current state.",
                rationale_summary="The current perception contains an information gap.",
                generated_new_thought=False,
                update_subject_state=False,
                request_more_memory=True,
                additional_memory_query="Retrieve the missing project decision.",
                should_wait=False,
                suggest_future_user_contact=False,
                token_budget=TokenBudget(1_000, 1_000, 500, ThinkingDepth.LOW),
                result_id="thinking-permission-context",
            )
            context = ActionContext(
                context_id="action-permission-context",
                subject_id="subject-1",
                wake_session_id="wake-1",
                think_session_id="think-1",
                subject_state_revision=0,
                thinking_result=thinking,
                perception_summary=PerceptionActionSummary(
                    perception_id="perception-1",
                    wake_session_id="wake-1",
                    source_revision=0,
                    summary="More information may be useful.",
                    current_focus="Permission continuity.",
                    temporal_meaning="The context is current.",
                    relationship_meaning="No relationship movement is relevant.",
                    memory_influence="No selected memory resolves the gap.",
                    observation_notes=["More information is needed."],
                    internal_drives=["Request relevant memory."],
                ),
                current_time=self.now,
                available_permissions=[],
                resource_limits=ResourceLimits(),
                permission_context=permission_context,
            )
            immediate_provider = InMemoryPermissionProvider(
                [
                    PermissionGrant(
                        permission="memory:request",
                        subject_id="subject-1",
                        valid_from=self.now - timedelta(days=1),
                        scopes=["memory_manager"],
                    )
                ]
            )
            action = ActionService(
                immediate_provider,
                InMemoryActionRepository(),
            ).decide(context)
            restored_context = ActionContext.from_dict(context.to_dict())

            self.assertEqual(
                action.decision.selected_action.action_type,
                ActionType.REQUEST_MEMORY,
            )
            self.assertTrue(action.decision.approved)
            self.assertEqual(action.plan.status, ActionPlanStatus.PLANNED)
            self.assertEqual(context.available_permissions, [])
            self.assertEqual(context.effective_permissions, ["memory:request"])
            self.assertEqual(
                restored_context.permission_context.to_dict(),
                permission_context.to_dict(),
            )

            permissions.revoke_permission(
                "subject-1",
                "permission-memory",
                reason="Memory permission was withdrawn.",
                source="user_authorization",
            )
            context.permission_context = permissions.get_context("subject-1")
            context.available_permissions = ["memory:request"]
            blocked = ActionService(
                immediate_provider,
                InMemoryActionRepository(),
            ).decide(context)
            self.assertEqual(context.effective_permissions, [])
            self.assertFalse(blocked.decision.approved)
            self.assertEqual(blocked.plan.status, ActionPlanStatus.BLOCKED)

    def test_permission_service_returns_event_but_does_not_modify_subject_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            states = SubjectStateService(
                JsonSubjectStateRepository(directory),
                clock=lambda: self.now,
            )
            states.create("subject-1")
            permissions = self.service(directory)

            change = self.create_memory_permission(permissions)

            unchanged = states.load("subject-1")
            self.assertEqual(unchanged.revision, 0)
            self.assertEqual(unchanged.continuity.recent_changes, [])

            evolution = states.apply_event(
                "subject-1",
                change.event,
                expected_revision=0,
            )
            self.assertEqual(evolution.state.revision, 1)
            self.assertIn(
                "Permission Continuity memory access: GRANTED at revision 0",
                evolution.state.continuity.recent_changes,
            )


if __name__ == "__main__":
    unittest.main()
