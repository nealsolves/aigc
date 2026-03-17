"""
Validators for mission-critical governance constraints.

This module ensures:
- Preconditions are satisfied
- Postconditions can be validated
- Output matches expected JSON schemas
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Mapping

import jsonschema
from jsonschema import ValidationError
from aigc._internal.errors import (
    GovernanceViolationError,
    PreconditionError,
    SchemaValidationError,
)

logger = logging.getLogger("aigc.validator")


def _path_to_pointer(path: list[Any]) -> str:
    if not path:
        return "$"
    return "$." + ".".join(str(part) for part in path)


def validate_role(role: str, policy: Mapping[str, Any]) -> None:
    allowed_roles = policy.get("roles", [])
    if role not in allowed_roles:
        raise GovernanceViolationError(
            f"Unauthorized role '{role}'",
            code="ROLE_NOT_ALLOWED",
            details={"role": role, "allowed_roles": allowed_roles},
        )


def validate_schema(output: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """
    Validate output of model against JSON schema.

    :param output: LLM output parsed to dict
    :param schema: JSON schema to validate against
    :raises jsonschema.ValidationError on mismatch
    """
    try:
        jsonschema.validate(output, schema)
    except ValidationError as err:
        pointer = _path_to_pointer(list(err.absolute_path))
        raise SchemaValidationError(
            f"Output schema validation failed at {pointer}: {err.message}",
            details={"path": pointer, "validator": err.validator},
        ) from err


def _validate_typed_precondition(
    key: str,
    spec: Mapping[str, Any],
    context: Mapping[str, Any],
) -> None:
    """Validate a single typed precondition against context value."""
    if key not in context:
        raise PreconditionError(
            f"Missing required precondition: {key}",
            details={"precondition": key},
        )

    value = context[key]

    # Build a mini JSON Schema for validation
    schema: dict[str, Any] = {}
    if "type" in spec and spec["type"] != "any":
        schema["type"] = spec["type"]
    if "pattern" in spec:
        schema["pattern"] = spec["pattern"]
    if "enum" in spec:
        schema["enum"] = spec["enum"]
    if "minLength" in spec:
        schema["minLength"] = spec["minLength"]
    if "maxLength" in spec:
        schema["maxLength"] = spec["maxLength"]
    if "minimum" in spec:
        schema["minimum"] = spec["minimum"]
    if "maximum" in spec:
        schema["maximum"] = spec["maximum"]

    if not schema:
        # Type "any" or no constraints - just check existence
        if not bool(value):
            raise PreconditionError(
                f"Missing or false required precondition: {key}",
                details={"precondition": key},
            )
        return

    try:
        jsonschema.validate(value, schema)
    except ValidationError as err:
        raise PreconditionError(
            f"Precondition '{key}' validation failed: {err.message}",
            details={"precondition": key, "value": value, "constraint": schema},
        ) from err


def validate_preconditions(
    context: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[str]:
    """
    Validates that all policy preconditions are met.

    Supports two formats:
    - Legacy bare-string: required: ["key1", "key2"] (deprecated)
    - Typed: required: {"key1": {"type": "string", "pattern": "..."}} (preferred)
    """
    required = policy.get("pre_conditions", {}).get("required", [])

    if isinstance(required, dict):
        # Typed preconditions
        satisfied: list[str] = []
        for key in sorted(required.keys()):
            spec = required[key]
            _validate_typed_precondition(key, spec, context)
            satisfied.append(key)
        return satisfied

    # Legacy bare-string format
    if isinstance(required, list) and required and isinstance(required[0], str):
        if any(isinstance(r, str) for r in required):
            warnings.warn(
                "Bare-string preconditions are deprecated. "
                "Use typed format: required: {key: {type: string}}",
                DeprecationWarning,
                stacklevel=3,
            )

    satisfied = []
    for cond in required:
        if cond not in context or not bool(context[cond]):
            raise PreconditionError(
                f"Missing or false required precondition: {cond}",
                details={"precondition": cond},
            )
        satisfied.append(cond)
    return satisfied


def validate_postconditions(
    policy: Mapping[str, Any],
    *,
    schema_valid: bool,
) -> list[str]:
    required = policy.get("post_conditions", {}).get("required", [])
    satisfied: list[str] = []
    for cond in required:
        if cond == "output_schema_valid" and schema_valid:
            satisfied.append(cond)
            continue
        if cond == "output_schema_valid" and not schema_valid:
            raise GovernanceViolationError(
                "Postcondition 'output_schema_valid' requires output_schema validation",
                code="POSTCONDITION_FAILED",
                details={"postcondition": cond},
            )
        raise GovernanceViolationError(
            f"Unsupported postcondition: {cond}",
            code="UNSUPPORTED_POSTCONDITION",
            details={"postcondition": cond},
        )
    return satisfied
