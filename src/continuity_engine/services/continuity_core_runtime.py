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
    external=options.pop('external_capabilities',None)
    absorption=(external.absorption if external is not None and gates.enabled else None)
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
        memory_source=MemoryContextSource(memory,environment=environment)
        summary_source=DerivedSummaryContextSource(memory,environment=environment)
        memory_resolver=MemoryMaterialResolver(memory,environment=environment)
        summary_resolver=DerivedSummaryMaterialResolver(memory,environment=environment)
        if absorption is not None:
            from .external_absorption_service import (
                ExternalAwareMemorySource,ExternalAwareSummarySource,ExternalAwareMaterialResolver,
            )
            memory_source=ExternalAwareMemorySource(memory,environment=environment,absorption=absorption)
            summary_source=ExternalAwareSummarySource(memory,environment=environment,absorption=absorption)
            memory_resolver=ExternalAwareMaterialResolver(memory_resolver,memory,absorption)
            summary_resolver=ExternalAwareMaterialResolver(summary_resolver,memory,absorption,summary=True)
        sources.extend([ContextSourceBinding(memory_source),ContextSourceBinding(summary_source)])
        resolvers.extend([TrustedContextResolverBinding(memory_resolver,
            ContextAuthority.CONFIRMED_MEMORY, "memory_record"), TrustedContextResolverBinding(
            summary_resolver, ContextAuthority.DERIVED_SUMMARY,
            "derived_summary")])
    sources.extend(extra_sources)
    resolvers.extend(extra_resolvers)
    input_processing = None
    input_history = None
    if gates.enabled and gates.input_processing:
        from .input_context_source import InputContextSource
        from .input_processing_service import InputProcessingService
        source = InputContextSource(ledger, permission, clock, binding.subject_id, environment)
        input_processing = InputProcessingService(source)
        sources.append(ContextSourceBinding(source))
        resolvers.append(TrustedContextResolverBinding(source, ContextAuthority.RETRIEVED_CANDIDATE, 'current_message'))
        if gates.automatic_recall:
            from .input_context_source import HistoricalInputContextSource
            input_history=HistoricalInputContextSource(ledger,permission,clock,binding.subject_id,environment)
            sources.append(ContextSourceBinding(input_history))
            resolvers.append(TrustedContextResolverBinding(input_history,ContextAuthority.RETRIEVED_CANDIDATE,'historical_message'))
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
        if absorption is None:
            options['growth_repository']=JsonLearningRepository(data_dir)
        else:
            from .external_absorption_service import external_aware_learning_repository
            options['growth_repository']=external_aware_learning_repository(JsonLearningRepository,data_dir,absorption)
    core=ContinuityCoreService(subject_id=binding.subject_id, environment=environment,
        router=ContextRouterService(sources, permission_policy=permission, enabled=gates.enabled),
        composer=ContextComposerService(resolvers, clock=clock, enabled=gates.enabled,
                                        material_token_cost=(lambda m:model_material_tokens(m,recall=True)) if gates.automatic_recall else model_material_tokens),
        detector=ContradictionDetectorService(claim_resolver, repository, clock=clock,
                                              resolution_evidence_verifier=resolution_verifier),
        timeline=timeline, memory_repository=memory,
        consolidation=MemoryConsolidationService(memory, clock=clock), subject_states=subject_states,
        coordination=CapabilityCoordinationService(ledger), action_gate=action_gate, constraints=constraints,
        capabilities=capabilities, clock=clock, permission_policy=permission, gates=gates,
        external_capabilities=external, execution=execution, input_processing=input_processing, **options)
    if input_processing is not None:
        input_processing.core = core
    if input_history is not None:
        def current_input_root(fact):
            from continuity_engine.domain.timeline import TimelineEventStatus
            entries=core.timeline.rebuild(core.subject_id).entries
            entry=next((e for e in entries if e.event.event_id==fact.source_event_id),None)
            if entry is not None and entry.status is not TimelineEventStatus.ACTIVE:return False
            return not gates.memory or core.memory.event_recall_weights(core.subject_id).get(fact.source_event_id,1.0)>0
        input_history.current_source=current_input_root
    if external is not None:external.bind(core)
    if execution is not None:execution.bind(core)
    return core
