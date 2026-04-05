"""Regression tests for AIGC final audit findings (2026-04-05).

Finding #1 — PreCallResult forged via _origin stamping is now rejected by the
             HMAC integrity check added in addition to the sentinel check.
Finding #2 — Invalid _frozen_evidence_bytes now produces a typed
             InvocationValidationError + FAIL artifact, not a raw TypeError.
"""
from __future__ import annotations

import json

import pytest

from aigc._internal.enforcement import (
    AIGC,
    PreCallResult,
    _ENFORCEMENT_TOKEN,
    _token_sign,
    enforce_post_call,
    enforce_pre_call,
)
from aigc._internal.errors import InvocationValidationError

GOLDEN_POLICY = "tests/golden_replays/golden_policy_v1.yaml"


def _pre_call_inv(**overrides):
    inv = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "planner",
        "input": {"query": "test"},
        "context": {"role_declared": True, "schema_exists": True},
    }
    inv.update(overrides)
    return inv


def _valid_output():
    return {"result": "ok", "confidence": 0.9}


def _make_forged_token(
    *,
    evidence_bytes: bytes | None = None,
    hmac_bytes: bytes | None = None,
) -> PreCallResult:
    """Construct a PreCallResult that stamps _origin without going through Phase A.

    Used to verify that post-call rejects such tokens (Finding #1 path) or
    that corrupted-bytes tokens produce typed errors (Finding #2 path).
    """
    from aigc._internal.policy_loader import load_policy

    policy = load_policy(GOLDEN_POLICY)
    inv_snapshot = {
        "policy_file": GOLDEN_POLICY,
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-5-20250929",
        "role": "attacker",
        "input": {"query": "forged"},
        "context": {},
        "output": {},
    }

    token = PreCallResult(
        effective_policy=policy,
        resolved_guards=(),
        resolved_conditions={},
        phase_a_metadata={"gates_evaluated": [], "pre_call_timestamp": 0},
        invocation_snapshot=inv_snapshot,
        policy_file=GOLDEN_POLICY,
        model_provider="anthropic",
        model_identifier="claude-sonnet-4-5-20250929",
        role="attacker",
    )
    # Stamp _origin — the same bypass reproduced in the audit.
    object.__setattr__(token, "_origin", _ENFORCEMENT_TOKEN)
    object.__setattr__(token, "_frozen_effective_policy", dict(policy))
    object.__setattr__(token, "_frozen_invocation_snapshot", dict(inv_snapshot))
    object.__setattr__(token, "_frozen_phase_a_metadata", {})

    # If caller provides bytes, use them; otherwise default to valid JSON bytes
    # so tests can focus on the HMAC path.
    if evidence_bytes is None:
        evidence_bytes = json.dumps(
            {
                "invocation_snapshot": inv_snapshot,
                "phase_a_metadata": {"gates_evaluated": [], "pre_call_timestamp": 0},
                "guards_evaluated_engine": [],
                "conditions_resolved": {},
            },
            sort_keys=True,
        ).encode()
    object.__setattr__(token, "_frozen_evidence_bytes", evidence_bytes)

    policy_bytes = json.dumps(policy, sort_keys=True).encode()
    object.__setattr__(token, "_frozen_policy_bytes", policy_bytes)

    # Set HMAC: None means leave default b"" (HMAC check will fail).
    # Caller can pass _token_sign(evidence_bytes) to make HMAC pass.
    if hmac_bytes is not None:
        object.__setattr__(token, "_token_hmac", hmac_bytes)
    # else: _token_hmac stays at default b"" — invalid digest, HMAC check fails.

    return token


# ── Finding #1: HMAC check rejects forged tokens ─────────────────────────────


class TestFinding1HMACRejectsForgedTokens:
    """A token forged by stamping _origin without the session key must be
    rejected by the HMAC integrity check with InvocationValidationError.

    Before the fix, forged tokens with _origin=_ENFORCEMENT_TOKEN would
    pass enforce_post_call() and return PASS.
    """

    def test_module_forged_origin_no_hmac_raises(self):
        """Forged _origin with default b'' HMAC raises InvocationValidationError."""
        token = _make_forged_token()
        with pytest.raises(InvocationValidationError, match="integrity check failed"):
            enforce_post_call(token, _valid_output())

    def test_module_forged_origin_no_hmac_attaches_artifact(self):
        """HMAC failure path attaches a FAIL artifact to the exception."""
        token = _make_forged_token()
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(token, _valid_output())
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "invocation_validation"

    def test_module_forged_origin_no_hmac_does_not_return_pass(self):
        """Forged token must not produce a PASS artifact (pre-fix behavior)."""
        token = _make_forged_token()
        with pytest.raises(InvocationValidationError):
            enforce_post_call(token, _valid_output())
        # If we reach here the exception was raised — no PASS artifact returned.

    def test_aigc_forged_origin_no_hmac_raises(self):
        """AIGC instance: forged _origin with no HMAC raises InvocationValidationError."""
        engine = AIGC()
        token = _make_forged_token()
        with pytest.raises(InvocationValidationError, match="integrity check failed"):
            engine.enforce_post_call(token, _valid_output())

    def test_aigc_forged_origin_no_hmac_attaches_artifact(self):
        """AIGC instance: HMAC failure attaches a FAIL artifact."""
        engine = AIGC()
        token = _make_forged_token()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(token, _valid_output())
        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"

    def test_genuine_token_passes_hmac_check(self):
        """A genuine token issued by enforce_pre_call passes the HMAC check."""
        pre = enforce_pre_call(_pre_call_inv())
        artifact = enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"

    def test_genuine_aigc_token_passes_hmac_check(self):
        """A genuine AIGC token passes the HMAC check."""
        engine = AIGC()
        pre = engine.enforce_pre_call(_pre_call_inv())
        artifact = engine.enforce_post_call(pre, _valid_output())
        assert artifact["enforcement_result"] == "PASS"


# ── Finding #2: invalid evidence bytes → typed error, not raw TypeError ───────


class TestFinding2InvalidEvidenceBytesTypedError:
    """Invalid _frozen_evidence_bytes must produce InvocationValidationError +
    FAIL artifact, not a raw TypeError.

    Before the fix, if _frozen_evidence_bytes was None or malformed JSON,
    json.loads() raised a raw TypeError or ValueError with no audit artifact.

    To trigger this path we need a token that passes the HMAC check but has
    invalid bytes — achieved by using _token_sign to compute a valid HMAC over
    the invalid bytes.
    """

    def test_module_invalid_bytes_raises_typed_error(self):
        """Invalid evidence bytes → InvocationValidationError, not TypeError."""
        bad_bytes = b"this is not valid json"
        token = _make_forged_token(
            evidence_bytes=bad_bytes,
            hmac_bytes=_token_sign(bad_bytes),
        )
        with pytest.raises(InvocationValidationError):
            enforce_post_call(token, _valid_output())

    def test_module_invalid_bytes_attaches_artifact(self):
        """Invalid evidence bytes: exception has attached FAIL artifact."""
        bad_bytes = b"not json"
        token = _make_forged_token(
            evidence_bytes=bad_bytes,
            hmac_bytes=_token_sign(bad_bytes),
        )
        with pytest.raises(InvocationValidationError) as exc_info:
            enforce_post_call(token, _valid_output())
        artifact = exc_info.value.audit_artifact
        assert artifact is not None
        assert artifact["enforcement_result"] == "FAIL"
        assert artifact["failure_gate"] == "invocation_validation"

    def test_module_invalid_bytes_is_not_raw_typeerror(self):
        """Invalid evidence bytes must NOT raise a bare TypeError."""
        bad_bytes = b"not json"
        token = _make_forged_token(
            evidence_bytes=bad_bytes,
            hmac_bytes=_token_sign(bad_bytes),
        )
        # TypeError must not escape — only InvocationValidationError is allowed.
        try:
            enforce_post_call(token, _valid_output())
        except InvocationValidationError:
            pass  # expected
        except TypeError as e:
            pytest.fail(f"Raw TypeError escaped enforce_post_call(): {e}")

    def test_aigc_invalid_bytes_raises_typed_error(self):
        """AIGC instance: invalid evidence bytes → InvocationValidationError."""
        bad_bytes = b"not json at all"
        token = _make_forged_token(
            evidence_bytes=bad_bytes,
            hmac_bytes=_token_sign(bad_bytes),
        )
        engine = AIGC()
        with pytest.raises(InvocationValidationError):
            engine.enforce_post_call(token, _valid_output())

    def test_aigc_invalid_bytes_attaches_artifact(self):
        """AIGC instance: invalid evidence bytes: FAIL artifact attached."""
        bad_bytes = b"bad"
        token = _make_forged_token(
            evidence_bytes=bad_bytes,
            hmac_bytes=_token_sign(bad_bytes),
        )
        engine = AIGC()
        with pytest.raises(InvocationValidationError) as exc_info:
            engine.enforce_post_call(token, _valid_output())
        assert exc_info.value.audit_artifact is not None
        assert exc_info.value.audit_artifact["enforcement_result"] == "FAIL"
