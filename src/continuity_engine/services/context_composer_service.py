from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Callable, Protocol

from continuity_engine.domain.context_composition import (
    ComposedContextFragment,
    ComposedContextSnapshot,
    CompositionDecision,
    CompositionDecisionStatus,
    CompositionStatus,
    CompositionTrace,
    ContextAuthority,
    ContextBudget,
    ContextCompositionResult,
    MissingContextNotice,
    ResolverReadCount,
    ResolvedContextMaterial,
    composition_hash,
)
from continuity_engine.domain.context_routing import (
    ContextCandidateReference,
    ContextPartition,
    ContextRouteResult,
    ContextRouteStatus,
    PartitionDecisionStatus,
)
from continuity_engine.domain.errors import (
    ContinuityEngineError,
    ContextCompositionSourceError,
    ContextCompositionValidationError,
)
from continuity_engine.services.context_material_resolvers import (
    ExactContextMaterialResolver,
)


class ContextTokenEstimator(Protocol):
    def estimate(self, content: str, *, source_type: str) -> int: ...


class DeterministicContextTokenEstimator:
    """Local deterministic estimator; it does not call a model or tokenizer service."""

    def estimate(self, content: str, *, source_type: str) -> int:
        del source_type
        return max(1, (len(content) + 3) // 4)


@dataclass(frozen=True, slots=True)
class TrustedContextResolverBinding:
    resolver: ExactContextMaterialResolver
    authority: ContextAuthority
    source_type: str
    required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "authority", ContextAuthority(self.authority))
        if not isinstance(self.source_type, str) or not self.source_type.strip():
            raise ContextCompositionValidationError("binding source_type is required")
        if not isinstance(self.required, bool):
            raise ContextCompositionValidationError("binding required must be boolean")


class ContextComposerService:
    """P06 deterministic Composer over exact references selected by P05."""

    def __init__(
        self,
        bindings: list[TrustedContextResolverBinding],
        *,
        estimator: ContextTokenEstimator | None = None,
        clock: Callable[[], datetime] | None = None,
        enabled: bool = True,
        feature_gate_version: str = "p06-context-composer-v1",
        default_token_limit: int = 2048,
    ) -> None:
        if not isinstance(enabled, bool):
            raise ContextCompositionValidationError("P06 feature gate must be boolean")
        if not isinstance(default_token_limit, int) or default_token_limit < 1:
            raise ContextCompositionValidationError("default token limit must be positive")
        if not feature_gate_version:
            raise ContextCompositionValidationError("feature_gate_version is required")
        by_source: dict[str, TrustedContextResolverBinding] = {}
        for binding in bindings:
            if not isinstance(binding, TrustedContextResolverBinding):
                raise ContextCompositionValidationError("invalid resolver binding")
            source_id = binding.resolver.source_id
            if source_id in by_source:
                raise ContextCompositionValidationError("duplicate exact resolver source")
            by_source[source_id] = binding
        self._bindings = by_source
        self._estimator = estimator or DeterministicContextTokenEstimator()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._enabled = enabled
        self._feature_gate_version = feature_gate_version
        self._default_token_limit = default_token_limit

    def compose(
        self,
        route: ContextRouteResult,
        *,
        budget: ContextBudget | None = None,
    ) -> ContextCompositionResult:
        if not isinstance(route, ContextRouteResult):
            raise ContextCompositionValidationError(
                "Composer only accepts a validated P05 ContextRouteResult"
            )
        effective_budget = budget or ContextBudget(
            token_limit=(
                route.plan.request.budget.context_budget_hint
                or self._default_token_limit
            )
        )
        if not isinstance(effective_budget, ContextBudget):
            raise ContextCompositionValidationError("composition budget is invalid")
        composed_at = self._normalized_clock()
        resolver_reads = {source_id: 0 for source_id in self._bindings}
        if not self._enabled:
            return self._route_failure(
                route,
                effective_budget,
                composed_at,
                CompositionStatus.FEATURE_GATED,
                "P06_FEATURE_GATE_DISABLED",
                resolver_reads,
            )
        if route.trace.route_status is not ContextRouteStatus.COMPLETE:
            status = (
                CompositionStatus.REJECTED
                if route.trace.route_status is ContextRouteStatus.REJECTED
                else CompositionStatus.FEATURE_GATED
                if route.trace.route_status is ContextRouteStatus.FEATURE_GATED
                else CompositionStatus.INCOMPLETE
            )
            return self._route_failure(
                route,
                effective_budget,
                composed_at,
                status,
                f"P05_ROUTE_{route.trace.route_status.value}",
                resolver_reads,
            )

        partition_required = {
            item.partition: item.required for item in route.plan.partitions
        }
        resolved: list[tuple[int, ResolvedContextMaterial]] = []
        candidate_notices: list[MissingContextNotice] = []
        upstream_notices = self._upstream_notices(route)
        decisions: dict[str, CompositionDecision] = {}
        required_failed = False

        for reference in route.manifest.candidates:
            reference_id = composition_hash(reference.to_dict())
            binding = self._bindings.get(reference.source_id)
            required = bool(partition_required.get(reference.partition, False))
            if binding is not None:
                required = required or binding.required
            if required_failed:
                candidate_notices.append(
                    MissingContextNotice(
                        reference_id,
                        reference.source_id,
                        reference.stable_id,
                        required,
                        "NOT_RESOLVED_AFTER_REQUIRED_FAILURE",
                    )
                )
                decisions[reference_id] = CompositionDecision(
                    reference_id,
                    reference.source_id,
                    reference.stable_id,
                    CompositionDecisionStatus.MISSING,
                    "NOT_RESOLVED_AFTER_REQUIRED_FAILURE",
                )
                continue
            reason = self._reference_failure_reason(route, reference, binding)
            if reason is not None:
                candidate_notices.append(
                    MissingContextNotice(
                        reference_id,
                        reference.source_id,
                        reference.stable_id,
                        required,
                        reason,
                    )
                )
                decisions[reference_id] = CompositionDecision(
                    reference_id,
                    reference.source_id,
                    reference.stable_id,
                    CompositionDecisionStatus.MISSING,
                    reason,
                )
                required_failed = required_failed or required
                continue
            try:
                resolver_reads[reference.source_id] += 1
                payload = binding.resolver.resolve(reference)
                material = self._seal_material(
                    route,
                    reference,
                    reference_id,
                    binding,
                    payload,
                    required,
                )
            except ContinuityEngineError as exc:
                reason = self._source_failure_reason(exc, required=required)
                candidate_notices.append(
                    MissingContextNotice(
                        reference_id,
                        reference.source_id,
                        reference.stable_id,
                        required,
                        reason,
                    )
                )
                decisions[reference_id] = CompositionDecision(
                    reference_id,
                    reference.source_id,
                    reference.stable_id,
                    CompositionDecisionStatus.MISSING,
                    reason,
                    binding.authority,
                )
                required_failed = required_failed or required
                continue
            resolved.append((reference.rank, material))

        if required_failed:
            for _, material in resolved:
                decisions[material.reference_id] = CompositionDecision(
                    material.reference_id,
                    material.source_id,
                    material.stable_source_id,
                    CompositionDecisionStatus.EXCLUDED,
                    "COMPOSITION_NOT_CONSUMABLE_REQUIRED_SOURCE_FAILURE",
                    material.authority,
                )
            return self._finish_failure(
                route,
                effective_budget,
                composed_at,
                CompositionStatus.INCOMPLETE,
                "REQUIRED_CONTEXT_SOURCE_UNAVAILABLE",
                resolved,
                candidate_notices,
                upstream_notices,
                decisions,
                resolver_reads,
            )

        unique: list[tuple[int, ResolvedContextMaterial, int]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for rank, material in resolved:
            key = (
                material.source_id,
                material.stable_source_id,
                material.version,
                material.content_hash,
            )
            tokens = self._estimator.estimate(
                material.content, source_type=material.source_type
            )
            if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 1:
                raise ContextCompositionValidationError(
                    "context token estimator returned an invalid cost"
                )
            if key in seen:
                decisions[material.reference_id] = CompositionDecision(
                    material.reference_id,
                    material.source_id,
                    material.stable_source_id,
                    CompositionDecisionStatus.DEDUPLICATED,
                    "EXACT_REFERENCE_DUPLICATE",
                    material.authority,
                    tokens,
                )
                continue
            seen.add(key)
            unique.append((rank, material, tokens))

        ordered = sorted(unique, key=lambda item: (not item[1].protected, item[0]))
        protected = [item for item in ordered if item[1].protected]
        protected_tokens = sum(item[2] for item in protected)
        if (
            len(protected) > effective_budget.core_fragment_limit
            or protected_tokens > effective_budget.token_limit
        ):
            for _, material, tokens in ordered:
                decisions[material.reference_id] = CompositionDecision(
                    material.reference_id,
                    material.source_id,
                    material.stable_source_id,
                    CompositionDecisionStatus.EXCLUDED,
                    "INSUFFICIENT_CONTEXT_BUDGET",
                    material.authority,
                    tokens,
                )
            return self._finish_failure(
                route,
                effective_budget,
                composed_at,
                CompositionStatus.INSUFFICIENT_CONTEXT_BUDGET,
                "INSUFFICIENT_CONTEXT_BUDGET",
                resolved,
                candidate_notices,
                upstream_notices,
                decisions,
                resolver_reads,
            )

        retained: list[tuple[ResolvedContextMaterial, int]] = []
        token_total = 0
        for _, material, tokens in ordered:
            if len(retained) >= effective_budget.core_fragment_limit:
                decisions[material.reference_id] = CompositionDecision(
                    material.reference_id,
                    material.source_id,
                    material.stable_source_id,
                    CompositionDecisionStatus.EXCLUDED,
                    "CONTEXT_FRAGMENT_LIMIT",
                    material.authority,
                    tokens,
                )
                continue
            if token_total + tokens > effective_budget.token_limit:
                decisions[material.reference_id] = CompositionDecision(
                    material.reference_id,
                    material.source_id,
                    material.stable_source_id,
                    CompositionDecisionStatus.EXCLUDED,
                    "CONTEXT_TOKEN_BUDGET_EXHAUSTED",
                    material.authority,
                    tokens,
                )
                continue
            retained.append((material, tokens))
            token_total += tokens
            decisions[material.reference_id] = CompositionDecision(
                material.reference_id,
                material.source_id,
                material.stable_source_id,
                CompositionDecisionStatus.RETAINED,
                "PROTECTED_CONTEXT_RETAINED"
                if material.protected
                else "VERIFIED_CONTEXT_RETAINED",
                material.authority,
                tokens,
            )

        fragments = tuple(
            self._fragment(material, tokens, rank)
            for rank, (material, tokens) in enumerate(retained, start=1)
        )
        trace = self._trace(
            route,
            effective_budget,
            composed_at,
            CompositionStatus.COMPLETE,
            resolved,
            candidate_notices,
            upstream_notices,
            decisions,
            resolver_reads,
            token_total,
        )
        snapshot = ComposedContextSnapshot(
            snapshot_id=f"context-snapshot:{route.plan.request.request_id}",
            request_id=route.plan.request.request_id,
            subject_id=route.plan.request.subject_id,
            environment=route.plan.request.environment,
            source_revision=route.plan.request.source_revision,
            composed_at=composed_at,
            route_result_hash=route.canonical_hash(),
            route_plan_hash=route.plan.canonical_hash(),
            manifest_hash=route.manifest.manifest_hash or "",
            budget=effective_budget,
            fragments=fragments,
            missing_notices=tuple(candidate_notices + upstream_notices),
        )
        return ContextCompositionResult(CompositionStatus.COMPLETE, trace, snapshot)

    def _seal_material(
        self,
        route: ContextRouteResult,
        reference: ContextCandidateReference,
        reference_id: str,
        binding: TrustedContextResolverBinding,
        payload,
        required: bool,
    ) -> ResolvedContextMaterial:
        request = route.plan.request
        if (
            payload.source_id != reference.source_id
            or payload.partition is not reference.partition
            or payload.stable_source_id != reference.stable_id
        ):
            raise ContextCompositionSourceError("MATERIAL_PROVENANCE_INVALID")
        if payload.subject_id != request.subject_id:
            raise ContextCompositionSourceError("SOURCE_SUBJECT_MISMATCH")
        if payload.environment != request.environment:
            raise ContextCompositionSourceError("SOURCE_ENVIRONMENT_MISMATCH")
        if payload.version != reference.version:
            raise ContextCompositionSourceError("SOURCE_VERSION_DRIFT")
        if payload.content_hash != reference.content_hash:
            raise ContextCompositionSourceError("SOURCE_HASH_DRIFT")
        if not isinstance(payload.content, str) or not payload.content.strip():
            raise ContextCompositionSourceError("MATERIAL_CONTENT_MISSING")
        if not payload.provenance_roots:
            raise ContextCompositionSourceError("MATERIAL_PROVENANCE_INVALID")
        return ResolvedContextMaterial(
            reference_id=reference_id,
            source_id=reference.source_id,
            partition=reference.partition,
            stable_source_id=reference.stable_id,
            subject_id=reference.subject_id,
            environment=reference.environment,
            version=reference.version,
            content_hash=reference.content_hash,
            source_type=binding.source_type,
            authority=binding.authority,
            occurred_at=payload.occurred_at,
            relevance=reference.score,
            confidence=payload.confidence,
            provenance_roots=tuple(payload.provenance_roots),
            content=payload.content,
            required=required,
            protected=payload.protected,
            protection_role=payload.protection_role,
            conflict_markers=tuple(payload.conflict_markers),
            missing_markers=tuple(payload.missing_markers),
        )

    @staticmethod
    def _fragment(
        material: ResolvedContextMaterial,
        tokens: int,
        rank: int,
    ) -> ComposedContextFragment:
        fragment_id = composition_hash(
            {
                "reference_id": material.reference_id,
                "authority": material.authority.value,
                "source_type": material.source_type,
            }
        )
        return ComposedContextFragment(
            fragment_id=fragment_id,
            reference_id=material.reference_id,
            subject_id=material.subject_id,
            environment=material.environment,
            authority=material.authority,
            source_id=material.source_id,
            source_type=material.source_type,
            stable_source_id=material.stable_source_id,
            version=material.version,
            content_hash=material.content_hash,
            occurred_at=material.occurred_at,
            relevance=material.relevance,
            confidence=material.confidence,
            provenance_roots=material.provenance_roots,
            conflict_markers=material.conflict_markers,
            missing_markers=material.missing_markers,
            estimated_tokens=tokens,
            rank=rank,
            retained_reason=(
                "PROTECTED_CONTEXT_RETAINED"
                if material.protected
                else "VERIFIED_CONTEXT_RETAINED"
            ),
            content=material.content,
            protected=material.protected,
            protection_role=material.protection_role,
        )

    def _route_failure(
        self,
        route: ContextRouteResult,
        budget: ContextBudget,
        composed_at: datetime,
        status: CompositionStatus,
        error_code: str,
        resolver_reads: dict[str, int],
    ) -> ContextCompositionResult:
        upstream_notices = self._upstream_notices(route)
        candidate_notices = [
            MissingContextNotice(
                composition_hash(item.to_dict()),
                item.source_id,
                item.stable_id,
                True,
                error_code,
            )
            for item in route.manifest.candidates
        ]
        decisions = {
            item.reference_id: CompositionDecision(
                item.reference_id,
                item.source_id,
                item.stable_source_id,
                CompositionDecisionStatus.MISSING,
                error_code,
            )
            for item in candidate_notices
        }
        return self._finish_failure(
            route,
            budget,
            composed_at,
            status,
            error_code,
            [],
            candidate_notices,
            upstream_notices,
            decisions,
            resolver_reads,
        )

    def _finish_failure(
        self,
        route: ContextRouteResult,
        budget: ContextBudget,
        composed_at: datetime,
        status: CompositionStatus,
        error_code: str,
        resolved: list[tuple[int, ResolvedContextMaterial]],
        candidate_notices: list[MissingContextNotice],
        upstream_notices: list[MissingContextNotice],
        decisions: dict[str, CompositionDecision],
        resolver_reads: dict[str, int],
    ) -> ContextCompositionResult:
        trace = self._trace(
            route,
            budget,
            composed_at,
            status,
            resolved,
            candidate_notices,
            upstream_notices,
            decisions,
            resolver_reads,
            0,
        )
        return ContextCompositionResult(status, trace, None, error_code)

    def _trace(
        self,
        route: ContextRouteResult,
        budget: ContextBudget,
        composed_at: datetime,
        status: CompositionStatus,
        resolved: list[tuple[int, ResolvedContextMaterial]],
        candidate_notices: list[MissingContextNotice],
        upstream_notices: list[MissingContextNotice],
        decisions: dict[str, CompositionDecision],
        resolver_reads: dict[str, int],
        tokens_used: int,
    ) -> CompositionTrace:
        ordered_ids = [composition_hash(item.to_dict()) for item in route.manifest.candidates]
        ordered_decisions = tuple(decisions[item] for item in ordered_ids)
        counts = {item: 0 for item in CompositionDecisionStatus}
        for item in ordered_decisions:
            counts[item.status] += 1
        return CompositionTrace(
            trace_id=f"composition-trace:{route.plan.request.request_id}",
            request_id=route.plan.request.request_id,
            subject_id=route.plan.request.subject_id,
            environment=route.plan.request.environment,
            source_revision=route.plan.request.source_revision,
            composed_at=composed_at,
            status=status,
            route_result_hash=route.canonical_hash(),
            route_plan_hash=route.plan.canonical_hash(),
            manifest_hash=route.manifest.manifest_hash or "",
            p05_trace_hash=composition_hash(route.trace.to_dict()),
            feature_gate_version=self._feature_gate_version,
            budget=budget,
            candidate_count=len(route.manifest.candidates),
            resolved_count=len(resolved),
            retained_count=counts[CompositionDecisionStatus.RETAINED],
            deduplicated_count=counts[CompositionDecisionStatus.DEDUPLICATED],
            excluded_count=counts[CompositionDecisionStatus.EXCLUDED],
            missing_count=len(candidate_notices),
            upstream_notice_count=len(upstream_notices),
            resolver_read_count=sum(resolver_reads.values()),
            resolver_read_counts=tuple(
                ResolverReadCount(source_id, resolver_reads[source_id])
                for source_id in sorted(resolver_reads)
            ),
            tokens_used=tokens_used,
            decisions=ordered_decisions,
            upstream_notices=tuple(upstream_notices),
        )

    @staticmethod
    def _reference_failure_reason(
        route: ContextRouteResult,
        reference: ContextCandidateReference,
        binding: TrustedContextResolverBinding | None,
    ) -> str | None:
        if reference.subject_id != route.plan.request.subject_id:
            return "SOURCE_SUBJECT_MISMATCH"
        if reference.environment != route.plan.request.environment:
            return "SOURCE_ENVIRONMENT_MISMATCH"
        if binding is None:
            return "SOURCE_MISSING"
        if binding.resolver.partition is not reference.partition:
            return "MATERIAL_PROVENANCE_INVALID"
        return None

    @staticmethod
    def _source_failure_reason(
        error: ContinuityEngineError,
        *,
        required: bool,
    ) -> str:
        value = str(error)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", value):
            return value
        return (
            "REQUIRED_SOURCE_RESOLUTION_FAILED"
            if required
            else "OPTIONAL_SOURCE_RESOLUTION_FAILED"
        )

    @staticmethod
    def _upstream_notices(route: ContextRouteResult) -> list[MissingContextNotice]:
        required = {item.partition: item.required for item in route.plan.partitions}
        notices: list[MissingContextNotice] = []
        reasons = {
            PartitionDecisionStatus.NOT_OPENED: "ROUTER_PARTITION_NOT_OPENED",
            PartitionDecisionStatus.UNAVAILABLE: "ROUTER_PARTITION_UNAVAILABLE",
            PartitionDecisionStatus.FEATURE_GATED: "ROUTER_PARTITION_FEATURE_GATED",
            PartitionDecisionStatus.REJECTED: "ROUTER_PARTITION_REJECTED",
        }
        for item in route.trace.partition_traces:
            reason = reasons.get(item.status)
            if item.status is PartitionDecisionStatus.OPENED and item.candidate_count == 0:
                reason = "ROUTER_PARTITION_EMPTY"
            if reason is None:
                continue
            notices.append(
                MissingContextNotice(
                    composition_hash(item.to_dict()),
                    "p05.route",
                    f"partition:{item.partition.value}",
                    bool(required.get(item.partition, False)),
                    reason,
                )
            )
        return notices

    def _normalized_clock(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ContextCompositionValidationError("Composer clock must be timezone-aware")
        return value.astimezone(timezone.utc)
