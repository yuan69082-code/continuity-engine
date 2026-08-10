from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

from continuity_engine.domain.errors import (
    CapabilityValidationError,
    MachineContractSchemaError,
)


CAPABILITY_REQUEST_SCHEMA_ID = "urn:continuity-engine:capability:schema:request:v1"
CAPABILITY_RESULT_SCHEMA_ID = "urn:continuity-engine:capability:schema:result:v1"
CAPABILITY_MODEL_OUTPUT_SCHEMA_ID = (
    "urn:continuity-engine:capability:schema:model-output:v1"
)
CAPABILITY_SCHEMA_IDS = (
    CAPABILITY_REQUEST_SCHEMA_ID,
    CAPABILITY_RESULT_SCHEMA_ID,
    CAPABILITY_MODEL_OUTPUT_SCHEMA_ID,
)

_SCHEMA_FILES = {
    CAPABILITY_REQUEST_SCHEMA_ID: "capability-request.v1.schema.json",
    CAPABILITY_RESULT_SCHEMA_ID: "capability-result.v1.schema.json",
    CAPABILITY_MODEL_OUTPUT_SCHEMA_ID: "capability-model-output.v1.schema.json",
}
_UTC = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?Z$"
)


def _strict_utc(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if _UTC.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


_FORMAT_CHECKER = FormatChecker()
_FORMAT_CHECKER.checks("date-time")(_strict_utc)


def _reject_external(uri: str) -> Resource[Any]:
    raise NoSuchResource(ref=uri)


class CapabilitySchemaRegistry:
    """Closed package-local registry for the E5 capability protocol."""

    def __init__(self) -> None:
        root = files("continuity_engine.interfaces").joinpath("schemas")
        schemas: dict[str, dict[str, Any]] = {}
        for schema_id, filename in _SCHEMA_FILES.items():
            try:
                schema = json.loads(root.joinpath(filename).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise MachineContractSchemaError(
                    f"cannot load local capability schema {filename}"
                ) from exc
            if not isinstance(schema, dict) or schema.get("$id") != schema_id:
                raise MachineContractSchemaError(
                    f"capability schema {filename} has the wrong $id"
                )
            try:
                Draft202012Validator.check_schema(schema)
            except Exception as exc:
                raise MachineContractSchemaError(
                    f"capability schema {schema_id} is not Draft 2020-12"
                ) from exc
            schemas[schema_id] = schema
        self._schemas = schemas
        self._registry: Registry[Any] = Registry(retrieve=_reject_external).with_resources(
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
                f"capability schema is not registered: {schema_id}"
            ) from exc

    def validate(self, schema_id: str, instance: Any) -> None:
        try:
            validator = Draft202012Validator(
                self.get_schema(schema_id),
                registry=self._registry,
                format_checker=_FORMAT_CHECKER,
            )
            errors = sorted(
                validator.iter_errors(instance),
                key=lambda item: (list(item.absolute_path), item.message),
            )
        except Unresolvable as exc:
            raise MachineContractSchemaError(
                f"capability schema reference cannot be resolved locally: {exc.ref}"
            ) from exc
        if errors:
            error = errors[0]
            path = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            raise CapabilityValidationError(
                f"capability schema validation failed at {path}: {error.message}"
            )


DEFAULT_CAPABILITY_SCHEMA_REGISTRY = CapabilitySchemaRegistry()
