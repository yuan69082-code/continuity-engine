"""C1 input checkpoint, embedded in the existing Perception/ThinkSession journal.

This is an input snapshot, never another current state or execution ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from collections import Counter

from .action_planning import digest
from .context_composition import ContextCompositionResult, CompositionStatus
from .context_routing import ContextRouteResult
from .contradiction import ContradictionDetectionResult, ContradictionDetectionStatus
from .errors import CapabilityValidationError


def model_fragment(fragment):
    return {"id": getattr(fragment, "fragment_id", "sha256:" + "0" * 64),
            "authority": fragment.authority.value, "source": fragment.stable_source_id,
            "version": fragment.version, "hash": fragment.content_hash,
            "provenance": list(fragment.provenance_roots), "content": fragment.content}


def model_material_tokens(material):
    """Deterministic serialized-input estimate, including source metadata."""
    size = len(json.dumps(model_fragment(material), ensure_ascii=False, separators=(",", ":"))) + 1
    return (size + 3) // 4


@dataclass(frozen=True)
class ContinuityCoreContext:
    perception_hash: str
    route: ContextRouteResult
    composition: ContextCompositionResult
    contradictions: ContradictionDetectionResult
    effective_emotion: dict
    actions_enabled: bool = True
    pending_event_count: int = 0
    version: str = "c1-context-v1"
    expression_enabled: bool = False

    def __post_init__(self):
        snapshot = self.composition.snapshot
        trace = self.contradictions.trace
        if (type(self.expression_enabled) is not bool or self.version != "c1-context-v1" or type(self.actions_enabled) is not bool
                or type(self.pending_event_count) is not int or self.pending_event_count < 0
                or self.composition.status is not CompositionStatus.COMPLETE
                or snapshot is None or not snapshot.consumable
                or self.contradictions.status is not ContradictionDetectionStatus.COMPLETE
                or trace is None
                or snapshot.route_result_hash != self.route.canonical_hash()
                or (snapshot.subject_id, snapshot.environment, snapshot.source_revision,
                    snapshot.snapshot_hash) != (trace.subject_id, trace.environment,
                    trace.source_revision, trace.source_snapshot_hash)):
            raise CapabilityValidationError("C1_CONTEXT_BOUNDARY_INVALID")

    def validate_perception(self, perception):
        raw = perception.to_dict()
        raw.pop("continuity_context", None)
        snapshot = self.composition.snapshot
        if (digest(raw) != self.perception_hash or
                (perception.subject_id, perception.source_revision, perception.perception_id) !=
                (snapshot.subject_id, snapshot.source_revision, self.route.plan.request.perception_id)):
            raise CapabilityValidationError("C1_PERCEPTION_BINDING_INVALID")

    def to_dict(self):
        return {"version": self.version, "perception_hash": self.perception_hash,
                "route": self.route.to_dict(), "composition": self.composition.to_dict(),
                "contradictions": self.contradictions.to_dict(),
                "effective_emotion": self.effective_emotion, "actions_enabled": self.actions_enabled,
                "pending_event_count": self.pending_event_count,
                **({"expression_enabled": True} if self.expression_enabled else {})}

    def binding_hash(self):
        """Bind the full input and original gates, not the truth of a receipt."""
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value)-{"expression_enabled"} != {
                "version", "perception_hash", "route", "composition", "contradictions",
                "effective_emotion", "actions_enabled", "pending_event_count"}:
            raise CapabilityValidationError("C1_CONTEXT_SHAPE_INVALID")
        return cls(value["perception_hash"], ContextRouteResult.from_dict(value["route"]),
                   ContextCompositionResult.from_dict(value["composition"]),
                   ContradictionDetectionResult.from_dict(value["contradictions"]),
                   value["effective_emotion"], value["actions_enabled"], value["pending_event_count"], value["version"], value.get("expression_enabled",False))

    def model_summary(self):
        """Bounded content belongs to model input, not to the structural Trace."""
        snapshot = self.composition.snapshot
        payload = {
            "context": [model_fragment(f) for f in snapshot.fragments],
            "disputed": dict(Counter(c.proposition_id for c in self.contradictions.cases)),
            "missing": dict(Counter(n.reason_code for n in snapshot.missing_notices)),
            "emotion": self.effective_emotion,
            "direct_state_write_allowed": False,
        }
        if self.pending_event_count:
            payload["missing"]["C1_CONSOLIDATION_BACKLOG"] = self.pending_event_count
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(text) > 4096:
            raise CapabilityValidationError("C1_MODEL_INPUT_BUDGET_EXCEEDED")
        return text
