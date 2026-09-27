"""W04-1 read-only local history contract over the original Router/Composer."""
from __future__ import annotations

from continuity_engine.domain.context_routing import ContextRouteStatus, RetrievalBudget
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.environment_access import EnvironmentAccessError, HistoryScope
from continuity_engine.domain.perception import PerceptionResult


class ScopedHistoryService:
    def __init__(self, core, *, authorize_scope, source_scope=None):
        self.core = core
        self.authorize_scope = authorize_scope
        # Optional verified source metadata. No missing software/device/session
        # is guessed from a title or a person's name.
        self.source_scope = source_scope

    def query(self, scope: HistoryScope, perception: PerceptionResult):
        if not isinstance(scope, HistoryScope) or not isinstance(perception, PerceptionResult):
            raise EnvironmentAccessError("W04_HISTORY_INPUT")
        if (scope.subject_id, scope.environment) != (self.core.subject_id, self.core.environment) or (
                perception.subject_id != scope.subject_id):
            raise EnvironmentAccessError("W04_HISTORY_BOUNDARY")
        if perception.source_revision != self.core.subject_states.load(scope.subject_id).revision:
            raise EnvironmentAccessError("W04_HISTORY_REVISION")
        self.core.subject_states.require_active(scope.subject_id, scope.environment)
        try:
            allowed = self.authorize_scope(scope, at=self.core.clock())
        except Exception:
            raise EnvironmentAccessError("W04_HISTORY_PERMISSION_UNAVAILABLE") from None
        if allowed is not True:
            raise EnvironmentAccessError("W04_HISTORY_PERMISSION_DENIED")
        if scope.mode != "LOCAL":
            return {"status": "DEPENDENCY_MISSING", "reason": "DEEP_HISTORY_ROUTE_NOT_READY",
                    "references": (), "model_calls": 0, "external_calls": 0}
        if any((scope.software_id, scope.device_id, scope.session_id)) and self.source_scope is None:
            return {"status": "DEPENDENCY_MISSING", "reason": "VERIFIED_SOURCE_SCOPE_NOT_AVAILABLE",
                    "references": (), "model_calls": 0, "external_calls": 0}
        route = self.core.router.route(
            perception, request_id="history:" + scope.query_id,
            environment=scope.environment, budget=RetrievalBudget(total_candidate_limit=30),
            recall_terms=(scope.object_id,),
        )
        if route.trace.route_status is not ContextRouteStatus.COMPLETE:
            return {"status": "BLOCKED", "reason": "SOURCE_OR_PERMISSION_UNAVAILABLE",
                    "references": (), "model_calls": 0, "external_calls": 0,
                    "trace_hash": digest(route.trace.to_dict())}
        composed = self.core.composer.compose(route, budget=self.core.context_budget)
        if composed.snapshot is None or not composed.snapshot.consumable:
            return {"status": "BLOCKED", "reason": "CONTEXT_NOT_CONSUMABLE",
                    "references": (), "model_calls": 0, "external_calls": 0}
        from continuity_engine.domain.capability import parse_capability_datetime
        begin = parse_capability_datetime(scope.from_at) if scope.from_at else None
        end = parse_capability_datetime(scope.until_at) if scope.until_at else None
        references = []
        for fragment in composed.snapshot.fragments:
            if fragment.source_id in {"engine.subject-state", "engine.current-input"}:
                continue
            if scope.source_ids and fragment.source_id not in scope.source_ids:
                continue
            occurred = fragment.occurred_at
            if (begin is not None and occurred < begin) or (end is not None and occurred > end):
                continue
            if self.source_scope is not None:
                try:
                    binding = self.source_scope(fragment)
                except Exception:
                    raise EnvironmentAccessError("W04_HISTORY_SOURCE_SCOPE_UNAVAILABLE") from None
                if not isinstance(binding, dict) or any(
                    binding.get(key) != value for key, value in (
                        ("software_id", scope.software_id), ("device_id", scope.device_id),
                        ("session_id", scope.session_id)) if value is not None
                ):
                    continue
            references.append({"source_id": fragment.source_id,
                               "stable_id": fragment.stable_source_id,
                               "version": fragment.version, "content_hash": fragment.content_hash,
                               "occurred_at": occurred.isoformat(),
                               "root_ids": tuple(fragment.provenance_roots),
                               "authority": "RETRIEVED_CANDIDATE_NOT_MEMORY"})
            if len(references) >= scope.limit:
                break
        try:
            still_allowed = self.authorize_scope(scope, at=self.core.clock())
        except Exception:
            raise EnvironmentAccessError("W04_HISTORY_PERMISSION_UNAVAILABLE") from None
        if still_allowed is not True or self.core.subject_states.load(scope.subject_id).revision != perception.source_revision:
            raise EnvironmentAccessError("W04_HISTORY_CURRENT_ACCESS_CHANGED")
        # No replay, response formation, memory write, or revision advance.
        return {"status": "AVAILABLE" if references else "NO_MATCH",
                "reason": "VERIFIED_LOCAL_REFERENCES" if references else "NO_MATCH_IN_CURRENT_SCOPE",
                "references": tuple(references), "model_calls": 0, "external_calls": 0,
                "trace_hash": digest(route.trace.to_dict()),
                "snapshot_hash": composed.snapshot.snapshot_hash}
