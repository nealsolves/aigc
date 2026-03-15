"""
Audit artifact signing and verification.

Provides HMAC-SHA256 based signing of audit artifacts with a pluggable
signer interface for alternative implementations.

Signing is applied to the canonical JSON representation of the artifact
(excluding the signature field itself) to ensure deterministic signatures.
"""

from __future__ import annotations

import abc
import hashlib
import hmac
import logging
from typing import Any

from aigc._internal.utils import canonical_json_bytes

logger = logging.getLogger("aigc.signing")


class ArtifactSigner(abc.ABC):
    """Abstract base class for audit artifact signers."""

    @abc.abstractmethod
    def sign(self, payload: bytes) -> str:
        """Sign canonical payload bytes and return signature string.

        :param payload: Canonical JSON bytes of the artifact (without signature)
        :return: Signature string to embed in the artifact
        """

    @abc.abstractmethod
    def verify(self, payload: bytes, signature: str) -> bool:
        """Verify a signature against canonical payload bytes.

        :param payload: Canonical JSON bytes of the artifact (without signature)
        :param signature: Signature string from the artifact
        :return: True if signature is valid
        """


class HMACSigner(ArtifactSigner):
    """HMAC-SHA256 based artifact signer.

    Uses a shared secret key for signing and verification.
    Suitable for single-organization SDK deployments where the
    signing key is managed as a deployment secret.

    Usage::

        signer = HMACSigner(key=b"my-secret-key")
        signed_artifact = sign_artifact(artifact, signer)
        assert verify_artifact(signed_artifact, signer)
    """

    def __init__(self, key: bytes) -> None:
        if not key:
            raise ValueError("Signing key must be non-empty")
        self._key = key

    def sign(self, payload: bytes) -> str:
        """Produce HMAC-SHA256 signature as hex string."""
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature using constant-time comparison."""
        expected = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def _canonical_signing_payload(artifact: dict[str, Any]) -> bytes:
    """Produce canonical bytes for signing (artifact without signature field).

    The signature field is excluded from the payload to avoid circular
    dependency. All other fields are included in sorted-key canonical form.
    """
    signable = {k: v for k, v in artifact.items() if k != "signature"}
    return canonical_json_bytes(signable)


def sign_artifact(
    artifact: dict[str, Any],
    signer: ArtifactSigner,
) -> dict[str, Any]:
    """Sign an audit artifact in place and return it.

    :param artifact: Audit artifact dict (signature field will be set)
    :param signer: Signer implementation
    :return: The artifact with signature field populated
    """
    payload = _canonical_signing_payload(artifact)
    artifact["signature"] = signer.sign(payload)
    logger.debug("Artifact signed: %s", artifact.get("enforcement_result"))
    return artifact


def verify_artifact(
    artifact: dict[str, Any],
    signer: ArtifactSigner,
) -> bool:
    """Verify an audit artifact's signature.

    :param artifact: Audit artifact dict with signature field
    :param signer: Signer implementation (must match the signing key)
    :return: True if signature is valid, False otherwise
    """
    signature = artifact.get("signature")
    if signature is None:
        logger.warning("Artifact has no signature to verify")
        return False

    payload = _canonical_signing_payload(artifact)
    valid = signer.verify(payload, signature)
    if not valid:
        logger.warning("Artifact signature verification failed")
    return valid
