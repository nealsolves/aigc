"""
Core enforcement logic.

Combines:
- policy loading
- validation
- error handling
- audit logging triggers
"""

from typing import Dict
from src.policy_loader import load_policy
from src.validator import validate_preconditions, validate_schema
from src.audit import generate_audit_artifact


def enforce_invocation(invocation: Dict) -> Dict:
    """
    Enforce all governance rules for a model invocation.

    :param invocation: Dict with:
      - "policy_file": path to policy
      - "input": model input
      - "output": model output (to be validated)
      - "context": additional context
    :return: audit artifact
    """
    # Load policy
    policy = load_policy(invocation["policy_file"])

    # Validate preconditions
    validate_preconditions(invocation["context"], policy)

    # Validate output schema (if provided in policy)
    if "output_schema" in policy:
        validate_schema(invocation["output"], policy["output_schema"])

    # Generate audit artifact
    audit_record = generate_audit_artifact(invocation, policy)

    return audit_record
