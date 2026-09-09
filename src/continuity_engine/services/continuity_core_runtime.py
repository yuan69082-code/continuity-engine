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
               ContextSourceBinding(TimelineContextSource(timeline, environment=environment,
                   memory_repository=memory if gates.memory else None))]
    resolvers = [TrustedContextResolverBinding(
        SubjectStateMaterialResolver(state, environment=environment), ContextAuthority.CONFIRMED_STATE,
        "subject_state_section", required=True), TrustedContextResolverBinding(
        TimelineMaterialResolver(timeline, environment=environment,memory_repository=memory if gates.memory else None),
        ContextAuthority.RAW_SOURCE, "event")]
    if gates.memory:
        sources.extend([ContextSourceBinding(MemoryContextSource(memory, environment=environment)),
                        ContextSourceBinding(DerivedSummaryContextSource(memory, environment=environment))])
        resolvers.extend([TrustedContextResolverBinding(MemoryMaterialResolver(memory, environment=environment),
            ContextAuthority.CONFIRMED_MEMORY, "memory_record"), TrustedContextResolverBinding(
            DerivedSummaryMaterialResolver(memory, environment=environment), ContextAuthority.DERIVED_SUMMARY,
            "derived_summary")])
    sources.extend(extra_sources)
    resolvers.extend(extra_resolvers)
    external=options.pop('external_capabilities',None)
    if external is not None and gates.enabled:
        from .external_context_source import ExternalContextSource
        source=ExternalContextSource(external)
        sources.append(ContextSourceBinding(source))
        resolvers.append(TrustedContextResolverBinding(source,ContextAuthority.RETRIEVED_CANDIDATE,'external_candidate'))
        capabilities=(*capabilities,*external.bindings())
        options['policy']=external.policy(options.get('policy'))
    else:external=None
    execution=options.pop('execution',None)
    if execution is not None and gates.enabled:
        from .execution_context_source import ExecutionContextSource
        source=ExecutionContextSource(execution)
        sources.append(ContextSourceBinding(source))
        resolvers.append(TrustedContextResolverBinding(source,ContextAuthority.RETRIEVED_CANDIDATE,'execution_result'))
        capabilities=(*capabilities,*execution.bindings())
        options['policy']=execution.policy(options.get('policy'))
    else:
        execution=None
    repository = JsonContradictionRepository(data_dir, environment=environment,
                                              resolution_evidence_verifier=resolution_verifier)
    if options.get('subject_growth'):
        from continuity_engine.storage.json_learning_repository import JsonLearningRepository
        options['growth_repository']=JsonLearningRepository(data_dir)
    core=ContinuityCoreService(subject_id=binding.subject_id, environment=environment,
        router=ContextRouterService(sources, permission_policy=permission, enabled=gates.enabled),
        composer=ContextComposerService(resolvers, clock=clock, enabled=gates.enabled,
                                        material_token_cost=model_material_tokens),
        detector=ContradictionDetectorService(claim_resolver, repository, clock=clock,
                                              resolution_evidence_verifier=resolution_verifier),
        timeline=timeline, memory_repository=memory,
        consolidation=MemoryConsolidationService(memory, clock=clock), subject_states=subject_states,
        coordination=CapabilityCoordinationService(ledger), action_gate=action_gate, constraints=constraints,
        capabilities=capabilities, clock=clock, permission_policy=permission, gates=gates,
        external_capabilities=external, execution=execution, **options)
    if external is not None:external.bind(core)
    if execution is not None:execution.bind(core)
    return core
