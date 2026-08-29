from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.awakening import AwakeCycle, AwakeMode
from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.domain.errors import IntegrationPersistenceError
from continuity_engine.domain.integration_hashing import calculate_state_hash
from continuity_engine.domain.subject_binding import SubjectBinding
from continuity_engine.interfaces.integration_adapter import IntegrationAdapter
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.capability_coordination_service import (
    CapabilityCoordinationService,
)
from continuity_engine.services.continuity_interaction_service import ContinuityInteractionService
from continuity_engine.services.deterministic_integration_providers import (
    DeterministicContractReplyComposer,
    DeterministicMemoryInfluenceRecorder,
    DeterministicMemoryRetriever,
    DeterministicThinkingProvider,
    DeterministicTokenBudgetManager,
    DeferredCapabilityThinkingProvider,
    CapabilityContractReplyComposer,
)
from continuity_engine.services.integration_contract_validation import MachineContractValidator
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.in_memory_action_repository import InMemoryActionRepository
from continuity_engine.storage.json_awakening_repository import JsonAwakeningRepository
from continuity_engine.storage.json_integration_repository import JsonIntegrationResultLedger
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_subject_binding_repository import JsonSubjectBindingRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


class LocalIntegrationInitializationError(RuntimeError):
    """The formal local data directory is absent, partial, or inconsistent."""


@dataclass(frozen=True, slots=True)
class LocalIntegrationApp:
    adapter: IntegrationAdapter
    binding: SubjectBinding
    subject_states: SubjectStateService
    awakening_repository: JsonAwakeningRepository
    ledger: JsonIntegrationResultLedger
    data_dir: Path
    thinking_mode: IntegrationThinkingMode

    def assert_ready(self) -> None:
        binding = JsonSubjectBindingRepository(self.data_dir).load_active()
        if binding != self.binding:
            raise LocalIntegrationInitializationError("runtime binding changed")
        state = self.subject_states.load(binding.subject_id)
        cycle = self.awakening_repository.load_cycle(binding.cycle_id)
        if cycle.subject_id != binding.subject_id or cycle.mode is not AwakeMode.MANUAL:
            raise LocalIntegrationInitializationError("runtime AwakeCycle is inconsistent")
        self.ledger.validate_initialized()
        capability_ledger_exists = self.ledger.capability_path.exists()
        if self.thinking_mode is IntegrationThinkingMode.CAPABILITY:
            self.ledger.validate_capability_initialized()
        updates = self.subject_states.get_update_history(binding.subject_id)
        update_ids = {item.update_id for item in updates}
        operations = self.ledger.list_operations()
        results = self.ledger.list_completed()
        operations_by_request = {item.request_id: item for item in operations}
        results_by_request = {item.request_id: item for item in results}
        for operation in operations:
            if operation.subject_id != binding.subject_id or operation.input_revision > state.revision:
                raise LocalIntegrationInitializationError(
                    "operation journal conflicts with authoritative SubjectState"
                )
            if (
                operation.stage.value == "completed"
                and operation.request_id not in results_by_request
            ):
                raise LocalIntegrationInitializationError(
                    "completed operation is missing its immutable result"
                )
            capability_request = (
                self.ledger.find_capability_request_by_operation(operation.operation_id)
                if capability_ledger_exists
                else None
            )
            attempts = (
                self.ledger.list_capability_attempts(
                    capability_request.capability_request_id
                )
                if capability_request is not None
                else []
            )
            if self.thinking_mode is IntegrationThinkingMode.DETERMINISTIC:
                if capability_request is not None or operation.capability is not None:
                    raise LocalIntegrationInitializationError(
                        "capability operation cannot run in deterministic mode"
                    )
            elif (
                operation.stage.value == "waiting_capability"
                and capability_request is None
            ):
                raise LocalIntegrationInitializationError(
                    "waiting operation is missing its CapabilityRequest"
                )
            elif operation.capability is not None and (
                capability_request is None
                or operation.capability.capability_request_id
                != capability_request.capability_request_id
            ):
                raise LocalIntegrationInitializationError(
                    "operation capability checkpoint conflicts with its request"
                )
            elif operation.capability is not None and (
                operation.capability.status.value != "PROPOSED"
                and not any(
                    attempt.result.capability_result_id
                    == operation.capability.accepted_result_id
                    and attempt.result_hash
                    == operation.capability.accepted_result_hash
                    and attempt.result.status is operation.capability.status
                    for attempt in attempts
                )
            ):
                raise LocalIntegrationInitializationError(
                    "operation capability checkpoint references an unknown result"
                )
        for result in results:
            operation = operations_by_request.get(result.request_id)
            if (
                operation is None
                or operation.request_hash != result.request_hash
                or operation.operation_id != result.operation_id
            ):
                raise LocalIntegrationInitializationError(
                    "completed result conflicts with its operation journal record"
                )
            projection = result.state_projection
            if result.subject_id != binding.subject_id or projection.current_revision > state.revision:
                raise LocalIntegrationInitializationError(
                    "result ledger conflicts with authoritative SubjectState"
                )
            if projection.engine_update_id is not None and projection.engine_update_id not in update_ids:
                raise LocalIntegrationInitializationError(
                    "state projection references an unknown StateUpdateRecord"
                )
            if (
                projection.current_revision == state.revision
                and projection.snapshot.state_hash != calculate_state_hash(state)
            ):
                raise LocalIntegrationInitializationError(
                    "current state projection conflicts with SubjectState"
                )

    def is_ready(self) -> bool:
        try:
            self.assert_ready()
            return True
        except Exception:
            return False


def _uuid_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _validate_data_dir(path: Path) -> Path:
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise LocalIntegrationInitializationError("data directory must be a real directory")
    return path.resolve()


def _read_binding_file(path: Path, binding_hash: str, cycle_id: str) -> SubjectBinding:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload: Any = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalIntegrationInitializationError("binding file is not valid UTF-8 JSON") from exc
    try:
        fixture = MachineContractValidator().validate_fixed_subject_binding(
            payload,
            binding_fixture_hash=binding_hash,
        )
        return SubjectBinding.from_fixture(
            fixture,
            cycle_id=cycle_id,
            binding_fixture_hash=binding_hash,
        )
    except Exception as exc:
        raise LocalIntegrationInitializationError("binding fixture validation failed") from exc


def initialize_local_integration(
    *,
    data_dir: str | Path,
    binding_file: str | Path,
    binding_fixture_hash: str,
    cycle_id: str,
) -> SubjectBinding:
    """Explicitly initialize or idempotently verify a formal local data directory."""

    root = _validate_data_dir(Path(data_dir))
    binding = _read_binding_file(Path(binding_file), binding_fixture_hash, cycle_id)
    empty = not root.exists() or next(root.iterdir(), None) is None
    validation_mode = IntegrationThinkingMode.DETERMINISTIC
    if empty:
        root.mkdir(parents=True, exist_ok=True)
        subject_states = SubjectStateService(JsonSubjectStateRepository(root / "subject-state"))
        binding_repository = JsonSubjectBindingRepository(root)
        awakening_repository = JsonAwakeningRepository(root)
        ledger = JsonIntegrationResultLedger(root)
        try:
            binding_repository.initialize(binding)
            state = subject_states.create(binding.subject_id)
            if state.revision != 0:
                raise LocalIntegrationInitializationError(
                    "a new integration subject must start at revision 0"
                )
            cycle = AwakeCycle.manual(
                subject_id=binding.subject_id,
                created_at=_binding_datetime(binding.effective_at),
                cycle_id=binding.cycle_id,
            )
            awakening_repository.save_cycle(cycle)
            ledger.initialize_empty()
        except Exception as exc:
            raise LocalIntegrationInitializationError(
                "formal local integration initialization did not complete"
            ) from exc
    else:
        try:
            persisted = JsonSubjectBindingRepository(root).load_active()
        except Exception as exc:
            raise LocalIntegrationInitializationError(
                "existing data directory is only partially initialized or corrupt"
            ) from exc
        if persisted != binding:
            raise LocalIntegrationInitializationError(
                "existing data directory uses a different immutable binding"
            )
        ledger = JsonIntegrationResultLedger(root)
        validation_mode = _persisted_thinking_mode(ledger)
        existing_app = build_local_integration_app(
            root,
            thinking_mode=validation_mode,
        )
        if existing_app.binding != binding:
            raise LocalIntegrationInitializationError(
                "existing data directory uses an inconsistent binding"
            )
        existing_app.ledger.initialize_capabilities()
    app = build_local_integration_app(root, thinking_mode=validation_mode)
    if app.binding != binding:
        raise LocalIntegrationInitializationError("initialized binding does not match")
    return binding


def _persisted_thinking_mode(
    ledger: JsonIntegrationResultLedger,
) -> IntegrationThinkingMode:
    """Select only the mode needed to validate existing durable history."""

    operations = ledger.list_operations()
    capability_ledger_exists = ledger.capability_path.exists()
    if any(
        operation.capability is not None
        or (
            capability_ledger_exists
            and ledger.find_capability_request_by_operation(operation.operation_id)
            is not None
        )
        for operation in operations
    ):
        return IntegrationThinkingMode.CAPABILITY
    return IntegrationThinkingMode.DETERMINISTIC


def _binding_datetime(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value[:-1] + "+00:00")


def build_local_integration_app(
    data_dir: str | Path,
    *,
    thinking_mode: IntegrationThinkingMode = IntegrationThinkingMode.DETERMINISTIC,
    capability_thinking_provider_id: str = "vio-capability-model-provider",
) -> LocalIntegrationApp:
    """Restore the formal deterministic E4 graph from an initialized directory."""

    if not isinstance(thinking_mode, IntegrationThinkingMode):
        raise LocalIntegrationInitializationError(
            "thinking mode must be deterministic or capability"
        )

    root = _validate_data_dir(Path(data_dir))
    if not root.exists() or next(root.iterdir(), None) is None:
        raise LocalIntegrationInitializationError(
            "formal local integration data has not been initialized"
        )
    try:
        binding_repository = JsonSubjectBindingRepository(root)
        binding = binding_repository.load_active()
        subject_states = SubjectStateService(JsonSubjectStateRepository(root / "subject-state"))
        awakening_repository = JsonAwakeningRepository(root)
        ledger = JsonIntegrationResultLedger(root)

        memory = MemoryService(
            DeterministicMemoryRetriever(),
            DeterministicMemoryInfluenceRecorder(),
        )
        awakening = AwakeningService(subject_states, memory, awakening_repository)
        thinking_provider = (
            DeferredCapabilityThinkingProvider(capability_thinking_provider_id)
            if thinking_mode is IntegrationThinkingMode.CAPABILITY
            else DeterministicThinkingProvider(
                result_id_factory=lambda: _uuid_id("thinking-result")
            )
        )
        thinking = ThinkingService(
            thinking_provider,
            DeterministicTokenBudgetManager(usage_id_factory=lambda: _uuid_id("usage")),
            subject_states,
            JsonThinkingRepository(root),
        )
        permission_name = "subject_state:update"
        action = ActionService(
            InMemoryPermissionProvider(
                [
                    PermissionGrant(
                        permission=permission_name,
                        subject_id=binding.subject_id,
                        valid_from=_binding_datetime(binding.effective_at) - timedelta(days=1),
                        scopes=["*"],
                    )
                ]
            ),
            InMemoryActionRepository(),
        )
        capabilities = (
            CapabilityCoordinationService(ledger)
            if thinking_mode is IntegrationThinkingMode.CAPABILITY
            else None
        )
        service = ContinuityInteractionService(
            validator=MachineContractValidator(),
            bindings=binding_repository,
            ledger=ledger,
            subject_states=subject_states,
            awakening=awakening,
            perception=PerceptionService(),
            thinking=thinking,
            action=action,
            action_evolution=ActionEvolutionService(subject_states),
            reply_composer=(
                CapabilityContractReplyComposer()
                if thinking_mode is IntegrationThinkingMode.CAPABILITY
                else DeterministicContractReplyComposer()
            ),
            available_permissions=[permission_name],
            thinking_mode=thinking_mode,
            capabilities=capabilities,
        )
        app = LocalIntegrationApp(
            adapter=IntegrationAdapter(service),
            binding=binding,
            subject_states=subject_states,
            awakening_repository=awakening_repository,
            ledger=ledger,
            data_dir=root,
            thinking_mode=thinking_mode,
        )
        app.assert_ready()
        return app
    except LocalIntegrationInitializationError:
        raise
    except Exception as exc:
        raise LocalIntegrationInitializationError(
            "formal local integration data is incomplete, corrupt, or inconsistent"
        ) from exc
