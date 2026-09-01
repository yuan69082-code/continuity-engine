from typing import Protocol, Sequence

from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryRecord,
    MemoryInfluenceRecord,
    MemoryRetrievalRequest,
)


class MemoryRetriever(Protocol):
    """Port implemented by a future external memory adapter, such as MCP."""

    def retrieve(self, request: MemoryRetrievalRequest) -> Sequence[MemoryCandidate]: ...


class MemoryInfluenceRecorder(Protocol):
    """Port for sending influence records to an external memory system."""

    def record_influence(self, record: MemoryInfluenceRecord) -> None: ...


class DerivedSummaryGenerator(Protocol):
    """Host-neutral P04 generator port; P04 supplies only a local deterministic fake."""

    def generate(self, memories: Sequence[MemoryRecord]) -> str: ...
