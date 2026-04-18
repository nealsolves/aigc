"""
Policy loading and normalization.

- Loads YAML policy definitions
- Normalizes them into Python-native objects
- Validates structure against JSON schema
- Supports pluggable PolicyLoader interface
- Supports composition restriction semantics (intersect/union/replace)
- Supports policy version dates (effective_date/expiration_date)
"""

from __future__ import annotations

import abc
import asyncio
import copy
import json
import logging
import os
import threading
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft7Validator

from aigc._internal.errors import PolicyLoadError, PolicyValidationError

logger = logging.getLogger("aigc.policy_loader")

# Schema resolution: prefer package-internal schemas (works in wheel installs),
# fall back to repo-root schemas (works in editable/dev installs).
_PKG_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
_REPO_SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"
SCHEMAS_DIR = _PKG_SCHEMAS_DIR if _PKG_SCHEMAS_DIR.is_dir() else _REPO_SCHEMAS_DIR
LEGACY_POLICY_SCHEMA_PATH = SCHEMAS_DIR / "invocation_policy.schema.json"
POLICY_DSL_SCHEMA_PATH = SCHEMAS_DIR / "policy_dsl.schema.json"
POLICY_SCHEMA_DRAFT_07 = "http://json-schema.org/draft-07/schema#"

# Valid composition strategies
COMPOSITION_INTERSECT = "intersect"
COMPOSITION_UNION = "union"
COMPOSITION_REPLACE = "replace"
VALID_COMPOSITION_STRATEGIES = (
    COMPOSITION_INTERSECT,
    COMPOSITION_UNION,
    COMPOSITION_REPLACE,
)


# ── Pluggable PolicyLoader interface ─────────────────────────────


class PolicyLoaderBase(abc.ABC):
    """Abstract base class for policy loaders.

    Implement this interface to load policies from custom sources
    (databases, APIs, remote stores) instead of the default filesystem.

    Safety constraints:
    - Loaders must return valid policy dicts
    - Loaders must not bypass schema validation
    - Loaders must handle errors by raising PolicyLoadError

    Usage::

        class DatabasePolicyLoader(PolicyLoaderBase):
            def load(self, policy_ref):
                row = db.query("SELECT yaml FROM policies WHERE id = ?", policy_ref)
                return yaml.safe_load(row["yaml"])

        aigc = AIGC(policy_loader=DatabasePolicyLoader())
    """

    @abc.abstractmethod
    def load(self, policy_ref: str) -> dict[str, Any]:
        """Load a raw policy dict from the source.

        :param policy_ref: Policy reference (file path, ID, URL, etc.)
        :return: Parsed policy dict (before schema validation)
        :raises PolicyLoadError: On load failure
        """


class FilePolicyLoader(PolicyLoaderBase):
    """Default filesystem-based policy loader."""

    def load(self, policy_ref: str) -> dict[str, Any]:
        """Load policy from a YAML file on disk."""
        policy_path = _resolve_policy_path(policy_ref)
        try:
            with open(policy_path, "r", encoding="utf-8") as file_obj:
                policy = yaml.safe_load(file_obj)
        except yaml.YAMLError as err:
            raise PolicyLoadError(
                "Policy YAML parsing failed",
                details={"policy_file": policy_ref, "error": str(err)},
            ) from err

        if not isinstance(policy, dict):
            raise PolicyLoadError(
                "Policy root must be a mapping object",
                details={"policy_file": policy_ref},
            )
        return policy


# Default loader singleton
_default_loader = FilePolicyLoader()


# ── Path resolution ──────────────────────────────────────────────


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
            details={
                "searched": [
                    str(POLICY_DSL_SCHEMA_PATH),
                    str(LEGACY_POLICY_SCHEMA_PATH),
                ]
            },
        )
    logger.warning("Using legacy policy schema: %s", LEGACY_POLICY_SCHEMA_PATH)
    return LEGACY_POLICY_SCHEMA_PATH


def _resolve_policy_path(policy_file: str) -> Path:
    candidate = Path(policy_file)
    if not candidate.is_absolute():
        # Relative paths are resolved against the caller's working directory
        # so that pip-installed users can pass paths like "policies/my_policy.yaml"
        # relative to their project root.  See ADR-0005.
        candidate = (Path.cwd() / candidate).resolve()
    else:
        # Absolute paths are accepted as-is.  The caller is responsible for
        # ensuring the path is intentional (e.g. a consumer project's own
        # policy directory).  See ADR-0005.
        candidate = candidate.resolve()

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


# ── Composition restriction semantics ────────────────────────────


def _merge_arrays_intersect(base: list, overlay: list) -> list:
    """Intersect: keep only items present in both arrays."""
    return [item for item in base if item in overlay]


def _merge_arrays_union(base: list, overlay: list) -> list:
    """Union: combine both arrays, deduplicating."""
    seen = set()
    result = []
    for item in base + overlay:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_policies(
    base: dict[str, Any],
    overlay: dict[str, Any],
    composition_strategy: str | None = None,
) -> dict[str, Any]:
    """
    Merge overlay policy into base policy.

    Merge rules depend on composition_strategy:
    - None/default: arrays append, dicts recursive merge, scalars replace
    - "intersect": arrays intersect, dicts recursive merge, scalars overlay
    - "union": arrays union (deduplicated), dicts recursive merge, scalars overlay
    - "replace": overlay completely replaces base for all keys present

    :param base: Base policy dict
    :param overlay: Overlay policy dict
    :param composition_strategy: Optional strategy override
    :return: New merged dict (base and overlay unchanged)
    """
    if composition_strategy == COMPOSITION_REPLACE:
        merged = copy.deepcopy(base)
        for key, value in overlay.items():
            if key in ("extends", "composition_strategy"):
                continue
            merged[key] = copy.deepcopy(value)
        return merged

    merged = copy.deepcopy(base)

    for key, value in overlay.items():
        if key in ("extends", "composition_strategy"):
            continue

        if key not in merged:
            merged[key] = copy.deepcopy(value)
        elif isinstance(merged[key], list) and isinstance(value, list):
            if composition_strategy == COMPOSITION_INTERSECT:
                merged[key] = _merge_arrays_intersect(merged[key], value)
            elif composition_strategy == COMPOSITION_UNION:
                merged[key] = _merge_arrays_union(merged[key], value)
            else:
                # Default: append
                merged[key] = merged[key] + copy.deepcopy(value)
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_policies(
                merged[key], value, composition_strategy
            )
        else:
            # Scalar replacement
            merged[key] = copy.deepcopy(value)

    return merged


def _validate_composition_restriction(
    base: dict[str, Any],
    merged: dict[str, Any],
) -> None:
    """Enforce monotonic restriction: child policies may not expand roles or
    remove required postconditions relative to the base policy.

    :param base: The resolved base policy dict (before overlay was applied).
    :param merged: The merged policy dict (after overlay was applied).
    :raises PolicyValidationError: If the merged policy escalates privileges or
        weakens postconditions.
    """
    # Role escalation check: merged roles must be a subset of base roles
    base_roles = set(base.get("roles") or [])
    merged_roles = set(merged.get("roles") or [])
    if base_roles and (escalated := sorted(merged_roles - base_roles)):
        raise PolicyValidationError(
            f"Composition escalation: child policy adds roles not present "
            f"in base policy: {escalated}",
            details={
                "base_roles": sorted(base_roles),
                "merged_roles": sorted(merged_roles),
                "escalated_roles": escalated,
            },
        )

    # Postcondition weakening check: merged must retain all base required postconditions
    base_post = set(
        base.get("post_conditions", {}).get("required") or []
    )
    merged_post = set(
        merged.get("post_conditions", {}).get("required") or []
    )
    if base_post and (removed := sorted(base_post - merged_post)):
        raise PolicyValidationError(
            f"Composition weakening: child policy removes required "
            f"postconditions from base policy: {removed}",
            details={
                "base_required": sorted(base_post),
                "merged_required": sorted(merged_post),
                "removed_postconditions": removed,
            },
        )

    # Workflow budget escalation checks: child must not widen base budgets
    base_wf = base.get("workflow") or {}
    merged_wf = merged.get("workflow") or {}

    base_max_steps = base_wf.get("max_steps")
    merged_max_steps = merged_wf.get("max_steps")
    if (
        base_max_steps is not None
        and merged_max_steps is not None
        and merged_max_steps > base_max_steps
    ):
        raise PolicyValidationError(
            f"Composition escalation: child policy widens max_steps "
            f"from {base_max_steps} to {merged_max_steps}",
            details={
                "base_max_steps": base_max_steps,
                "merged_max_steps": merged_max_steps,
            },
        )

    base_max_calls = base_wf.get("max_total_tool_calls")
    merged_max_calls = merged_wf.get("max_total_tool_calls")
    if (
        base_max_calls is not None
        and merged_max_calls is not None
        and merged_max_calls > base_max_calls
    ):
        raise PolicyValidationError(
            f"Composition escalation: child policy widens max_total_tool_calls "
            f"from {base_max_calls} to {merged_max_calls}",
            details={
                "base_max_total_tool_calls": base_max_calls,
                "merged_max_total_tool_calls": merged_max_calls,
            },
        )

    # Participant narrowing check: merged participants (by id) must be ⊆ base participants
    base_participants = {p["id"] for p in (base_wf.get("participants") or [])}
    merged_participants = {p["id"] for p in (merged_wf.get("participants") or [])}
    if base_participants and (added := sorted(merged_participants - base_participants)):
        raise PolicyValidationError(
            f"Composition escalation: child policy adds participants not in base: {added}",
            details={
                "base_participant_ids": sorted(base_participants),
                "merged_participant_ids": sorted(merged_participants),
                "added_participant_ids": added,
            },
        )


# ── Policy version dates ─────────────────────────────────────────


def _parse_date(value: Any) -> date | None:
    """Parse a date value from policy. Accepts YYYY-MM-DD strings or date objects."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise PolicyValidationError(
                f"Invalid date format: {value!r}; expected YYYY-MM-DD",
                details={"value": value},
            )
    raise PolicyValidationError(
        f"Invalid date type: {type(value).__name__}; expected string or date",
        details={"value": str(value)},
    )


def validate_policy_dates(
    policy: dict[str, Any],
    *,
    clock: Callable[[], date] | None = None,
) -> dict[str, Any]:
    """Validate policy effective_date and expiration_date.

    :param policy: Policy dict with optional date fields
    :param clock: Injectable clock function for testing (default: date.today)
    :return: Dict with date validation evidence
    :raises PolicyValidationError: If policy is not currently active
    """
    effective_date = _parse_date(policy.get("effective_date"))
    expiration_date = _parse_date(policy.get("expiration_date"))

    if effective_date is None and expiration_date is None:
        return {"policy_dates": "none_specified", "active": True}

    # Check logical consistency first (before time-dependent checks)
    if effective_date and expiration_date and effective_date > expiration_date:
        raise PolicyValidationError(
            "Policy effective_date is after expiration_date",
            details={
                "effective_date": effective_date.isoformat(),
                "expiration_date": expiration_date.isoformat(),
            },
        )

    today = (clock or date.today)()

    evidence: dict[str, Any] = {
        "evaluation_date": today.isoformat(),
        "active": True,
    }

    if effective_date is not None:
        evidence["effective_date"] = effective_date.isoformat()
        if today < effective_date:
            evidence["active"] = False
            raise PolicyValidationError(
                f"Policy not yet active: effective_date is "
                f"{effective_date.isoformat()}, today is {today.isoformat()}",
                details={
                    "effective_date": effective_date.isoformat(),
                    "today": today.isoformat(),
                },
            )

    if expiration_date is not None:
        evidence["expiration_date"] = expiration_date.isoformat()
        if today > expiration_date:
            evidence["active"] = False
            raise PolicyValidationError(
                f"Policy expired: expiration_date is "
                f"{expiration_date.isoformat()}, today is {today.isoformat()}",
                details={
                    "expiration_date": expiration_date.isoformat(),
                    "today": today.isoformat(),
                },
            )

    return evidence


# ── Extends resolution ───────────────────────────────────────────


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

    # Get composition strategy from overlay policy
    strategy = policy.get("composition_strategy")
    if strategy is not None and strategy not in VALID_COMPOSITION_STRATEGIES:
        raise PolicyValidationError(
            f"Invalid composition_strategy: {strategy!r}; "
            f"expected one of {VALID_COMPOSITION_STRATEGIES}",
            details={"composition_strategy": strategy},
        )

    # Merge current policy into base (current overrides base)
    merged = _merge_policies(base_policy_dict, policy, strategy)

    # Enforce monotonic restriction: child must not escalate privileges
    _validate_composition_restriction(base_policy_dict, merged)

    # Remove extends and composition_strategy from merged policy
    merged.pop("extends", None)
    merged.pop("composition_strategy", None)

    return merged


# ── Core load_policy ─────────────────────────────────────────────


def load_policy(
    policy_file: str,
    visited: set[Path] | None = None,
    *,
    loader: PolicyLoaderBase | None = None,
    clock: Callable[[], date] | None = None,
) -> dict[str, Any]:
    """
    Load and validate a policy YAML file.

    :param policy_file: Path to YAML policy file
    :param visited: Set of visited policy paths (for cycle detection)
    :param loader: Optional custom policy loader
    :param clock: Optional clock function for date validation
    :return: Python dict representing the policy
    """
    effective_loader = loader or _default_loader

    if isinstance(effective_loader, FilePolicyLoader):
        # File-based loader: resolve path first
        policy_path = _resolve_policy_path(policy_file)
        policy = effective_loader.load(str(policy_path))
    else:
        # Custom loader: let the loader handle resolution
        try:
            policy = effective_loader.load(policy_file)
        except PolicyLoadError:
            raise
        except Exception as exc:
            raise PolicyLoadError(
                f"Custom policy loader failed: {exc}",
                details={
                    "policy_file": policy_file,
                    "loader": type(effective_loader).__name__,
                },
            ) from exc

        if not isinstance(policy, dict):
            raise PolicyLoadError(
                "Policy root must be a mapping object",
                details={"policy_file": policy_file},
            )
        policy_path = Path(policy_file).resolve()

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
            details={
                "schema_path": str(schema_path),
                "found": schema.get("$schema"),
            },
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

    # Validate policy version dates if present
    if (
        policy.get("effective_date") is not None
        or policy.get("expiration_date") is not None
    ):
        validate_policy_dates(policy, clock=clock)

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
    :param visited: Set of visited policy paths (for cycle detection)
    :return: Python dict representing the policy
    """
    return await asyncio.to_thread(load_policy, policy_file, visited)


class PolicyCache:
    """LRU cache for loaded policies, keyed by (canonical_path, file_mtime).

    Thread-safe via threading.Lock. Cache lives on an AIGC instance to
    eliminate global mutable state.

    Usage::

        cache = PolicyCache(max_size=128)
        policy = cache.get_or_load("policies/my_policy.yaml")
    """

    def __init__(self, max_size: int = 128) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._cache: dict[tuple[str, float], dict[str, Any]] = {}
        self._access_order: list[tuple[str, float]] = []
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_or_load(
        self,
        policy_file: str,
        visited: set[Path] | None = None,
        *,
        loader: PolicyLoaderBase | None = None,
    ) -> dict[str, Any]:
        """Load policy from cache or the supplied loader.

        :param policy_file: Path or reference to policy
        :param visited: For cycle detection during extends resolution
        :param loader: Optional custom policy loader (bypasses filesystem)
        :return: Loaded policy dict
        """
        if loader is not None and not isinstance(loader, FilePolicyLoader):
            # Custom loaders: use policy_file as opaque key (no filesystem
            # resolution).  Mtime is not meaningful for non-file sources so
            # we use a sentinel; callers who need cache-busting should call
            # cache.clear().
            key = (policy_file, 0.0)

            with self._lock:
                if key in self._cache:
                    logger.debug("Policy cache hit (custom loader): %s",
                                 policy_file)
                    if key in self._access_order:
                        self._access_order.remove(key)
                    self._access_order.append(key)
                    return self._cache[key]

            policy = load_policy(policy_file, visited, loader=loader)

            with self._lock:
                if len(self._cache) >= self._max_size:
                    self._evict_oldest()
                self._cache[key] = policy
                self._access_order.append(key)
            return policy

        # Default filesystem path
        canonical = str(_resolve_policy_path(policy_file))
        mtime = os.path.getmtime(canonical)
        key = (canonical, mtime)

        with self._lock:
            if key in self._cache:
                logger.debug("Policy cache hit: %s", policy_file)
                # Move to end for LRU
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]

        # Load outside lock to avoid blocking other threads
        policy = load_policy(policy_file, visited, loader=loader)

        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            self._cache[key] = policy
            self._access_order.append(key)
            logger.debug(
                "Policy cached: %s (cache size: %d)",
                policy_file,
                len(self._cache),
            )

        return policy

    def _evict_oldest(self) -> None:
        """Evict the least recently used cache entry. Must hold lock."""
        if self._access_order:
            oldest = self._access_order.pop(0)
            self._cache.pop(oldest, None)

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
