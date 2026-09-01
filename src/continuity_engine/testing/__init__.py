"""Test-only P01 sandbox infrastructure.

Nothing in this package is a production Subject, Memory, or recovery authority.
The package is deliberately isolated from the normal Engine entry points.
"""

from .models import (
    CleanupResult,
    RetentionMode,
    SandboxDescriptor,
    SandboxEnvironment,
    SandboxEvidence,
    SandboxLifecycle,
    SandboxOperationError,
    SnapshotComponent,
    SnapshotManifest,
    StateFixture,
)
from .sandbox import P01SandboxManager, SandboxRuntime
from .p03_timeline_fixture import (
    P03_GOLDEN_SCENARIO_VERSION,
    P03_TIME_FIXTURE_VERSION,
    P03GoldenScenarioResult,
    P03LocalEventFixtureAdapter,
    P03TemporalFactFixture,
    run_p03_golden_scenario,
)
from .p04_memory_fixture import (
    P04_GOLDEN_SCENARIO_VERSION,
    P04GoldenScenarioResult,
    run_p04_golden_scenario,
)

__all__ = [
    "CleanupResult",
    "P01SandboxManager",
    "P03_GOLDEN_SCENARIO_VERSION",
    "P03_TIME_FIXTURE_VERSION",
    "P03GoldenScenarioResult",
    "P03LocalEventFixtureAdapter",
    "P03TemporalFactFixture",
    "P04_GOLDEN_SCENARIO_VERSION",
    "P04GoldenScenarioResult",
    "RetentionMode",
    "SandboxDescriptor",
    "SandboxEnvironment",
    "SandboxEvidence",
    "SandboxLifecycle",
    "SandboxOperationError",
    "SandboxRuntime",
    "SnapshotComponent",
    "SnapshotManifest",
    "StateFixture",
    "run_p03_golden_scenario",
    "run_p04_golden_scenario",
]
