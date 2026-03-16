"""
Tamper-evident audit chain for AIGC governance artifacts.

Provides hash-chained audit evidence where each artifact links to the
previous one via a cryptographic hash. This creates an append-only,
tamper-evident chain that complements per-artifact integrity (checksums).

Chain construction rules:
- Each artifact includes previous_audit_checksum (hash of prior artifact)
- chain_id groups related artifacts in a governance session
- chain_index provides ordering within a chain
- The first artifact in a chain has previous_audit_checksum = null
- Verification traverses the chain and checks each link

What is tamper-evident:
- Insertion, deletion, or reordering of artifacts in the chain
- Modification of any artifact field (detected via checksum mismatch)

What is NOT tamper-evident (requires external controls):
- Complete chain replacement
- Attacks on the hash algorithm itself
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from aigc._internal.utils import canonical_json_bytes

logger = logging.getLogger("aigc.audit_chain")


class AuditChain:
    """Manages a tamper-evident chain of audit artifacts.

    Usage::

        chain = AuditChain()
        artifact1 = generate_audit_artifact(...)
        chain.append(artifact1)  # Adds chain fields

        artifact2 = generate_audit_artifact(...)
        chain.append(artifact2)  # Links to artifact1

        assert chain.verify()  # Checks all links
    """

    def __init__(self, chain_id: str | None = None) -> None:
        """Initialize a new audit chain.

        :param chain_id: Optional chain identifier. Generated if not provided.
        """
        self._chain_id = chain_id or str(uuid.uuid4())
        self._artifacts: list[dict[str, Any]] = []
        self._last_checksum: str | None = None

    @property
    def chain_id(self) -> str:
        return self._chain_id

    @property
    def length(self) -> int:
        return len(self._artifacts)

    def _compute_artifact_checksum(self, artifact: dict[str, Any]) -> str:
        """Compute SHA-256 checksum of an artifact's canonical form."""
        return hashlib.sha256(canonical_json_bytes(artifact)).hexdigest()

    def append(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Append an artifact to the chain, adding chain metadata fields.

        Mutates the artifact in place and returns it.

        :param artifact: Audit artifact dict
        :return: The artifact with chain fields added
        """
        chain_index = len(self._artifacts)

        artifact["chain_id"] = self._chain_id
        artifact["chain_index"] = chain_index
        artifact["previous_audit_checksum"] = self._last_checksum

        # Compute checksum of the complete artifact (including chain fields)
        self._last_checksum = self._compute_artifact_checksum(artifact)
        self._artifacts.append(artifact)

        logger.debug(
            "Artifact appended to chain %s at index %d",
            self._chain_id,
            chain_index,
        )
        return artifact

    def verify(self) -> tuple[bool, list[str]]:
        """Verify the integrity of the entire chain.

        :return: (valid, errors) where valid is True if chain is intact
        """
        errors: list[str] = []

        if not self._artifacts:
            return True, []

        # First artifact must have null previous_audit_checksum
        first = self._artifacts[0]
        if first.get("previous_audit_checksum") is not None:
            errors.append(
                "Chain index 0: previous_audit_checksum must be null"
            )

        prev_checksum: str | None = None
        for i, artifact in enumerate(self._artifacts):
            # Verify chain_index
            if artifact.get("chain_index") != i:
                errors.append(
                    f"Chain index {i}: expected chain_index={i}, "
                    f"got {artifact.get('chain_index')}"
                )

            # Verify chain_id
            if artifact.get("chain_id") != self._chain_id:
                errors.append(
                    f"Chain index {i}: chain_id mismatch"
                )

            # Verify link to previous
            if artifact.get("previous_audit_checksum") != prev_checksum:
                errors.append(
                    f"Chain index {i}: previous_audit_checksum mismatch "
                    f"(broken link)"
                )

            # Compute this artifact's checksum for next link
            prev_checksum = self._compute_artifact_checksum(artifact)

        valid = len(errors) == 0
        if not valid:
            logger.warning(
                "Chain %s verification failed: %d error(s)",
                self._chain_id,
                len(errors),
            )
        return valid, errors


def verify_chain(artifacts: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Verify a chain of artifacts without an AuditChain instance.

    Useful for verifying chains loaded from storage.

    :param artifacts: Ordered list of artifacts with chain fields
    :return: (valid, errors)
    """
    errors: list[str] = []

    if not artifacts:
        return True, []

    # Determine chain_id from first artifact
    chain_id = artifacts[0].get("chain_id")

    prev_checksum: str | None = None
    for i, artifact in enumerate(artifacts):
        if artifact.get("chain_index") != i:
            errors.append(
                f"Index {i}: expected chain_index={i}, "
                f"got {artifact.get('chain_index')}"
            )

        if artifact.get("chain_id") != chain_id:
            errors.append(f"Index {i}: chain_id mismatch")

        if artifact.get("previous_audit_checksum") != prev_checksum:
            errors.append(
                f"Index {i}: previous_audit_checksum mismatch (broken link)"
            )

        prev_checksum = hashlib.sha256(
            canonical_json_bytes(artifact)
        ).hexdigest()

    return len(errors) == 0, errors
