from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from typing import Any, Protocol

import rfc8785

from continuity_engine.domain.errors import MachineContractValidationError


HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class JsonSerializable(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "to_dict"):
        return _json_value(value.to_dict())
    return value


def canonicalize_json(value: Any) -> bytes:
    """Return RFC 8785 canonical JSON as UTF-8 bytes."""

    try:
        return rfc8785.dumps(_json_value(value))
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as exc:
        raise MachineContractValidationError(
            "value cannot be canonicalized as RFC 8785 JSON"
        ) from exc


def sha256_hash(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def calculate_content_hash(content: str) -> str:
    if not isinstance(content, str):
        raise MachineContractValidationError("content must be a string")
    return sha256_hash(content.encode("utf-8"))


def calculate_request_hash(request: Mapping[str, Any] | JsonSerializable) -> str:
    value = _json_value(request)
    if not isinstance(value, dict):
        raise MachineContractValidationError("request hash input must be an object")
    logical_request = dict(value)
    logical_request.pop("requestHash", None)
    return sha256_hash(canonicalize_json(logical_request))


def _without_hash_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_hash_fields(item)
            for key, item in value.items()
            if not key.casefold().endswith("hash")
        }
    if isinstance(value, (list, tuple)):
        return [_without_hash_fields(item) for item in value]
    return value


def calculate_binding_fixture_hash(
    fixture: Mapping[str, Any] | JsonSerializable,
) -> str:
    value = _json_value(fixture)
    if not isinstance(value, dict):
        raise MachineContractValidationError(
            "SubjectBinding fixture hash input must be an object"
        )
    return sha256_hash(canonicalize_json(_without_hash_fields(value)))


def verify_declared_hash(*, declared: str, calculated: str, field_name: str) -> None:
    if not isinstance(declared, str) or HASH_PATTERN.fullmatch(declared) is None:
        raise MachineContractValidationError(
            f"{field_name} must use sha256: followed by 64 lowercase hexadecimal digits"
        )
    if not hmac.compare_digest(declared, calculated):
        raise MachineContractValidationError(f"{field_name} does not match its content")
