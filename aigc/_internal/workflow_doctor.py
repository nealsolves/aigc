"""
workflow doctor — runtime/evidence-aware diagnostics for AIGC governance targets.

Doctor always starts with lint for the detected target kind, then adds
time-aware and evidence-aware checks that static lint cannot perform.

Each public function returns a list of finding dicts:
    {
        "code":        str,   # machine-readable code
        "severity":    str,   # "ERROR" | "WARNING" | "INFO"
        "message":     str,   # human-readable description
        "next_action": str,   # plain-English guidance
    }

An empty list means no issues found.
The CLI exits 1 only if any finding has severity "ERROR".
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from aigc._internal.errors import PolicyLoadError, PolicyValidationError
from aigc._internal.policy_loader import load_policy
from aigc._internal.workflow_lint import (
    detect_target_kind,
    lint_policy,
    lint_starter_dir,
    lint_workflow_artifact,
    _audit_schema,
)

from jsonschema import Draft7Validator


# ---------------------------------------------------------------------------
# Next-action registry
# ---------------------------------------------------------------------------

_NEXT_ACTIONS: dict[str, str] = {
    "WORKFLOW_INVALID_TRANSITION": (
        "Ensure your workflow follows the correct lifecycle: "
        "open_session() -> enforce_step_pre_call() / enforce_step_post_call() "
        "-> complete() or cancel(). "
        "Call resume() before adding steps when the session is PAUSED."
    ),
    "WORKFLOW_APPROVAL_REQUIRED": (
        "Implement a real approval callback to replace the simulated one in "
        "_request_human_approval(). When approval is denied, call "
        "session.cancel() explicitly. When approved, call session.resume() "
        "before continuing with additional steps."
    ),
    "WORKFLOW_SOURCE_REQUIRED": (
        "Provide context.provenance.source_ids in every invocation context "
        "when using ProvenanceGate(require_source_ids=True). "
        "See docs/INTEGRATION_GUIDE.md for provenance usage."
    ),
    "WORKFLOW_TOOL_BUDGET_EXCEEDED": (
        "Reduce the number of tool_calls in your invocation to stay within "
        "the max_calls limit defined in policy.yaml (tools.allowed_tools). "
        "See policies/policy_dsl_spec.md for tool constraint syntax."
    ),
    "WORKFLOW_STEP_BUDGET_EXCEEDED": (
        "The session reached its max_steps limit defined in the policy workflow "
        "block. Increase max_steps in policy.yaml, or redesign the workflow to "
        "complete within the allowed number of steps."
    ),
    "WORKFLOW_HOOK_DENIED": (
        "A ValidatorHook returned DENY or timed out. Inspect the hook's "
        "denial_reason in the error details. If using the built-in timeout, "
        "increase the hook's timeout_ms or make the hook respond faster."
    ),
    "WORKFLOW_UNSUPPORTED_BINDING": (
        "Remove or rename condition/guard entries that reference unsupported "
        "protocol names (grpc, websocket, soap). Only HTTP/REST adapter "
        "bindings are supported in v0.9.0."
    ),
    "WORKFLOW_SESSION_TOKEN_INVALID": (
        "Ensure callers provide a well-formed, non-replayed session token "
        "in the required precondition field. Use GovernanceSession as a "
        "context manager to manage token lifecycle automatically. "
        "Tokens are single-use; retry with a fresh token if the session "
        "is still open."
    ),
    "WORKFLOW_STARTER_INTEGRITY_ERROR": (
        "Re-run 'aigc workflow init --profile <profile>' to regenerate the "
        "starter, or fix the integrity issue described above. "
        "See the generated README.md in the starter directory for usage."
    ),
    "POLICY_LOAD_ERROR": (
        "Fix the policy file syntax or structure. "
        "See policies/policy_dsl_spec.md for the full policy DSL reference."
    ),
    "POLICY_SCHEMA_VALIDATION_ERROR": (
        "Fix the schema violation in policy.yaml. "
        "Run 'aigc policy lint <file>' to list all violations. "
        "See policies/policy_dsl_spec.md for field specifications."
    ),
    "TOOL_CONSTRAINT_VIOLATION": (
        "Fix the tool constraint issue in policy.yaml. "
        "See policies/policy_dsl_spec.md for tool allowlist syntax."
    ),
}

_DEFAULT_NEXT_ACTION = (
    "Review the policy or artifact described above. "
    "See docs/INTEGRATION_GUIDE.md and policies/policy_dsl_spec.md for guidance."
)


def _next_action(code: str) -> str:
    return _NEXT_ACTIONS.get(code, _DEFAULT_NEXT_ACTION)


# ---------------------------------------------------------------------------
# Finding constructors
# ---------------------------------------------------------------------------

def _finding(
    code: str,
    severity: str,
    message: str,
    next_action: str | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "next_action": next_action or _next_action(code),
    }


def _lint_to_doctor(lint_findings: list[dict]) -> list[dict]:
    """Promote lint findings to doctor findings (severity=ERROR for lint errors)."""
    result = []
    for f in lint_findings:
        code = f["code"]
        # Treat all lint failures as ERROR-severity in the doctor context
        result.append(_finding(
            code,
            "ERROR",
            f["message"],
        ))
    return result


# ---------------------------------------------------------------------------
# Policy doctor
# ---------------------------------------------------------------------------

_UNSUPPORTED_PROTOCOLS = frozenset({"grpc", "websocket", "soap"})

# Session-token misuse patterns from enforcement.py
_TOKEN_MISUSE_PATTERNS = [
    "SessionPreCallResult cannot be completed via enforce_post_call",
    "token belongs to a different session",
    "token already consumed",
    "token not registered in this session",
    "token fields do not match minted values",
]


def diagnose_workflow_policy(
    path: str,
    *,
    now: date | None = None,
) -> list[dict]:
    """
    Run doctor diagnostics on a policy YAML file.

    Steps:
    1. Lint (static checks)
    2. Date checks (expired / future-effective) using injected clock
    3. Full semantic validation via load_policy with same clock
    4. Unsupported binding pattern detection
    5. Session-token precondition advisory
    """
    findings: list[dict] = []
    if now is None:
        now = date.today()

    # 1. Run lint
    lint_findings = lint_policy(path)
    if lint_findings:
        findings.extend(_lint_to_doctor(lint_findings))
        return findings

    # Load the policy dict for deeper checks (already validated by lint)
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return findings  # lint already caught this

    if not isinstance(raw, dict):
        return findings

    # 2. Date checks with injected clock
    eff_raw = raw.get("effective_date")
    exp_raw = raw.get("expiration_date")

    if exp_raw:
        if isinstance(exp_raw, str):
            try:
                from datetime import date as _date
                exp = _date.fromisoformat(exp_raw)
            except ValueError:
                exp = None
        elif hasattr(exp_raw, "year"):
            exp = exp_raw
        else:
            exp = None

        if exp and now > exp:
            findings.append(_finding(
                "POLICY_LOAD_ERROR",
                "ERROR",
                f"Policy expired on {exp}. Today is {now}. "
                "Expired policies are rejected at runtime.",
            ))

    if eff_raw:
        if isinstance(eff_raw, str):
            try:
                from datetime import date as _date
                eff = _date.fromisoformat(eff_raw)
            except ValueError:
                eff = None
        elif hasattr(eff_raw, "year"):
            eff = eff_raw
        else:
            eff = None

        if eff and now < eff:
            findings.append(_finding(
                "POLICY_LOAD_ERROR",
                "WARNING",
                f"Policy is not yet effective (effective_date: {eff}, today: {now}). "
                "The policy will be rejected until its effective date.",
            ))

    # 3. Full semantic validation via load_policy (extends, composition, etc.)
    # Guard: skip only this semantic-validation step if date findings already
    # exist — load_policy uses the same validate_policy_dates path and would
    # otherwise duplicate those date-specific errors. The later advisory checks
    # still run on the raw policy payload.
    _has_date_findings = bool(findings)
    if not _has_date_findings:
        try:
            load_policy(str(path), clock=lambda: now)
        except (PolicyLoadError, PolicyValidationError) as exc:
            findings.append(_finding(
                exc.code,
                "ERROR",
                str(exc),
            ))
            return findings
        except Exception as exc:
            findings.append(_finding(
                "POLICY_LOAD_ERROR",
                "ERROR",
                f"Unexpected error during semantic validation: {exc}",
            ))
            return findings

    # 4. Unsupported binding detection
    conditions: dict = raw.get("conditions", {}) or {}
    guards: list = raw.get("guards", []) or []
    guard_condition_names = set()
    for g in guards:
        if isinstance(g, dict):
            cname = g.get("condition", "")
            if cname:
                guard_condition_names.add(cname)

    all_condition_names = set(conditions.keys()) | guard_condition_names
    binding_hits = {
        n for n in all_condition_names
        if any(proto in n.lower() for proto in _UNSUPPORTED_PROTOCOLS)
    }
    if binding_hits:
        findings.append(_finding(
            "WORKFLOW_UNSUPPORTED_BINDING",
            "WARNING",
            f"Policy references condition/guard names that suggest unsupported "
            f"protocol bindings: {sorted(binding_hits)}. "
            "Only HTTP/REST adapter bindings are supported in v0.9.0.",
            _next_action("WORKFLOW_UNSUPPORTED_BINDING"),
        ))

    # 5. Session-token precondition advisory
    pre_conditions = raw.get("pre_conditions", {}) or {}
    pre_required = pre_conditions.get("required", {}) or {}
    if isinstance(pre_required, dict):
        token_keys = {k for k in pre_required if "token" in k.lower()}
    else:
        token_keys = set()

    if token_keys:
        keys_str = ", ".join(sorted(token_keys))
        findings.append(_finding(
            "WORKFLOW_SESSION_TOKEN_INVALID",
            "INFO",
            f"Policy requires session token fields in preconditions: {keys_str}. "
            "Ensure tokens are well-formed and non-replayed; stale or malformed "
            "tokens raise WORKFLOW_SESSION_TOKEN_INVALID at runtime.",
            _next_action("WORKFLOW_SESSION_TOKEN_INVALID"),
        ))

    return findings


# ---------------------------------------------------------------------------
# Starter directory doctor
# ---------------------------------------------------------------------------

_APPROVAL_PATTERNS = [
    re.compile(r"session\.pause\(\)"),
    re.compile(r"_request_human_approval\("),
    re.compile(r"session\.resume\(\)"),
    re.compile(r"session\.cancel\(\)"),
]

_PROVENANCE_PATTERNS = [
    re.compile(r"ProvenanceGate\("),
    re.compile(r"require_source_ids\s*=\s*True"),
    re.compile(r"source_ids"),
]


def diagnose_starter_dir(path: str) -> list[dict]:
    """
    Run doctor diagnostics on a starter directory.

    Steps:
    1. Lint the starter directory
    2. Detect approval checkpoint pattern -> WORKFLOW_APPROVAL_REQUIRED advisory
    3. Detect regulated provenance requirement -> WORKFLOW_SOURCE_REQUIRED advisory
    """
    findings: list[dict] = []

    # 1. Lint
    lint_findings = lint_starter_dir(path)
    if lint_findings:
        findings.extend(_lint_to_doctor(lint_findings))
        return findings

    # Read workflow_example.py for pattern detection
    p = Path(path)
    workflow_py = p / "workflow_example.py"
    try:
        source = workflow_py.read_text(encoding="utf-8")
    except OSError:
        return findings

    # 2. Approval checkpoint detection
    approval_hit = any(pat.search(source) for pat in _APPROVAL_PATTERNS)
    if approval_hit:
        findings.append(_finding(
            "WORKFLOW_APPROVAL_REQUIRED",
            "INFO",
            "This starter includes a human approval checkpoint "
            "(session.pause() / session.resume() / session.cancel() pattern). "
            "You must implement a real approval callback to replace the "
            "simulated one in _request_human_approval().",
            _next_action("WORKFLOW_APPROVAL_REQUIRED"),
        ))

    # 3. Provenance / source-required detection
    provenance_hit = any(pat.search(source) for pat in _PROVENANCE_PATTERNS)
    if provenance_hit:
        findings.append(_finding(
            "WORKFLOW_SOURCE_REQUIRED",
            "INFO",
            "This starter requires source IDs in every invocation context "
            "(ProvenanceGate with require_source_ids=True). "
            "Provide context.provenance.source_ids in every enforce_step_pre_call() "
            "invocation, or enforcement will fail with CustomGateViolationError.",
            _next_action("WORKFLOW_SOURCE_REQUIRED"),
        ))

    return findings


# ---------------------------------------------------------------------------
# Workflow artifact doctor
# ---------------------------------------------------------------------------

_LIFECYCLE_FAILURE_PATTERNS = [
    "Invalid session lifecycle transition",
    "cannot call",
    "session is not in",
    "already in terminal state",
    "SessionStateError",
]


def diagnose_workflow_artifact(path: str) -> list[dict]:
    """
    Run doctor diagnostics on a workflow artifact JSON file.

    Steps:
    1. Lint the artifact
    2. Map FAILED + SessionStateError -> WORKFLOW_INVALID_TRANSITION
    3. INCOMPLETE artifacts -> recovery guidance
    """
    findings: list[dict] = []

    # 1. Lint
    lint_findings = lint_workflow_artifact(path)
    if lint_findings:
        findings.extend(_lint_to_doctor(lint_findings))
        return findings

    p = Path(path)
    artifact: dict = json.loads(p.read_text(encoding="utf-8"))
    status = artifact.get("status", "")
    failure_summary = artifact.get("failure_summary") or {}

    if status == "FAILED":
        exc_type = failure_summary.get("exception_type", "")
        msg = failure_summary.get("message", "")

        is_invalid_transition = (
            exc_type == "SessionStateError"
            or any(pat.lower() in msg.lower() for pat in _LIFECYCLE_FAILURE_PATTERNS)
        )
        if is_invalid_transition:
            findings.append(_finding(
                "WORKFLOW_INVALID_TRANSITION",
                "ERROR",
                f"Workflow session failed due to an invalid lifecycle transition. "
                f"Exception: {exc_type}. Message: {msg or '(none)'}.",
                _next_action("WORKFLOW_INVALID_TRANSITION"),
            ))
        else:
            findings.append(_finding(
                "POLICY_LOAD_ERROR",
                "ERROR",
                f"Workflow artifact has FAILED status. "
                f"Exception: {exc_type or '(unknown)'}. "
                f"Message: {msg or '(none)'}.",
                _DEFAULT_NEXT_ACTION,
            ))

    elif status == "INCOMPLETE":
        findings.append(_finding(
            "WORKFLOW_INVALID_TRANSITION",
            "WARNING",
            "Workflow artifact is INCOMPLETE. The session exited without a "
            "terminal call. Recovery options: call complete() when the workflow "
            "finishes normally; call cancel() to abandon a paused approval path; "
            "call resume() before adding steps if the session was paused.",
            _next_action("WORKFLOW_INVALID_TRANSITION"),
        ))

    return findings


# ---------------------------------------------------------------------------
# Invocation audit artifact doctor
# ---------------------------------------------------------------------------

_PROVENANCE_FAILURE_CODES = frozenset({
    "PROVENANCE_MISSING",
    "SOURCE_IDS_MISSING",
    "CUSTOM_GATE_VIOLATION",
})

_TOKEN_MISUSE_RE = re.compile(
    "|".join(re.escape(p) for p in _TOKEN_MISUSE_PATTERNS),
    re.IGNORECASE,
)


def diagnose_audit_artifact(path: str) -> list[dict]:
    """
    Run doctor diagnostics on an invocation audit artifact JSON file.

    Maps real runtime failure patterns to frozen PR-06 reason codes.
    """
    findings: list[dict] = []
    p = Path(path)

    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(_finding(
            "POLICY_LOAD_ERROR",
            "ERROR",
            f"Cannot read audit artifact: {exc}",
        ))
        return findings

    try:
        artifact: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        findings.append(_finding(
            "POLICY_LOAD_ERROR",
            "ERROR",
            f"JSON parse error in audit artifact: {exc}",
        ))
        return findings

    if not isinstance(artifact, dict):
        findings.append(_finding(
            "POLICY_LOAD_ERROR",
            "ERROR",
            "Audit artifact must be a JSON object.",
        ))
        return findings

    # Schema validation
    schema = _audit_schema()
    validator = Draft7Validator(schema)
    schema_errors = sorted(
        validator.iter_errors(artifact), key=lambda e: list(e.path)
    )
    if schema_errors:
        for err in schema_errors:
            pointer = ".".join(str(s) for s in err.absolute_path) or "$"
            findings.append(_finding(
                "POLICY_SCHEMA_VALIDATION_ERROR",
                "ERROR",
                f"Audit artifact schema violation at {pointer}: {err.message}",
            ))
        return findings

    enforcement_result = artifact.get("enforcement_result", "")
    if enforcement_result == "PASS":
        return findings  # No issues

    # FAIL — map to frozen reason codes
    failure_gate = artifact.get("failure_gate", "") or ""
    failure_reason = artifact.get("failure_reason", "") or ""
    failures: list[dict] = artifact.get("failures", []) or []
    failure_codes = {f.get("code", "") for f in failures if isinstance(f, dict)}
    failure_messages = " ".join(
        f.get("message", "") for f in failures if isinstance(f, dict)
    )
    all_failure_text = f"{failure_reason} {failure_messages}".strip()

    mapped = False

    # Source-required: custom_gate_violation with provenance-related codes
    if failure_gate == "custom_gate_violation":
        provenance_hit = bool(
            failure_codes & _PROVENANCE_FAILURE_CODES
            or re.search(
                r"provenance|source.?id", all_failure_text, re.IGNORECASE
            )
        )
        if provenance_hit:
            findings.append(_finding(
                "WORKFLOW_SOURCE_REQUIRED",
                "ERROR",
                f"Invocation failed due to missing source IDs or provenance. "
                f"Failure gate: {failure_gate}. "
                f"Reason: {failure_reason or '(see failures array)'}.",
                _next_action("WORKFLOW_SOURCE_REQUIRED"),
            ))
            mapped = True

    # Tool budget: tool_validation gate
    if failure_gate == "tool_validation":
        findings.append(_finding(
            "WORKFLOW_TOOL_BUDGET_EXCEEDED",
            "ERROR",
            f"Invocation failed due to tool constraint violation. "
            f"Failure gate: {failure_gate}. "
            f"Reason: {failure_reason or '(see failures array)'}.",
            _next_action("WORKFLOW_TOOL_BUDGET_EXCEEDED"),
        ))
        mapped = True

    # Session-token misuse: invocation_validation gate with token pattern
    if failure_gate == "invocation_validation":
        token_hit = bool(_TOKEN_MISUSE_RE.search(all_failure_text))
        if token_hit:
            findings.append(_finding(
                "WORKFLOW_SESSION_TOKEN_INVALID",
                "ERROR",
                f"Invocation failed due to session token misuse. "
                f"Failure gate: {failure_gate}. "
                f"Reason: {failure_reason or '(see failures array)'}.",
                _next_action("WORKFLOW_SESSION_TOKEN_INVALID"),
            ))
            mapped = True

    # Generic fallback
    if not mapped:
        findings.append(_finding(
            "POLICY_LOAD_ERROR",
            "ERROR",
            f"Invocation audit artifact shows FAIL. "
            f"Failure gate: {failure_gate or '(unknown)'}. "
            f"Reason: {failure_reason or '(see failures array)'}.",
            _DEFAULT_NEXT_ACTION,
        ))

    return findings


# ---------------------------------------------------------------------------
# Unified entry-point
# ---------------------------------------------------------------------------

def diagnose_target(
    path: str,
    *,
    kind: str = "auto",
    now: date | None = None,
) -> list[dict]:
    """
    Run doctor diagnostics on any supported target.

    Args:
        path: Path to the target.
        kind: One of "auto", "policy", "starter_dir", "workflow_artifact",
              "audit_artifact". When "auto", the kind is inferred.
        now:  Date to use for time-aware checks (defaults to today).

    Returns:
        List of finding dicts (empty = no issues).
    """
    if kind == "auto":
        kind = detect_target_kind(path)

    if kind == "policy":
        return diagnose_workflow_policy(path, now=now)
    elif kind == "starter_dir":
        return diagnose_starter_dir(path)
    elif kind == "workflow_artifact":
        return diagnose_workflow_artifact(path)
    elif kind == "audit_artifact":
        return diagnose_audit_artifact(path)
    else:
        return [_finding(
            "POLICY_LOAD_ERROR",
            "ERROR",
            f"Cannot determine target kind for: {path}. "
            "Supported targets: .yaml/.yml policy files, starter directories "
            "(containing policy.yaml + workflow_example.py + README.md), "
            "workflow artifact .json files, and invocation audit artifact .json files.",
        )]
