"""
Generates structured audit artifacts for model invocations.

These artifacts must be stored/consumed by the system
to support:
- replay
- audit
- compliance analysis
"""

import time
import hashlib
from typing import Dict


def checksum(obj: Dict) -> str:
    """
    Generate checksum of a Python object.

    Used to ensure:
    - input checksum stability
    - output checksum stability

    :param obj: Dict representing input or output
    """
    # Convert canonical representation
    data = str(sorted(obj.items())).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generate_audit_artifact(invocation: Dict, policy: Dict) -> Dict:
    """
    Gather required audit fields and return structured object.

    :param invocation: original invocation data
    :param policy: loaded policy definitions
    :return: audit artifact
    """
    return {
        "model_provider": invocation["model_provider"],
        "model_identifier": invocation["model_identifier"],
        "role": invocation["role"],
        "policy_version": policy.get("policy_version"),
        "input_checksum": checksum(invocation["input"]),
        "output_checksum": checksum(invocation["output"]),
        "timestamp": int(time.time()),
    }
