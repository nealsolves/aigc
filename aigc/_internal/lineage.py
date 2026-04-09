"""
Lineage reconstruction for multi-invocation audit trails.

AuditLineage builds a directed acyclic graph (DAG) from audit artifacts
loaded from a JSONL audit trail. Nodes are identified by each artifact's
stored ``"checksum"`` field when present (written by ``AuditChain``),
falling back to ``sha256(canonical_json_bytes(artifact))`` for unchained
artifacts. Edges are drawn from
artifact["provenance"]["derived_from_audit_checksums"] — the caller-supplied
list of prior artifact checksums this invocation was derived from.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

from aigc._internal.utils import canonical_json_bytes


def _artifact_checksum(artifact: dict[str, Any]) -> str:
    """
    Derive the node key for an artifact.

    If the artifact carries a stored 'checksum' field (written by AuditChain
    as sha256 of the artifact-without-checksum), use that value directly —
    it is the canonical identifier callers already reference in
    derived_from_audit_checksums (per the integration guide).

    For artifacts without a stored checksum (not processed by AuditChain),
    fall back to sha256(canonical_json(artifact)).
    """
    stored = artifact.get("checksum")
    if stored is not None:
        if not isinstance(stored, str):
            raise ValueError(
                f"checksum field must be a str, got {type(stored).__name__!r}"
            )
        if stored:
            return stored
    return hashlib.sha256(canonical_json_bytes(artifact)).hexdigest()


class AuditLineage:
    """
    Directed acyclic graph of audit artifacts.

    Nodes are audit artifact dicts, identified by their SHA-256 checksum.
    Edges flow from child to parent: an artifact's
    ``provenance["derived_from_audit_checksums"]`` lists the checksums of
    the artifacts it was derived from (its parents).
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._parents: dict[str, list[str]] = {}
        self._children: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def add_artifact(self, artifact: dict[str, Any]) -> str:
        """
        Add an artifact to the graph.

        Returns the artifact's checksum (its node key). If an artifact with
        the same checksum already exists it is silently overwritten.

        Raises ValueError (without mutating the graph) if the artifact's
        provenance fields are malformed.
        """
        key = _artifact_checksum(artifact)

        # Validate provenance before any graph mutation so that a bad artifact
        # cannot corrupt an otherwise-valid graph state.
        provenance = artifact.get("provenance") or {}
        raw_parents = provenance.get("derived_from_audit_checksums") or []
        if not isinstance(raw_parents, list):
            raise ValueError(
                f"derived_from_audit_checksums must be a list, got {type(raw_parents).__name__!r}"
            )
        for item in raw_parents:
            if not isinstance(item, str):
                raise ValueError(
                    f"derived_from_audit_checksums entries must be str, got {type(item).__name__!r}"
                )
        parent_keys: list[str] = raw_parents

        # Mutation begins here — validation passed.
        self._artifacts[key] = artifact

        # Clear stale parent edges when overwriting an existing key so that
        # topology stays consistent with the new artifact's provenance.
        if key in self._parents:
            for old_parent in self._parents[key]:
                if old_parent in self._children:
                    self._children[old_parent] = [
                        c for c in self._children[old_parent] if c != key
                    ]
        self._parents[key] = []
        if key not in self._children:
            self._children[key] = []

        for parent_key in parent_keys:
            if parent_key not in self._parents[key]:
                self._parents[key].append(parent_key)
            # Initialise parent's child list if not yet in graph
            if parent_key not in self._children:
                self._children[parent_key] = []
            if key not in self._children[parent_key]:
                self._children[parent_key].append(key)

        return key

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "AuditLineage":
        """
        Load all artifacts from a JSONL audit trail file.

        Each non-empty line must be a JSON object representing one audit
        artifact.
        """
        lineage = cls()
        path = Path(path)
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                lineage.add_artifact(json.loads(line))
        return lineage

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, checksum: str) -> "dict[str, Any] | None":
        """Return the artifact with the given checksum, or None."""
        return self._artifacts.get(checksum)

    def checksum_of(self, artifact: dict[str, Any]) -> str:
        """
        Return the node key for an artifact, using the same logic as add_artifact().

        Callers need this after from_jsonl() to obtain stable keys for
        ancestors() / descendants() without calling the private
        _artifact_checksum() helper directly.
        """
        return _artifact_checksum(artifact)

    def __len__(self) -> int:
        return len(self._artifacts)

    # ------------------------------------------------------------------
    # Graph topology
    # ------------------------------------------------------------------

    def roots(self) -> list[dict[str, Any]]:
        """Artifacts with no declared parents (empty provenance edge list).

        An artifact with declared-but-missing parents is an orphan, not a root.
        """
        return [
            self._artifacts[key]
            for key in self._artifacts
            if not self._parents.get(key)
        ]

    def leaves(self) -> list[dict[str, Any]]:
        """Artifacts with no children."""
        return [
            self._artifacts[key]
            for key in self._artifacts
            if not self._children.get(key)
        ]

    def ancestors(self, checksum: str) -> list[dict[str, Any]]:
        """
        All ancestors of the artifact identified by *checksum* (BFS upstream).

        Only returns artifacts present in the graph. Unknown parent checksums
        are skipped.
        """
        visited: set[str] = set()
        queue: deque[str] = deque(self._parents.get(checksum, []))
        result: list[dict[str, Any]] = []
        while queue:
            key = queue.popleft()
            if key in visited:
                continue
            visited.add(key)
            if key in self._artifacts:
                result.append(self._artifacts[key])
                queue.extend(self._parents.get(key, []))
        return result

    def descendants(self, checksum: str) -> list[dict[str, Any]]:
        """
        All descendants of the artifact identified by *checksum* (BFS downstream).
        """
        visited: set[str] = set()
        queue: deque[str] = deque(self._children.get(checksum, []))
        result: list[dict[str, Any]] = []
        while queue:
            key = queue.popleft()
            if key in visited:
                continue
            visited.add(key)
            if key in self._artifacts:
                result.append(self._artifacts[key])
                queue.extend(self._children.get(key, []))
        return result

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def orphans(self) -> list[dict[str, Any]]:
        """
        Artifacts that reference parent checksums not present in the graph.
        """
        result = []
        for key, artifact in self._artifacts.items():
            for parent_key in self._parents.get(key, []):
                if parent_key not in self._artifacts:
                    result.append(artifact)
                    break
        return result

    def has_cycle(self) -> bool:
        """
        True if the graph contains a directed cycle (Kahn's algorithm).

        A valid audit DAG should never have cycles. This check exists to
        detect corrupt or adversarially crafted trails.
        """
        in_degree: dict[str, int] = {
            key: sum(1 for p in parents if p in self._artifacts)
            for key, parents in self._parents.items()
        }
        queue: deque[str] = deque(k for k, d in in_degree.items() if d == 0)
        visited = 0
        while queue:
            key = queue.popleft()
            visited += 1
            for child_key in self._children.get(key, []):
                if child_key in in_degree:
                    in_degree[child_key] -= 1
                    if in_degree[child_key] == 0:
                        queue.append(child_key)
        return visited < len(self._artifacts)
