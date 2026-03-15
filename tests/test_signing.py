"""Tests for audit artifact signing and verification (M2 feature)."""
import pytest
from aigc._internal.signing import (
    ArtifactSigner,
    HMACSigner,
    sign_artifact,
    verify_artifact,
    _canonical_signing_payload,
)


def _sample_artifact():
    return {
        "audit_schema_version": "1.2",
        "policy_file": "test.yaml",
        "policy_schema_version": "http://json-schema.org/draft-07/schema#",
        "policy_version": "1.0",
        "model_provider": "openai",
        "model_identifier": "gpt-4",
        "role": "planner",
        "enforcement_result": "PASS",
        "failures": [],
        "failure_gate": None,
        "failure_reason": None,
        "input_checksum": "a" * 64,
        "output_checksum": "b" * 64,
        "timestamp": 1000,
        "context": {},
        "metadata": {},
        "risk_score": None,
        "signature": None,
    }


# ── HMACSigner ──────────────────────────────────────────────────


def test_hmac_signer_empty_key_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        HMACSigner(key=b"")


def test_hmac_sign_and_verify():
    signer = HMACSigner(key=b"test-secret")
    payload = b"test payload data"
    sig = signer.sign(payload)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex
    assert signer.verify(payload, sig)


def test_hmac_verify_wrong_key():
    signer1 = HMACSigner(key=b"key-one")
    signer2 = HMACSigner(key=b"key-two")
    payload = b"data"
    sig = signer1.sign(payload)
    assert not signer2.verify(payload, sig)


def test_hmac_verify_tampered_payload():
    signer = HMACSigner(key=b"key")
    sig = signer.sign(b"original")
    assert not signer.verify(b"tampered", sig)


def test_hmac_deterministic():
    signer = HMACSigner(key=b"key")
    payload = b"data"
    assert signer.sign(payload) == signer.sign(payload)


# ── sign_artifact / verify_artifact ─────────────────────────────


def test_sign_artifact_sets_signature():
    signer = HMACSigner(key=b"secret")
    artifact = _sample_artifact()
    assert artifact["signature"] is None
    sign_artifact(artifact, signer)
    assert artifact["signature"] is not None
    assert len(artifact["signature"]) == 64


def test_verify_signed_artifact():
    signer = HMACSigner(key=b"secret")
    artifact = _sample_artifact()
    sign_artifact(artifact, signer)
    assert verify_artifact(artifact, signer)


def test_verify_unsigned_artifact():
    signer = HMACSigner(key=b"secret")
    artifact = _sample_artifact()
    assert not verify_artifact(artifact, signer)


def test_verify_tampered_artifact():
    signer = HMACSigner(key=b"secret")
    artifact = _sample_artifact()
    sign_artifact(artifact, signer)
    artifact["enforcement_result"] = "FAIL"
    assert not verify_artifact(artifact, signer)


def test_signature_excluded_from_payload():
    """Signature field is not included in signing payload."""
    artifact = _sample_artifact()
    artifact["signature"] = "should-be-excluded"
    payload = _canonical_signing_payload(artifact)
    assert b"should-be-excluded" not in payload
    assert b'"signature"' not in payload


def test_sign_fail_artifact():
    """FAIL artifacts can be signed too."""
    signer = HMACSigner(key=b"secret")
    artifact = _sample_artifact()
    artifact["enforcement_result"] = "FAIL"
    artifact["failure_gate"] = "role_validation"
    artifact["failure_reason"] = "Unauthorized role"
    sign_artifact(artifact, signer)
    assert verify_artifact(artifact, signer)


# ── Determinism ──────────────────────────────────────────────────


def test_signing_deterministic():
    signer = HMACSigner(key=b"key")
    a1 = _sample_artifact()
    a2 = _sample_artifact()
    sign_artifact(a1, signer)
    sign_artifact(a2, signer)
    assert a1["signature"] == a2["signature"]


# ── Abstract interface ───────────────────────────────────────────


def test_abstract_signer_cannot_instantiate():
    with pytest.raises(TypeError):
        ArtifactSigner()
