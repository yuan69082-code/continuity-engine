"""Host-neutral C1 dependency composition for build_local_integration_app.

No initializer, network, provider transport, fixture, or production data access.
"""
from continuity_engine.domain.context_composition import ContextAuthority
from continuity_engine.domain.continuity_core import model_material_tokens
from continuity_engine.services.context_router_service import (
    ContextRouterService, ContextSourceBinding, EnginePrivateContextPermissionPolicy,
    SubjectStateContextSource, MemoryContextSource, DerivedSummaryContextSource, TimelineContextSource,
    ContextPermissionDecision,
)
from continuity_engine.services.context_composer_service import ContextComposerService, TrustedContextResolverBinding
from continuity_engine.services.context_material_resolvers import (
    SubjectStateMaterialResolver, MemoryMaterialResolver, DerivedSummaryMaterialResolver, TimelineMaterialResolver,
)
from continuity_engine.services.timeline_service import TimelineService
from continuity_engine.services.memory_consolidation_service import MemoryConsolidationService
from continuity_engine.services.contradiction_detector_service import ContradictionDetectorService
from continuity_engine.services.capability_coordination_service import CapabilityCoordinationService
from continuity_engine.storage.json_repository import JsonSubjectStateRepository
from continuity_engine.storage.json_memory_repository import JsonMemoryRepository
from continuity_engine.storage.json_contradiction_repository import JsonContradictionRepository
from .continuity_core_service import ContinuityCoreService, ContinuityCoreGates


class ContinuityCorePermissionPolicy(EnginePrivateContextPermissionPolicy):
    """P05 read policy plus current, exact-reference permission for new C1 work.

    A host with finer ACLs must override authorize_reference as well as its P05
    candidate policy. Missing this port fails closed; a route is not a grant.
    """
    def authorize_reference(self, request, reference):
        allowed = (reference.subject_id == request.subject_id
                   and reference.environment == request.environment)
        return ContextPermissionDecision(allowed, "REFERENCE_AUTHORIZED" if allowed
                                         else "REFERENCE_BOUNDARY_DENIED", self.policy_version)


def build_continuity_core(*, data_dir, binding, ledger, subject_states, action_gate, clock,
                          environment, constraints, capabilities, claim_resolver,
                          resolution_verifier=None, permission_policy=None, gates=None,
                          extra_sources=(), extra_resolvers=(), **options):
    gates = gates or ContinuityCoreGates()
    permission = permission_policy or ContinuityCorePermissionPolicy()
    state = JsonSubjectStateRepository(data_dir / "subject-state")
    timeline = TimelineService(state)
    memory = JsonMemoryRepository(data_dir, environment=environment)
    sources = [ContextSourceBinding(SubjectStateContextSource(state, environment=environment), required=True),
               ContextSourceBinding(TimelineContextSource(timeline, environment=environment))]
    resolvers = [TrustedContextResolverBinding(
        SubjectStateMaterialResolver(state, environment=environment), ContextAuthority.CONFIRMED_STATE,
        "subject_state_section", required=True), TrustedContextResolverBinding(
        TimelineMaterialResolver(timeline, environment=environment), ContextAuthority.RAW_SOURCE, "event")]
    if gates.memory:
        sources.extend([ContextSourceBinding(MemoryContextSource(memory, environment=environment)),
                        ContextSourceBinding(DerivedSummaryContextSource(memory, environment=environment))])
        resolvers.extend([TrustedContextResolverBinding(MemoryMaterialResolver(memory, environment=environment),
            ContextAuthority.CONFIRMED_MEMORY, "memory_record"), TrustedContextResolverBinding(
            DerivedSummaryMaterialResolver(memory, environment=environment), ContextAuthority.DERIVED_SUMMARY,
            "derived_summary")])
    sources.extend(extra_sources)
    resolvers.extend(extra_resolvers)
    repository = JsonContradictionRepository(data_dir, environment=environment,
                                              resolution_evidence_verifier=resolution_verifier)
    return ContinuityCoreService(subject_id=binding.subject_id, environment=environment,
        router=ContextRouterService(sources, permission_policy=permission, enabled=gates.enabled),
        composer=ContextComposerService(resolvers, clock=clock, enabled=gates.enabled,
                                        material_token_cost=model_material_tokens),
        detector=ContradictionDetectorService(claim_resolver, repository, clock=clock,
                                              resolution_evidence_verifier=resolution_verifier),
        timeline=timeline, memory_repository=memory,
        consolidation=MemoryConsolidationService(memory, clock=clock), subject_states=subject_states,
        coordination=CapabilityCoordinationService(ledger), action_gate=action_gate, constraints=constraints,
        capabilities=capabilities, clock=clock, permission_policy=permission, gates=gates, **options)
