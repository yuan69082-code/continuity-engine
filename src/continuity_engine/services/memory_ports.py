from typing import Protocol, Sequence

from continuity_engine.domain.memory import (
    MemoryCandidate,
    MemoryInfluenceRecord,
    MemoryRetrievalRequest,
)


class MemoryRetriever(Protocol):
    """Port implemented by a future external memory adapter, such as MCP."""

    def retrieve(self, request: MemoryRetrievalRequest) -> Sequence[MemoryCandidate]: ...


class MemoryInfluenceRecorder(Protocol):
    """Port for sending influence records to an external memory system."""

    def record_influence(self, record: MemoryInfluenceRecord) -> None: ...
