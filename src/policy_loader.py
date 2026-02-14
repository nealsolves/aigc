"""
Policy loading and normalization.

- Loads YAML policy definitions
- Normalizes them into Python-native objects
- Validates structure against JSON schema
"""

import json
import yaml
import jsonschema
from pathlib import Path
from typing import Dict

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
LEGACY_POLICY_SCHEMA_PATH = SCHEMAS_DIR / "invocation_policy.schema.json"
POLICY_DSL_SCHEMA_PATH = SCHEMAS_DIR / "policy_dsl.schema.json"


def _resolve_policy_schema_path() -> Path:
    """
    Prefer the extended DSL schema when present.
    Fall back to the legacy schema.
    """
    if POLICY_DSL_SCHEMA_PATH.exists():
        return POLICY_DSL_SCHEMA_PATH
    return LEGACY_POLICY_SCHEMA_PATH


def load_policy(policy_file: str) -> Dict:
    """
    Load and validate a policy YAML file.

    :param policy_file: Path to YAML policy file
    :return: Python dict representing the policy
    """
    with open(policy_file, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)

    # Validate against JSON schema
    schema_path = _resolve_policy_schema_path()
    with open(schema_path, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    jsonschema.validate(policy, schema)
    return policy
