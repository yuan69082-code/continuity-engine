"""Compatibility imports for the shared contract hashing rules."""

from continuity_engine.domain.integration_hashing import (
    HASH_PATTERN,
    JsonSerializable,
    calculate_binding_fixture_hash,
    calculate_content_hash,
    calculate_projection_content_hash,
    calculate_request_hash,
    calculate_state_hash,
    canonicalize_json,
    sha256_hash,
    verify_declared_hash,
)


__all__ = [
    "HASH_PATTERN",
    "JsonSerializable",
    "calculate_binding_fixture_hash",
    "calculate_content_hash",
    "calculate_projection_content_hash",
    "calculate_request_hash",
    "calculate_state_hash",
    "canonicalize_json",
    "sha256_hash",
    "verify_declared_hash",
]
