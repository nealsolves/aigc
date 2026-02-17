"""
Policy loading and normalization.

- Loads YAML policy definitions
- Normalizes them into Python-native objects
- Validates structure against JSON schema
"""

from __future__ import annotations

import asyncio
import json
import logging
import yaml
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from src.errors import PolicyLoadError, PolicyValidationError

logger = logging.getLogger("aigc.policy_loader")

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_POLICY_SCHEMA_PATH = SCHEMAS_DIR / "invocation_policy.schema.json"
POLICY_DSL_SCHEMA_PATH = SCHEMAS_DIR / "policy_dsl.schema.json"
POLICY_SCHEMA_DRAFT_07 = "http://json-schema.org/draft-07/schema#"


def _resolve_policy_schema_path() -> Path:
    """
    Prefer the extended DSL schema when present.
    Fall back to the legacy schema.
    """
    if POLICY_DSL_SCHEMA_PATH.exists():
        return POLICY_DSL_SCHEMA_PATH
    if not LEGACY_POLICY_SCHEMA_PATH.exists():
        raise PolicyLoadError(
            "No policy schema file found",
            details={"searched": [str(POLICY_DSL_SCHEMA_PATH), str(LEGACY_POLICY_SCHEMA_PATH)]},
        )
    logger.warning("Using legacy policy schema: %s", LEGACY_POLICY_SCHEMA_PATH)
    return LEGACY_POLICY_SCHEMA_PATH


def _resolve_policy_path(policy_file: str) -> Path:
    candidate = Path(policy_file)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError:
        raise PolicyLoadError(
            "Policy path escapes repository root",
            details={"policy_file": policy_file},
        )
    if candidate.suffix not in {".yaml", ".yml"}:
        raise PolicyLoadError(
            "Policy file must be YAML",
            details={"policy_file": policy_file},
        )
    if not candidate.exists():
        raise PolicyLoadError(
            "Policy file does not exist",
            details={"policy_file": policy_file},
        )
    if not candidate.is_file():
        raise PolicyLoadError(
            "Policy path must reference a file",
            details={"policy_file": policy_file},
        )
    return candidate


def _path_to_pointer(path: list[Any]) -> str:
    if not path:
        return "$"
    return "$." + ".".join(str(part) for part in path)


def _merge_policies(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """
    Merge overlay policy into base policy.

    Merge rules:
    - Arrays: append overlay to base
    - Dicts: recursive merge
    - Scalars: overlay replaces base

    :param base: Base policy dict
    :param overlay: Overlay policy dict
    :return: New merged dict (base and overlay unchanged)
    """
    import copy

    merged = copy.deepcopy(base)

    for key, value in overlay.items():
        if key == "extends":
            # Don't copy extends to merged policy
            continue

        if key not in merged:
            merged[key] = copy.deepcopy(value)
        elif isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + copy.deepcopy(value)
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_policies(merged[key], value)
        else:
            # Scalar replacement
            merged[key] = copy.deepcopy(value)

    return merged


def _resolve_extends(
    policy: dict[str, Any],
    policy_path: Path,
    visited: set[Path] | None = None,
) -> dict[str, Any]:
    """
    Resolve policy inheritance via extends field.

    :param policy: Policy dict that may contain "extends"
    :param policy_path: Path to current policy file (for relative resolution)
    :param visited: Set of visited paths (for cycle detection)
    :return: Merged policy with inheritance applied
    :raises PolicyLoadError: On circular extends or missing base policy
    """
    if visited is None:
        visited = set()

    visited.add(policy_path)

    extends = policy.get("extends")
    if not extends:
        return policy

    # Resolve base policy path (relative to current policy)
    base_path = (policy_path.parent / extends).resolve()

    # Check cycle
    if base_path in visited:
        raise PolicyLoadError(
            f"Circular extends detected: {base_path}",
            details={
                "policy_path": str(policy_path),
                "extends": extends,
                "chain": sorted(str(p) for p in visited),
            },
        )

    # Load base policy (recursively, to handle chained extends)
    # Pass visited set to maintain cycle detection across the chain
    base_policy_dict = load_policy(str(base_path), visited)

    # Merge current policy into base (current overrides base)
    merged = _merge_policies(base_policy_dict, policy)

    # Remove extends field from merged policy
    merged.pop("extends", None)

    return merged


def load_policy(policy_file: str, visited: set[Path] | None = None) -> dict[str, Any]:
    """
    Load and validate a policy YAML file.

    :param policy_file: Path to YAML policy file
    :param visited: Set of visited policy paths (for cycle detection during extends resolution)
    :return: Python dict representing the policy
    """
    policy_path = _resolve_policy_path(policy_file)
    try:
        with open(policy_path, "r", encoding="utf-8") as file_obj:
            policy = yaml.safe_load(file_obj)
    except yaml.YAMLError as err:
        raise PolicyLoadError(
            "Policy YAML parsing failed",
            details={"policy_file": policy_file, "error": str(err)},
        ) from err

    if not isinstance(policy, dict):
        raise PolicyLoadError(
            "Policy root must be a mapping object",
            details={"policy_file": policy_file},
        )

    # Resolve inheritance BEFORE schema validation (Phase 2.6)
    if "extends" in policy:
        policy = _resolve_extends(policy, policy_path, visited)

    schema_path = _resolve_policy_schema_path()
    # Validate against JSON schema
    try:
        with open(schema_path, "r", encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
    except json.JSONDecodeError as err:
        raise PolicyLoadError(
            "Policy schema file is not valid JSON",
            details={"schema_path": str(schema_path), "error": str(err)},
        ) from err

    if schema.get("$schema") != POLICY_SCHEMA_DRAFT_07:
        raise PolicyLoadError(
            "Policy schema must declare JSON Schema Draft-07",
            details={"schema_path": str(schema_path), "found": schema.get("$schema")},
        )

    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema)
    errors = sorted(
        validator.iter_errors(policy),
        key=lambda err: _path_to_pointer(list(err.absolute_path)),
    )
    if errors:
        first = errors[0]
        pointer = _path_to_pointer(list(first.absolute_path))
        raise PolicyValidationError(
            f"Policy schema validation failed at {pointer}: {first.message}",
            details={
                "policy_file": policy_file,
                "schema_path": str(schema_path),
                "path": pointer,
                "validator": first.validator,
            },
        )

    logger.debug(
        "Policy loaded and validated: %s (version=%s)",
        policy_file,
        policy.get("policy_version"),
    )
    return policy


async def load_policy_async(
    policy_file: str, visited: set[Path] | None = None
) -> dict[str, Any]:
    """
    Async wrapper for load_policy.

    Runs load_policy in a thread pool to avoid blocking the event loop
    during file I/O and schema validation.

    :param policy_file: Path to YAML policy file
    :param visited: Set of visited policy paths (for cycle detection during extends resolution)
    :return: Python dict representing the policy
    """
    return await asyncio.to_thread(load_policy, policy_file, visited)
