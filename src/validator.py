"""
Validators for mission-critical governance constraints.

This module ensures:
- Preconditions are satisfied
- Postconditions can be validated
- Output matches expected JSON schemas
"""

from typing import Dict
import jsonschema
from jsonschema import ValidationError
from src.errors import PreconditionError, SchemaValidationError


def validate_schema(output: Dict, schema: Dict):
    """
    Validate output of model against JSON schema.

    :param output: LLM output parsed to dict
    :param schema: JSON schema to validate against
    :raises jsonschema.ValidationError on mismatch
    """
    try:
        jsonschema.validate(output, schema)
    except ValidationError as err:
        raise SchemaValidationError(str(err)) from err


def validate_preconditions(context: Dict, policy: Dict):
    """
    Validates that all policy preconditions are met.

    Preconditions might include:
    - role declared
    - schema exists
    - within budget limits
    """
    required = policy.get("pre_conditions", {}).get("required", [])
    for cond in required:
        if cond not in context or not bool(context[cond]):
            raise PreconditionError(
                f"Missing or false required precondition: {cond}"
            )
