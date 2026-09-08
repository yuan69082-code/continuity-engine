"""Local read-only experiment projection over existing state and Evolution.

Detailed reads are Owner-only via a trusted host identity port AND current
PermissionService grants. This is not a production authentication deployment.
No logger, allocation, provider, runtime or state-mutating dependency is called.
"""
from copy import deepcopy
from dataclasses import dataclass, replace

from continuity_engine.domain.action_planning import digest
from .mind_ports import VerifiedMindReader


class MindAccessError(PermissionError):
    pass


@dataclass(frozen=True)
class MindVisibilityPolicy:
    mode: str = 'DETAILED'
    export_allowed: bool = False
    extra_observation_retention: str = 'UNCONFIGURED'
    maximum_history_records: int = 64

    def __post_init__(self):
        if (self.mode not in {'DETAILED', 'SUMMARY', 'PRIVATE'}
                or type(self.export_allowed) is not bool
                or self.extra_observation_retention != 'UNCONFIGURED'
                or type(self.maximum_history_records) is not int
                or not 1 <= self.maximum_history_records <= 256):
            raise MindAccessError('MIND_VISIBILITY_POLICY_INVALID')


class MindProjectionService:
    def __init__(self, subject_states, permissions, identity_port, *, subject_id,
                 environment, owner_principal_id, policy=None):
        if environment not in {'TEST', 'RESEARCH'} or not owner_principal_id:
            raise MindAccessError('MIND_PROJECTION_BOUNDARY_INVALID')
        self.states, self.permissions, self.identity = subject_states, permissions, identity_port
        self.subject_id, self.environment, self.owner = subject_id, environment, owner_principal_id
        self.policy = policy or MindVisibilityPolicy()

    def with_policy(self, policy):
        if not isinstance(policy, MindVisibilityPolicy):
            raise MindAccessError('MIND_VISIBILITY_POLICY_INVALID')
        return type(self)(self.states, self.permissions, self.identity, subject_id=self.subject_id,
                          environment=self.environment, owner_principal_id=self.owner, policy=policy)

    def read_growth(self, session_handle, *, allowed_objects=None, export=False):
        """Explicit TEST/Research relationship policy; never a production default.

        Uses the existing authenticated Owner/permission gate. The caller is the
        trusted host policy composer, not model text or an external owner flag.
        History is structural here: a full Event may include other objects.
        """
        if allowed_objects is None:
            raise MindAccessError('GROWTH_VISIBILITY_POLICY_NOT_READY')
        if (not isinstance(allowed_objects,tuple) or type(export) is not bool
                or any(not isinstance(x,str) or not x for x in allowed_objects)):
            raise MindAccessError('GROWTH_VISIBILITY_POLICY_INVALID')
        policy=self.policy
        binding=(self.subject_id,self.environment,self.owner)
        self._authorize(session_handle,export)
        state=self.states.load(self.subject_id)
        if state.subject_id!=self.subject_id:
            raise MindAccessError('GROWTH_PROJECTION_SUBJECT_MISMATCH')
        snapshot_hash=digest(state.to_dict())
        result={'subject_id':self.subject_id,'environment':self.environment,'source_revision':state.revision,
                'read_only':True,'policy_scope':list(allowed_objects),'physical_erasure_claimed':False}
        for name,value in [('narrative',state.identity.self_narrative),('relationships',state.relationship.objects)]:
            if value is not None and (value['subject_id'],value['environment'])!=(self.subject_id,self.environment):
                raise MindAccessError('GROWTH_PROJECTION_BOUNDARY_INVALID')
            projected=deepcopy(value)
            if projected is not None:
                projected['entries']=[entry for entry in projected['entries'] if entry['object_id'] in allowed_objects]
            if self.policy.mode=='SUMMARY':
                projected=None if projected is None else {'entry_count':len(projected['entries']),'authority':projected['authority']}
            result[name]=projected
        result['source_hash']=digest([state.identity.self_narrative,state.relationship.objects])
        current=self.states.load(self.subject_id)
        if (current.subject_id!=self.subject_id or digest(current.to_dict())!=snapshot_hash
                or self.policy!=policy or (self.subject_id,self.environment,self.owner)!=binding):
            raise MindAccessError('GROWTH_PROJECTION_CHANGED_DURING_READ')
        self._authorize(session_handle,export)
        return result

    def _authorize(self, session_handle, export):
        principal = self.identity.resolve(session_handle)
        if (not isinstance(principal, VerifiedMindReader) or principal.principal_id != self.owner
                or principal.subject_id != self.subject_id or principal.environment != self.environment):
            raise MindAccessError('MIND_OWNER_IDENTITY_DENIED')
        if self.policy.mode == 'PRIVATE':
            raise MindAccessError('MIND_PRIVATE_VISIBILITY')
        if export and not self.policy.export_allowed:
            raise MindAccessError('MIND_EXPORT_POLICY_DENIED')
        scope = 'mind:' + self.environment + ':' + self.subject_id + ':' + self.owner
        context = self.permissions.get_context(self.subject_id)
        required = ['mind:read:' + self.policy.mode.lower()]
        if self.policy.mode == 'DETAILED':
            required.append('mind:read:history')
        if export:
            required.append('mind:export')
        if not all(context.has_capability(capability, scope) for capability in required):
            raise MindAccessError('MIND_CURRENT_PERMISSION_DENIED')

    def read(self, session_handle, *, export=False):
        if type(export) is not bool:
            raise MindAccessError('MIND_EXPORT_FLAG_INVALID')
        self._authorize(session_handle, export)
        state = self.states.load(self.subject_id)
        if state.subject_id != self.subject_id:
            raise MindAccessError('MIND_PROJECTION_SUBJECT_MISMATCH')
        mind = state.intentions.dynamic_mind
        if mind is not None and mind['environment'] != self.environment:
            raise MindAccessError('MIND_PROJECTION_ENVIRONMENT_MISMATCH')
        result = {'subject_id': self.subject_id, 'environment': self.environment,
                  'source_revision': state.revision, 'source_hash': digest(mind),
                  'mode': self.policy.mode, 'export_allowed': self.policy.export_allowed,
                  'extra_observation_retention': self.policy.extra_observation_retention,
                  'read_only': True, 'historical_copy_recall_claimed': False}
        if self.policy.mode == 'DETAILED':
            history = [u for u in self.states.get_update_history(self.subject_id)
                       if any(c.field_path == 'intentions.dynamic_mind' for c in u.changes)]
            result.update(mind=deepcopy(mind), history=[u.to_dict() for u in history[-self.policy.maximum_history_records:]],
                          history_omitted=max(0, len(history) - self.policy.maximum_history_records))
        else:
            result['summary'] = None if mind is None else {
                'episode_count': len(mind['episodes']), 'desire_count': len(mind['desires']),
                'conflict_count': len(mind['conflicts']), 'thought_count': len(mind['thoughts']),
                'updated_at': mind['updated_at']}
        current = self.states.load(self.subject_id)
        if current.revision != state.revision or digest(current.intentions.dynamic_mind) != result['source_hash']:
            raise MindAccessError('MIND_PROJECTION_CHANGED_DURING_READ')
        self._authorize(session_handle, export)
        return result
