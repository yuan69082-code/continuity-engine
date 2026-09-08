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


def permission_additions(data_root, subject_id):
    """Exact existing permission records in a TEST C1 fixture, not a new store."""
    from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
    if not (data_root / PROFILE).exists():
        return []
    repository = JsonPermissionRepository(data_root)
    folder = repository._subject_dir(subject_id)
    for parent in (repository.root, folder):
        if is_link_like(parent):
            raise SandboxOperationError('SNAPSHOT_INCOMPLETE', 'unsafe permission component')
    if not folder.exists():
        return []
    result = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or is_link_like(path) or path.suffix != '.json':
            raise SandboxOperationError('SNAPSHOT_INCOMPLETE', 'unmapped permission entry')
        document = read_json(path)
        identity = document.get('state', {}).get('permission_id')
        if not identity or repository._path(subject_id, identity) != path:
            raise SandboxOperationError('SNAPSHOT_INCOMPLETE', 'permission path identity mismatch')
        permission = repository.load(subject_id, identity)
        repository.history(subject_id, identity)
        if permission.subject_id != subject_id:
            raise SandboxOperationError('SNAPSHOT_INCOMPLETE', 'permission subject mismatch')
        result.append((path, document))
    return result


def external_additions(data_root,subject_id):
    """P16's explicitly provisioned TEST components on the original P01 inventory."""
    marker=data_root/'fixture/p16-profile.json'
    if not marker.exists():return []
    expected={'version':'p16-test-v1','subject_id':subject_id,'environment':'TEST'}
    if is_link_like(marker) or read_json(marker)!=expected:
        raise SandboxOperationError('SNAPSHOT_INCOMPLETE','invalid P16 profile')
    from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
    from continuity_engine.domain.action_capability import ActionReceipt
    from continuity_engine.domain.external_capabilities import ProviderResult
    from continuity_engine.domain.action_planning import digest
    repo=JsonExternalProviderRepository(data_root,subject_id=subject_id,environment='TEST')
    paths=[('state_fixture',marker),('state_fixture',repo.registry_path),('test_trace',repo.cache_path),
           ('state_fixture',data_root/'fixture/p16-control.json'),('action_sessions',data_root/'p16-fake/facts.json')]
    if any(not p.is_file() or is_link_like(p) for _,p in paths):
        raise SandboxOperationError('SNAPSHOT_INCOMPLETE','missing P16 component')
    repo.descriptors();repo.cached()
    control=read_json(data_root/'fixture/p16-control.json')
    if (control.get('subject_id'),control.get('environment'))!=(subject_id,'TEST'):
        raise SandboxOperationError('SNAPSHOT_INCOMPLETE','invalid P16 control binding')
    data=read_json(data_root/'p16-fake/facts.json')
    if data.get('version')!='p16-fake-receipts-v1' or data.get('hash')!=digest(data.get('facts')):
        raise SandboxOperationError('SNAPSHOT_INCOMPLETE','invalid P16 facts')
    for entry in data['facts']:
        fact=ActionReceipt.from_dict(entry['receipt']);value=ProviderResult.from_dict(entry['result'])
        if (fact.subject_id,value.subject_id,fact.environment,value.environment)!=(subject_id,subject_id,'TEST','TEST') or fact.output_hash!=digest(value.to_dict()):
            raise SandboxOperationError('SNAPSHOT_INCOMPLETE','invalid P16 fact binding')
    return [(name,path,read_json(path)) for name,path in paths]
