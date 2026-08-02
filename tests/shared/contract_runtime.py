from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from continuity_engine.domain.action import PermissionGrant
from continuity_engine.domain.integration_contract import SubjectBindingFixture
from continuity_engine.domain.integration_hashing import calculate_state_hash
from continuity_engine.domain.models import utc_now
from continuity_engine.interfaces.contract_test_adapter import ContractTestAdapter
from continuity_engine.services.action_evolution_service import ActionEvolutionService
from continuity_engine.services.action_permissions import InMemoryPermissionProvider
from continuity_engine.services.action_service import ActionService
from continuity_engine.services.awakening_service import AwakeningService
from continuity_engine.services.contract_test_bootstrap import (
    FirstRoundContractBootstrap,
    FirstRoundContractFixture,
)
from continuity_engine.services.contract_test_doubles import (
    DeterministicContractReplyComposer,
    DeterministicMemoryInfluenceRecorder,
    DeterministicMemoryRetriever,
    DeterministicThinkingProvider,
    DeterministicTokenBudgetManager,
)
from continuity_engine.services.integration_contract_hashing import (
    calculate_binding_fixture_hash,
)
from continuity_engine.services.integration_contract_validation import (
    MachineContractValidator,
)
from continuity_engine.services.memory_service import MemoryService
from continuity_engine.services.perception_service import PerceptionService
from continuity_engine.services.subject_state_service import SubjectStateService
from continuity_engine.services.thinking_service import ThinkingService
from continuity_engine.storage.in_memory_action_repository import (
    InMemoryActionRepository,
)
from continuity_engine.storage.json_awakening_repository import (
    JsonAwakeningRepository,
)
from continuity_engine.storage.json_integration_repository import (
    JsonIntegrationResultLedger,
    JsonSubjectBindingFixtureRepository,
)
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_thinking_repository import JsonThinkingRepository


_SENTINEL_HASH = "sha256:" + ("0" * 64)


class SharedContractRuntimeError(RuntimeError):
    """A local test-runner setup or persistence failure."""


@dataclass(frozen=True, slots=True)
class SharedContractRuntime:
    adapter: ContractTestAdapter
    fixture: FirstRoundContractFixture
    subject_states: SubjectStateService
    ledger: JsonIntegrationResultLedger


def _uuid_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _is_empty_directory(path: Path) -> bool:
    return not path.exists() or (path.is_dir() and next(path.iterdir(), None) is None)


def _validate_data_dir(path: Path) -> Path:
    if path.exists() and (not path.is_dir() or path.is_symlink()):
        raise SharedContractRuntimeError("data directory must be a real directory")
    resolved = path.resolve()
    if any(part.casefold() == ".continuity-data" for part in resolved.parts):
        raise SharedContractRuntimeError("production data directories are forbidden")
    return resolved


def _load_existing_fixture(
    subject_states: SubjectStateService,
    bindings: JsonSubjectBindingFixtureRepository,
    awakening_repository: JsonAwakeningRepository,
    ledger: JsonIntegrationResultLedger,
) -> FirstRoundContractFixture:
    expected_binding = SubjectBindingFixture.first_round()
    state = subject_states.load(FirstRoundContractBootstrap.SUBJECT_ID)
    binding, binding_hash = bindings.load_fixed()
    cycle = awakening_repository.load_cycle(FirstRoundContractBootstrap.CYCLE_ID)
    if binding != expected_binding:
        raise SharedContractRuntimeError("fixed SubjectBinding does not match")
    if binding_hash != calculate_binding_fixture_hash(expected_binding):
        raise SharedContractRuntimeError("fixed SubjectBinding hash does not match")
    if cycle.subject_id != state.subject_id or state.subject_id != binding.subject_id:
        raise SharedContractRuntimeError("fixture subject identities do not match")

    # Public lookups force both persisted journals through their existing strict
    # decoders without adding a second ledger implementation to the runner.
    ledger.lookup("__shared_runner_integrity_probe__", _SENTINEL_HASH)
    ledger.load_operation("__shared_runner_integrity_probe__")

    # Cross-store checks are deliberately limited to authoritative facts already
    # exposed by the repositories: a ledger cannot refer beyond the current state,
    # and its current projection must describe that exact state.
    results = ledger._load_results()  # noqa: SLF001 - test-only integrity audit
    operations = ledger._load_operations()  # noqa: SLF001 - test-only integrity audit
    updates = subject_states.get_update_history(state.subject_id)
    update_ids = {item.update_id for item in updates}
    for result in results:
        projection = result.state_projection
        if result.subject_id != state.subject_id or projection.current_revision > state.revision:
            raise SharedContractRuntimeError("result ledger conflicts with SubjectState")
        if projection.engine_update_id is not None and projection.engine_update_id not in update_ids:
            raise SharedContractRuntimeError("result ledger references an unknown state update")
        if (
            projection.current_revision == state.revision
            and projection.snapshot.state_hash != calculate_state_hash(state)
        ):
            raise SharedContractRuntimeError("current projection conflicts with SubjectState")
    for operation in operations:
        if operation.subject_id != state.subject_id:
            raise SharedContractRuntimeError("operation journal subject does not match")
        if operation.input_revision > state.revision:
            raise SharedContractRuntimeError("operation journal conflicts with SubjectState")

    return FirstRoundContractFixture(
        subject_id=state.subject_id,
        initial_revision=state.revision,
        binding=binding,
        binding_fixture_hash=binding_hash,
        cycle_id=cycle.cycle_id,
    )


def build_shared_contract_runtime(data_dir: str | Path) -> SharedContractRuntime:
    """Build the real E3 graph using only an explicit, test-controlled directory."""
    root = _validate_data_dir(Path(data_dir))
    empty = _is_empty_directory(root)
    root.mkdir(parents=True, exist_ok=True)

    subject_states = SubjectStateService(
        JsonSubjectStateRepository(root / "subject-state")
    )
    bindings = JsonSubjectBindingFixtureRepository(root)
    awakening_repository = JsonAwakeningRepository(root)
    ledger = JsonIntegrationResultLedger(root)
    try:
        if empty:
            fixture = FirstRoundContractBootstrap(
                subject_states,
                bindings,
                awakening_repository,
            ).prepare()
        else:
            fixture = _load_existing_fixture(
                subject_states,
                bindings,
                awakening_repository,
                ledger,
            )
    except Exception as exc:
        raise SharedContractRuntimeError("test fixture or persisted data is invalid") from exc

    memory = MemoryService(
        DeterministicMemoryRetriever(),
        DeterministicMemoryInfluenceRecorder(),
    )
    awakening = AwakeningService(
        subject_states,
        memory,
        awakening_repository,
    )
    thinking = ThinkingService(
        DeterministicThinkingProvider(
            result_id_factory=lambda: _uuid_id("thinking-result")
        ),
        DeterministicTokenBudgetManager(
            usage_id_factory=lambda: _uuid_id("usage")
        ),
        subject_states,
        JsonThinkingRepository(root),
    )
    now = utc_now()
    permission = "subject_state:update"
    action = ActionService(
        InMemoryPermissionProvider(
            [
                PermissionGrant(
                    permission=permission,
                    subject_id=fixture.subject_id,
                    valid_from=now - timedelta(days=1),
                    scopes=["*"],
                )
            ]
        ),
        InMemoryActionRepository(),
    )
    adapter = ContractTestAdapter(
        validator=MachineContractValidator(),
        bindings=bindings,
        ledger=ledger,
        subject_states=subject_states,
        awakening=awakening,
        perception=PerceptionService(),
        thinking=thinking,
        action=action,
        action_evolution=ActionEvolutionService(subject_states),
        reply_composer=DeterministicContractReplyComposer(),
        cycle_id=fixture.cycle_id,
        available_permissions=[permission],
    )
    return SharedContractRuntime(
        adapter=adapter,
        fixture=fixture,
        subject_states=subject_states,
        ledger=ledger,
    )
