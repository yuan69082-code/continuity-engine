"""A pure presentation seam, not a Provider/Capability execution port.

Implementations receive only the already formed visible body and immutable
Engine decision. No state writes, network, billing, scheduling or hidden CoT.
Real model execution continues to use the existing E5-A Thinking path.
"""
from typing import Protocol
from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.expression import ExpressionDecision, PresentationCandidate


class PresentationPort(Protocol):
    def present(self, decision: ExpressionDecision, body: str) -> PresentationCandidate: ...


class DeterministicPresentation:
    def present(self, decision, body):
        return PresentationCandidate(digest(decision.to_dict()),decision.mode,body,
            decision.layout,decision.compact,decision.emphasis)
