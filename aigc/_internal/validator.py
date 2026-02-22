"""
Validators for mission-critical governance constraints.

This module ensures:
- Preconditions are satisfied
- Postconditions can be validated
- Output matches expected JSON schemas
"""

from __future__ import annotations

from typing import Any, Mapping

import jsonschema
from jsonschema import ValidationError
from aigc._internal.errors import (
    GovernanceViolationError,
    PreconditionError,
    SchemaValidationError,
)


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


def validate_preconditions(
    context: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[str]:
    """
    Validates that all policy preconditions are met.

    Preconditions might include:
    - role declared
    - schema exists
    - within budget limits
    """
    required = policy.get("pre_conditions", {}).get("required", [])
    satisfied: list[str] = []
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
