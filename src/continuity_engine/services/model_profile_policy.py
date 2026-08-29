from __future__ import annotations

from continuity_engine.domain.errors import (
    ModelProviderConflictError,
    ModelProviderNotFoundError,
    ModelProviderValidationError,
)
from continuity_engine.domain.model_provider import ProviderModelProfile


class ConfiguredModelProfilePolicy:
    """Immutable, explicit profile selection for one Engine process."""

    def __init__(
        self,
        profiles: tuple[ProviderModelProfile, ...],
        *,
        selected_profile_id: str,
    ) -> None:
        if not profiles:
            raise ModelProviderValidationError("at least one model profile is required")
        by_id: dict[str, ProviderModelProfile] = {}
        for profile in profiles:
            if not isinstance(profile, ProviderModelProfile):
                raise ModelProviderValidationError("profile registry is invalid")
            if profile.profile_id in by_id:
                raise ModelProviderConflictError("model profile ids must be unique")
            by_id[profile.profile_id] = profile
        self._profiles = by_id
        self._selected_profile_id = selected_profile_id

    def select(self) -> ProviderModelProfile:
        profile = self._profiles.get(self._selected_profile_id)
        if profile is None:
            raise ModelProviderNotFoundError("selected model profile is not configured")
        if not profile.enabled:
            raise ModelProviderValidationError("selected model profile is disabled")
        if profile.fallback_enabled:
            raise ModelProviderValidationError(
                "P02 fallback must remain explicitly disabled"
            )
        return profile
