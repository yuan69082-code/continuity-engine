from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INTEGRATION_HOST = "127.0.0.1"
DEFAULT_INTEGRATION_PORT = 8766
INTEGRATION_TOKEN_ENV = "CONTINUITY_ENGINE_INTEGRATION_TOKEN"
MAX_REQUEST_BODY_BYTES = 1_048_576
DEFAULT_READ_TIMEOUT_SECONDS = 10.0


class IntegrationConfigurationError(ValueError):
    """Invalid local integration process configuration."""


@dataclass(frozen=True, slots=True)
class IntegrationServerConfig:
    data_dir: Path
    service_token: str
    port: int = DEFAULT_INTEGRATION_PORT
    host: str = DEFAULT_INTEGRATION_HOST
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.host != DEFAULT_INTEGRATION_HOST:
            raise IntegrationConfigurationError(
                "the local integration server may only bind 127.0.0.1"
            )
        if isinstance(self.port, bool) or not isinstance(self.port, int):
            raise IntegrationConfigurationError("port must be an integer")
        if not 1 <= self.port <= 65535:
            raise IntegrationConfigurationError("port must be between 1 and 65535")
        if not isinstance(self.service_token, str) or len(self.service_token) < 32:
            raise IntegrationConfigurationError(
                "the local integration service token must contain at least 32 characters"
            )
        if not isinstance(self.data_dir, Path):
            raise IntegrationConfigurationError("data_dir must be a Path")
        if (
            isinstance(self.read_timeout_seconds, bool)
            or not isinstance(self.read_timeout_seconds, (int, float))
            or not math.isfinite(self.read_timeout_seconds)
            or self.read_timeout_seconds <= 0
        ):
            raise IntegrationConfigurationError(
                "read_timeout_seconds must be a finite number greater than zero"
            )

    @classmethod
    def from_environment(
        cls,
        *,
        data_dir: str | Path,
        port: int = DEFAULT_INTEGRATION_PORT,
    ) -> IntegrationServerConfig:
        token = os.environ.get(INTEGRATION_TOKEN_ENV, "")
        return cls(data_dir=Path(data_dir), service_token=token, port=port)
