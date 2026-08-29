from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from continuity_engine.domain.capability import IntegrationThinkingMode
from continuity_engine.interfaces.local_integration_app import (
    LocalIntegrationApp,
    build_local_integration_app,
)
from continuity_engine.services.model_capability_service import ModelCapabilityService
from continuity_engine.services.model_provider_ports import ModelProfilePolicy, ModelProvider
from continuity_engine.storage.json_model_execution_repository import (
    JsonModelExecutionRepository,
)


@dataclass(frozen=True, slots=True)
class LocalModelCapabilityApp:
    """Engine-local P02 assembly; the Provider remains injected and host-neutral."""

    integration: LocalIntegrationApp
    models: ModelCapabilityService
    model_ledger: JsonModelExecutionRepository


def build_local_model_capability_app(
    data_dir: str | Path,
    *,
    provider: ModelProvider,
    profiles: ModelProfilePolicy,
    clock: Callable[[], datetime],
    fault_injector=None,
) -> LocalModelCapabilityApp:
    integration = build_local_integration_app(
        data_dir,
        thinking_mode=IntegrationThinkingMode.CAPABILITY,
        capability_thinking_provider_id="engine-host-neutral-model-capability",
    )
    ledger = JsonModelExecutionRepository(data_dir)
    models = ModelCapabilityService(
        integration=integration.adapter,
        provider=provider,
        profiles=profiles,
        repository=ledger,
        clock=clock,
        fault_injector=fault_injector,
    )
    return LocalModelCapabilityApp(integration, models, ledger)
