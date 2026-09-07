"""P12 isolated lifecycle command entry. No production policy or erase operation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile

from continuity_engine.domain.memory_lifecycle import MemoryLifecycleCommand, LifecycleAction, ForgettingPolicy
from continuity_engine.services.memory_lifecycle_service import MemoryLifecycleService, TimelineMemorySources
from continuity_engine.services.memory_consolidation_service import MemoryConsolidationService
from continuity_engine.services.permission_service import PermissionService
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_permission_repository import JsonPermissionRepository
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from .p04_memory_fixture import run_p04_golden_scenario
from .p08_action_fixture import _validate_fixture_root


class P12MemoryFixture:
    """Only independent Temp roots. Confirmation registry is TEST input, not authority."""
    def __init__(self, root, *, formal_data_roots=(), protected_paths=()):
        self.root=_validate_fixture_root(Path(root),formal_data_roots=formal_data_roots,protected_paths=protected_paths)
        self.now=datetime(2026,9,6,tzinfo=timezone.utc)
        self.golden=run_p04_golden_scenario(self.root)
        self.subject_id=self.golden.p03.subject_state.subject_id
        self.approved={}
        self.permissions=PermissionService(JsonPermissionRepository(self.root),clock=lambda:self.now)
        self.permission=self.permissions.create_permission(self.subject_id,permission_id='p12-test-permission',
            permission_type='TEST',name='P12 explicit TEST grant',description='TEST lifecycle only',scope=['*'],
            capabilities=['memory.lifecycle.'+x for x in ('deactivate','archive','restore','delete','downweight','decay','trace','recall')],
            source='p12-test',reason='explicit isolated test').permission
        self.reopen()

    def reopen(self):
        self.repository=JsonMemoryRepository(self.root,environment='TEST')
        self.timeline=TimelineService(JsonSubjectStateRepository(self.root))
        self.sources=TimelineMemorySources(self.timeline,self.repository,self.subject_id)
        self.service=MemoryLifecycleService(self.repository,subject_id=self.subject_id,environment='TEST',
            permissions=self.permissions,clock=lambda:self.now,source_snapshot=self.sources,
            confirmation_verifier=lambda c:self.approved.get(c.confirmation_id)==c.canonical_hash(),allow_test_delete=True)
        self.consolidation=MemoryConsolidationService(self.repository,clock=lambda:self.now)
        return self.service

    def command(self,memory_id,action,*,command_id=None,factor=None,policy=None):
        memory=self.repository.load_memory(self.subject_id,memory_id)
        identifier=command_id or f'p12:{memory_id}:{memory.revision}:{LifecycleAction(action).value}'
        sources=self.sources(memory) or {'invalid':'invalid'}
        command=MemoryLifecycleCommand(identifier,self.subject_id,'TEST',memory_id,LifecycleAction(action),
            memory.revision,memory.canonical_hash(),self.permission.permission_id,self.permission.revision,
            memory.scope,'explicit synthetic lifecycle command',self.now,self.now+timedelta(hours=1),
            'confirmation:'+identifier,tuple(sorted(sources.items())),factor,policy)
        self.approved[command.confirmation_id]=command.canonical_hash()
        return command


def run_golden(root):
    fixture=P12MemoryFixture(root)
    memory=fixture.golden.memories[0]
    initial=len(fixture.repository.list_memories(fixture.subject_id))
    fixture.service.submit(fixture.command(memory.memory_id,'downweight',factor=.5))
    fixture.now+=timedelta(days=7)
    fixture.service.submit(fixture.command(memory.memory_id,'decay',policy=ForgettingPolicy('TEST-seven-days',7*86400)))
    weight=fixture.repository.load_memory(fixture.subject_id,memory.memory_id).effective_weight
    fixture.service.submit(fixture.command(memory.memory_id,'archive'))
    after=len(fixture.repository.list_memories(fixture.subject_id))
    fixture.reopen()
    fixture.service.submit(fixture.command(memory.memory_id,'restore'))
    deletion=fixture.command(memory.memory_id,'delete')
    fixture.service.submit(deletion)
    fixture.reopen()
    replay=fixture.service.submit(deletion)
    return {'version':'p12-memory-golden-v1','environment':'TEST','logicalDays':7,'initialRecall':initial,
            'archivedRecall':after,'weightAfterDownweightAndDecay':weight,
            'restartPoints':2,'finalLifecycle':replay.lifecycle,'deleteReplay':replay.replay,
            'physicalErasure':'NOT_READY','productionPolicy':'UNCONFIGURED'}


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='continuity-p12-') as directory:
        print(json.dumps(run_golden(Path(directory)),ensure_ascii=False,indent=2))
