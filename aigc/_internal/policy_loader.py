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
    overlay: dict[str, Any] | None = None,
) -> None:
    """Enforce monotonic restriction: child policies may not expand roles or
    remove required postconditions relative to the base policy.

    :param base: The resolved base policy dict (before overlay was applied).
    :param merged: The merged policy dict (after overlay was applied).
    :param overlay: The raw child (overlay) policy dict before merging.
        Used for workflow field checks where array intersection can hide what
        the child is attempting to add.
    :raises PolicyValidationError: If the merged policy escalates privileges or
        weakens postconditions.
    """
    # Use overlay when available for workflow field comparisons so that
    # intersect/union merge strategies cannot hide widening attempts.
    child_wf_source = (overlay or {}).get("workflow") or {} if overlay is not None else None
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
    if base_max_steps is not None:
        if merged_max_steps is None or merged_max_steps > base_max_steps:
            raise PolicyValidationError(
                f"Composition escalation: child policy widens max_steps "
                f"(base={base_max_steps}, merged={merged_max_steps})",
                details={
                    "base_max_steps": base_max_steps,
                    "merged_max_steps": merged_max_steps,
                },
            )

    base_max_calls = base_wf.get("max_total_tool_calls")
    merged_max_calls = merged_wf.get("max_total_tool_calls")
    if base_max_calls is not None:
        if merged_max_calls is None or merged_max_calls > base_max_calls:
            raise PolicyValidationError(
                f"Composition escalation: child policy widens max_total_tool_calls "
                f"(base={base_max_calls}, merged={merged_max_calls})",
                details={
                    "base_max_total_tool_calls": base_max_calls,
                    "merged_max_total_tool_calls": merged_max_calls,
                },
            )

    # For workflow DSL field checks, prefer the raw child overlay (before merge)
    # so that array intersection/union strategies cannot hide widening attempts.
    # When overlay is None (legacy call sites), fall back to merged_wf.
    child_wf = child_wf_source if child_wf_source is not None else merged_wf

    # Participant narrowing check: child participants (by id) must be ⊆ base participants
    base_participants = {p["id"] for p in (base_wf.get("participants") or [])}
    child_participants = {p["id"] for p in (child_wf.get("participants") or [])}
    merged_participants = {p["id"] for p in (merged_wf.get("participants") or [])}
    if base_participants and not merged_participants:
        # Removal-to-empty: cleared participants disable enforcement entirely
        raise PolicyValidationError(
            "Composition escalation: child policy clears all participants declared in base, "
            "disabling participant enforcement",
            details={"base_participant_ids": sorted(base_participants)},
        )
    if base_participants and (added := sorted(child_participants - base_participants)):
        raise PolicyValidationError(
            f"Composition escalation: child policy adds participants not in base: {added}",
            details={
                "base_participant_ids": sorted(base_participants),
                "merged_participant_ids": sorted(child_participants),
                "added_participant_ids": added,
            },
        )

    # Per-participant roles/protocols narrowing
    base_participants_map = {p["id"]: p for p in (base_wf.get("participants") or [])}
    child_participants_map = {p["id"]: p for p in (child_wf.get("participants") or [])}
    for pid, child_p in child_participants_map.items():
        base_p = base_participants_map.get(pid, {})
        base_p_roles = set(base_p.get("roles") or [])
        child_p_roles = set(child_p.get("roles") or [])
        if base_p_roles and (widened := sorted(child_p_roles - base_p_roles)):
            raise PolicyValidationError(
                f"Composition escalation: child widens roles for participant {pid!r}: {widened}",
                details={"participant_id": pid, "widened_roles": widened},
            )
        base_p_protocols = set(base_p.get("protocols") or [])
        child_p_protocols = set(child_p.get("protocols") or [])
        if base_p_protocols and (widened := sorted(child_p_protocols - base_p_protocols)):
            raise PolicyValidationError(
                f"Composition escalation: child widens protocols for participant "
                f"{pid!r}: {widened}",
                details={"participant_id": pid, "widened_protocols": widened},
            )
        base_manifest = base_p.get("manifest_ref")
        child_manifest = child_p.get("manifest_ref")
        if base_manifest is not None and child_manifest != base_manifest:
            raise PolicyValidationError(
                f"Composition escalation: child changes manifest_ref for participant {pid!r}",
                details={
                    "participant_id": pid,
                    "base_manifest_ref": base_manifest,
                    "merged_manifest_ref": child_manifest,
                },
            )

    # required_sequence must only narrow (check child overlay vs base)
    base_seq = base_wf.get("required_sequence") or []
    child_seq = child_wf.get("required_sequence") or []
    merged_seq = merged_wf.get("required_sequence") or []
    base_seq_set = set(base_seq)
    child_seq_set = set(child_seq)
    if base_seq and not merged_seq:
        raise PolicyValidationError(
            "Composition escalation: child policy clears required_sequence declared in base, "
            "disabling sequence enforcement",
            details={"base_required_sequence": list(base_seq)},
        )
    if base_seq and (added := sorted(child_seq_set - base_seq_set)):
        raise PolicyValidationError(
            f"Composition escalation: child adds required_sequence steps not in base: {added}",
            details={"base_required_sequence": base_seq, "added_steps": added},
        )
    if base_seq and child_seq:
        base_iter = iter(base_seq)
        if not all(
            any(base_step == child_step for base_step in base_iter)
            for child_step in child_seq
        ):
            raise PolicyValidationError(
                "Composition escalation: child reorders required_sequence relative "
                "to the base policy",
                details={
                    "base_required_sequence": base_seq,
                    "child_required_sequence": child_seq,
                },
            )

    # allowed_transitions must only narrow (check child overlay vs base)
    base_trans = base_wf.get("allowed_transitions") or {}
    child_trans = child_wf.get("allowed_transitions") or {}
    merged_trans = merged_wf.get("allowed_transitions") or {}
    if base_trans and not merged_trans:
        raise PolicyValidationError(
            "Composition escalation: child policy clears allowed_transitions declared in base, "
            "disabling transition enforcement",
            details={"base_allowed_transitions": dict(base_trans)},
        )
    if base_trans:
        new_from_keys = sorted(set(child_trans) - set(base_trans))
        if new_from_keys:
            raise PolicyValidationError(
                f"Composition escalation: child adds new 'from' step keys in "
                f"allowed_transitions: {new_from_keys}",
                details={"new_from_step_keys": new_from_keys},
            )
        for from_step, child_to_steps in child_trans.items():
            base_to_steps = set(base_trans.get(from_step, []))
            child_to_steps_set = set(child_to_steps)
            if widened := sorted(child_to_steps_set - base_to_steps):
                raise PolicyValidationError(
                    f"Composition escalation: child widens allowed_transitions "
                    f"for {from_step!r}: {widened}",
                    details={"from_step": from_step, "widened_transitions": widened},
                )

    # allowed_agent_roles must only narrow (check child overlay vs base)
    base_agent_roles = set(base_wf.get("allowed_agent_roles") or [])
    child_agent_roles = set(child_wf.get("allowed_agent_roles") or [])
    merged_agent_roles = set(merged_wf.get("allowed_agent_roles") or [])
    if base_agent_roles and not merged_agent_roles:
        raise PolicyValidationError(
            "Composition escalation: child policy clears allowed_agent_roles declared in base, "
            "disabling agent role enforcement",
            details={"base_allowed_agent_roles": sorted(base_agent_roles)},
        )
    if base_agent_roles and (widened := sorted(child_agent_roles - base_agent_roles)):
        raise PolicyValidationError(
            f"Composition escalation: child widens allowed_agent_roles: {widened}",
            details={
                "base_allowed_agent_roles": sorted(base_agent_roles),
                "widened_roles": widened,
            },
        )

    # handoffs must only narrow (check child overlay vs base)
    base_handoffs = {(h["from"], h["to"]) for h in (base_wf.get("handoffs") or [])}
    child_handoffs = {(h["from"], h["to"]) for h in (child_wf.get("handoffs") or [])}
    merged_handoffs = {(h["from"], h["to"]) for h in (merged_wf.get("handoffs") or [])}
    if base_handoffs and not merged_handoffs:
        raise PolicyValidationError(
            "Composition escalation: child policy clears all handoffs declared in base, "
            "disabling handoff enforcement",
            details={"base_handoffs": [{"from": f, "to": t} for f, t in sorted(base_handoffs)]},
        )
    if base_handoffs and (added := sorted(child_handoffs - base_handoffs)):
        raise PolicyValidationError(
            f"Composition escalation: child adds handoff pairs not in base: {added}",
            details={"added_handoffs": [{"from": f, "to": t} for f, t in added]},
        )

    # escalation.require_approval_after_steps can only tighten (lower or match)
    # Use merged_wf here: the merged value correctly reflects the final resolved threshold.
    base_esc = base_wf.get("escalation") or {}
    merged_esc = merged_wf.get("escalation") or {}
    base_esc_n = base_esc.get("require_approval_after_steps")
    merged_esc_n = merged_esc.get("require_approval_after_steps")
    if base_esc_n is not None:
        if merged_esc_n is None or merged_esc_n > base_esc_n:
            raise PolicyValidationError(
                f"Composition escalation: child raises escalation threshold "
                f"(base={base_esc_n}, merged={merged_esc_n})",
                details={
                    "base_require_approval_after_steps": base_esc_n,
                    "merged_require_approval_after_steps": merged_esc_n,
                },
            )

    # escalation.require_approval_for_roles can only narrow (child cannot remove roles)
    base_esc_roles = set(base_esc.get("require_approval_for_roles") or [])
    merged_esc_roles = set(merged_esc.get("require_approval_for_roles") or [])
    if base_esc_roles and (removed_roles := sorted(base_esc_roles - merged_esc_roles)):
        raise PolicyValidationError(
            f"Composition weakening: child removes roles from "
            f"require_approval_for_roles: {removed_roles}",
            details={
                "base_require_approval_for_roles": sorted(base_esc_roles),
                "merged_require_approval_for_roles": sorted(merged_esc_roles),
                "removed_roles": removed_roles,
            },
        )

    # protocol_constraints must not add new families or weaken.
    # Use child overlay for structural comparison; merged_wf for value checks.
    # Only apply family-presence checks when the child explicitly declares
    # protocol_constraints; a child that omits the key inherits the base intact.
    base_proto = base_wf.get("protocol_constraints") or {}
    child_proto_raw = child_wf.get("protocol_constraints")  # None if child omits the key
    child_proto = child_proto_raw or {}
    merged_proto = merged_wf.get("protocol_constraints") or {}
    if base_proto and child_proto_raw is not None:
        # Child cannot add new protocol families
        if new_families := sorted(set(child_proto) - set(base_proto)):
            raise PolicyValidationError(
                f"Composition escalation: child adds new protocol families "
                f"not in base: {new_families}",
                details={"new_protocol_families": new_families},
            )
        # Child cannot remove base protocol families (check child overlay)
        if removed_families := sorted(set(base_proto) - set(child_proto)):
            raise PolicyValidationError(
                f"Composition weakening: child removes base protocol families: "
                f"{removed_families}",
                details={"removed_protocol_families": removed_families},
            )
    if base_proto:
        # For shared families, child cannot weaken scalar or list values
        for family, base_constraints in base_proto.items():
            merged_constraints = merged_proto.get(family, {})
            if isinstance(base_constraints, dict) and isinstance(merged_constraints, dict):
                for k, base_val in base_constraints.items():
                    merged_val = merged_constraints.get(k)
                    if merged_val is None:
                        raise PolicyValidationError(
                            f"Composition weakening: child removes "
                            f"{family}.{k!r} from protocol_constraints",
                            details={"family": family, "key": k},
                        )
                    if isinstance(base_val, list) and isinstance(merged_val, list):
                        if widened := sorted(set(merged_val) - set(base_val)):
                            raise PolicyValidationError(
                                f"Composition escalation: child widens "
                                f"{family}.{k!r}: {widened}",
                                details={"family": family, "key": k, "widened": widened},
                            )
                    elif base_val != merged_val:
                        raise PolicyValidationError(
                            f"Composition escalation: child changes "
                            f"{family}.{k!r} scalar value",
                            details={
                                "family": family,
                                "key": k,
                                "base": base_val,
                                "merged": merged_val,
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

    # Enforce monotonic restriction: child must not escalate privileges.
    # Pass the raw overlay policy so that array intersection/union strategies
    # cannot hide widening attempts in workflow DSL fields.
    _validate_composition_restriction(base_policy_dict, merged, overlay=policy)

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
