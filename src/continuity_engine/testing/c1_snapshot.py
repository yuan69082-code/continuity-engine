"""Explicit P09 additions to the existing P01 component inventory (TEST only)."""
from hashlib import sha256

from .models import SandboxOperationError
from .persistence import atomic_write_json, read_json, is_link_like

PROFILE = "fixture/c1-profile.v1.json"


def profile_for(subject_id):
    return {"version": "p09-c1-snapshot-v1", "subjectId": subject_id, "environment": "TEST"}


def initialize_profile(runtime):
    """Called only when provisioning an explicitly isolated C1 State Fixture."""
    from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
    from continuity_engine.storage.json_contradiction_repository import JsonContradictionRepository
    subject = runtime.descriptor.subject_id
    JsonMemoryRepository(runtime.data_root, environment="TEST").initialize_empty(subject)
    JsonContradictionRepository(runtime.data_root, environment="TEST").initialize_empty(subject)
    atomic_write_json(runtime.data_root / PROFILE, profile_for(subject))


def additions(data_root, subject_id):
    marker = data_root / PROFILE
    if not marker.exists():
        return {}  # Unmapped C1 files still fail P01's closed physical inventory.
    if is_link_like(marker) or read_json(marker) != profile_for(subject_id):
        raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "invalid C1 profile")
    name = sha256(subject_id.encode("utf-8")).hexdigest() + ".json"
    paths = {
        "memory": data_root / "memory" / "test" / name,
        "test_trace": data_root / "contradiction" / "test" / name,
        "action_sessions": data_root / "c1-receipts" / "p08-fake-receipts.json",
        "state_fixture": marker,
    }
    if any(not p.is_file() or is_link_like(p) for p in paths.values()):
        raise SandboxOperationError("SNAPSHOT_INCOMPLETE", "missing C1 component")
    return {key: (path, read_json(path)) for key, path in paths.items()}
