from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

from continuity_engine.domain.errors import (
    MachineContractSchemaError,
    MachineContractValidationError,
)


REQUEST_SCHEMA_ID = (
    "urn:vio-live:continuity-integration:schema:request:first-round-v1"
)
OBSERVATION_SCHEMA_ID = (
    "urn:vio-live:continuity-integration:schema:platform-observation:"
    "message-created:first-round-v1"
)
FACT_SCHEMA_ID = (
    "urn:vio-live:continuity-integration:schema:platform-fact:"
    "message-version:first-round-v1"
)

SCHEMA_IDS = (
    REQUEST_SCHEMA_ID,
    OBSERVATION_SCHEMA_ID,
    FACT_SCHEMA_ID,
)

_SCHEMA_FILES = {
    REQUEST_SCHEMA_ID: "continuity-interaction-request.first-round-v1.schema.json",
    OBSERVATION_SCHEMA_ID: (
        "platform-observation.message-created.first-round-v1.schema.json"
    ),
    FACT_SCHEMA_ID: "platform-fact.message-version.first-round-v1.schema.json",
}

_UTC_DATE_TIME_PATTERN = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?Z$"
)


def _is_strict_utc_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if _UTC_DATE_TIME_PATTERN.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return False
    return True


_FORMAT_CHECKER = FormatChecker()
_FORMAT_CHECKER.checks("date-time")(_is_strict_utc_date_time)


def _reject_external_schema(uri: str) -> Resource[Any]:
    raise NoSuchResource(ref=uri)


def _format_path(error_path: object) -> str:
    parts = list(error_path)  # type: ignore[arg-type]
    if not parts:
        return "$"
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


class LocalSchemaRegistry:
    """Closed, package-local registry for the first-round machine contract."""

    def __init__(self) -> None:
        schema_root = files("continuity_engine.interfaces").joinpath("schemas")
        schemas: dict[str, dict[str, Any]] = {}

        for expected_id, filename in _SCHEMA_FILES.items():
            try:
                raw_schema = schema_root.joinpath(filename).read_text(encoding="utf-8")
                schema = json.loads(raw_schema)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise MachineContractSchemaError(
                    f"cannot load local schema {filename}"
                ) from exc

            if not isinstance(schema, dict) or schema.get("$id") != expected_id:
                raise MachineContractSchemaError(
                    f"local schema {filename} does not declare the required $id"
                )
            try:
                Draft202012Validator.check_schema(schema)
            except Exception as exc:
                raise MachineContractSchemaError(
                    f"local schema {expected_id} is not valid Draft 2020-12"
                ) from exc
            schemas[expected_id] = schema

        if tuple(schemas) != SCHEMA_IDS or len(schemas) != 3:
            raise MachineContractSchemaError(
                "first-round registry must contain exactly the three approved schemas"
            )

        self._schemas = schemas
        self._registry: Registry[Any] = Registry(
            retrieve=_reject_external_schema
        ).with_resources(
            (schema_id, Resource.from_contents(schema))
            for schema_id, schema in schemas.items()
        )

    @property
    def schema_ids(self) -> tuple[str, ...]:
        return tuple(self._schemas)

    def get_schema(self, schema_id: str) -> dict[str, Any]:
        try:
            return deepcopy(self._schemas[schema_id])
        except KeyError as exc:
            raise MachineContractSchemaError(
                f"schema identifier is not registered locally: {schema_id}"
            ) from exc

    def validate(self, schema_id: str, instance: Any) -> None:
        self._validate_schema(self.get_schema(schema_id), instance)

    def validate_inline(self, schema: Mapping[str, Any], instance: Any) -> None:
        """Validate with the closed registry; primarily useful for conformance tests."""

        self._validate_schema(dict(schema), instance)

    def _validate_schema(self, schema: dict[str, Any], instance: Any) -> None:
        try:
            validator = Draft202012Validator(
                schema,
                registry=self._registry,
                format_checker=_FORMAT_CHECKER,
            )
            errors = sorted(
                validator.iter_errors(instance),
                key=lambda item: (list(item.absolute_path), item.message),
            )
        except Unresolvable as exc:
            raise MachineContractSchemaError(
                f"schema reference cannot be resolved locally: {exc.ref}"
            ) from exc

        if errors:
            error = errors[0]
            raise MachineContractValidationError(
                f"schema validation failed at {_format_path(error.absolute_path)}: "
                f"{error.message}"
            )


DEFAULT_SCHEMA_REGISTRY = LocalSchemaRegistry()
