# ADR-0008: Governance Artifact Chain (Tamper-Evident Audit Sequence)

Date: 2026-03-05
Status: Proposed
Owners: Neal

---

## Context

Individual audit artifacts are checksummed (SHA-256 of canonical JSON) and
optionally signed (planned in ADR-D05, roadmap v0.3.0). However, there is no
mechanism to detect:

1. **Deletion** — an artifact is removed from the audit trail
2. **Reordering** — artifacts are rearranged to disguise a sequence of actions
3. **Insertion** — a fabricated artifact is injected into the trail

These are distinct from *modification* of a single artifact (which signing
addresses). The audit trail as a *sequence* has no integrity guarantee.

For compliance frameworks (SOC 2, ISO 27001) and forensic analysis, the
question is not just "is this artifact authentic?" but "is the complete
sequence of artifacts intact and unmodified?"

### Constraints

- Hash chaining must be optional (not all deployments need it)
- Must not introduce mandatory dependencies (no blockchain, no external
  services)
- Must work with any `AuditSink` (JSONL, database, SIEM)
- Must be deterministic: same sequence of enforcements produces same chain
- Signing (HMAC/asymmetric) is a separate concern from chaining

---

## Decision

Introduce optional hash-chain linking between consecutive audit artifacts
within an `AIGC` instance. Each artifact optionally includes
`previous_audit_checksum`, creating a singly-linked chain that makes
deletions and insertions detectable.

### Mechanism

```
Artifact N:
  checksum: SHA-256(canonical_json_bytes(artifact_N excluding signature fields))
  previous_audit_checksum: artifact_N-1.checksum
  chain_index: N

Artifact N+1:
  checksum: SHA-256(canonical_json_bytes(artifact_N+1 excluding signature fields))
  previous_audit_checksum: artifact_N.checksum
  chain_index: N+1
```

The first artifact in a chain has `previous_audit_checksum: null` and
`chain_index: 0`.

### New audit artifact fields (v1.2 additive)

```json
{
  "previous_audit_checksum": "sha256:abc123...",
  "chain_index": 42,
  "chain_id": "aigc-instance-uuid"
}
```

- `previous_audit_checksum`: SHA-256 hex of the previous artifact's canonical
  bytes (null for the first artifact in a chain).
- `chain_index`: Monotonically increasing integer within a chain. Enables
  gap detection without reading every artifact.
- `chain_id`: UUID identifying the `AIGC` instance that produced the chain.
  Enables correlation when multiple instances write to the same sink.

### Opt-in activation

```python
aigc = AIGC(
    sink=JsonFileAuditSink("audit.jsonl"),
    chain_artifacts=True,  # enables hash chaining
)
```

When `chain_artifacts=False` (default), the three chain fields are omitted
from artifacts. No performance or storage overhead.

### Verification

A standalone verification function (and future CLI command) walks a sequence
of artifacts and checks:

1. Each `previous_audit_checksum` matches the computed checksum of the
   preceding artifact
2. `chain_index` is monotonically increasing with no gaps
3. `chain_id` is consistent within the sequence
4. No artifact has been modified (recompute checksum, compare)

```python
from aigc.audit import verify_chain

artifacts = load_artifacts("audit.jsonl")
result = verify_chain(artifacts)
# result.valid: bool
# result.breaks: list of (index, reason) tuples
```

---

## Options Considered

### Option A: Singly-linked hash chain on AIGC instance (chosen)

Pros:

- Simple, well-understood cryptographic primitive
- No external dependencies
- Deletion and insertion detectable
- Works with any sink (artifacts are self-contained)
- Optional — zero overhead when disabled

Cons:

- Chain breaks if AIGC instance restarts (new chain starts)
- Does not prevent reordering within a chain break
- Single-instance scope — cross-instance chains not supported

### Option B: Merkle tree over artifact batches

Pros:

- Efficient verification of large audit trails
- Can verify subsets without reading all artifacts

Cons:

- More complex implementation
- Requires batch boundaries (how often to close a tree?)
- Overkill for most deployments

### Option C: External append-only log (e.g., transparency log)

Pros:

- Strongest tamper-evidence guarantee
- Third-party verification possible

Cons:

- External dependency (network service)
- Availability concern — enforcement blocked if log is down?
- Contradicts "minimal dependencies" principle

---

## Consequences

- What becomes easier:
  - Compliance evidence: auditors can verify trail integrity with a single
    function call
  - Forensic analysis: deletions and insertions are detectable
  - Multi-instance deployments: `chain_id` enables per-instance correlation

- What becomes harder:
  - Instance restarts create chain breaks (mitigated: `chain_id` + initial
    `previous_audit_checksum: null` marks expected break points)
  - Sink implementations must preserve artifact ordering (already expected
    for JSONL; database sinks use `chain_index` for ordering)

- Risks introduced:
  - Chain verification is only as strong as the sink's append-only guarantee
  - Mitigation: document that sinks must preserve ordering; signing
    (separate concern) adds per-artifact authenticity
  - `previous_audit_checksum` creates a dependency between consecutive
    artifacts — parallel enforcement must serialize chain updates
  - Mitigation: chain update is protected by `threading.Lock` on the AIGC
    instance (already required for counter state)

---

## Contract Impact

- Enforcement pipeline impact: After `generate_audit_artifact()`, optionally
  compute and attach chain fields before `emit_to_sink()`.
- Policy DSL impact: None
- Schema impact: Three new optional fields in `audit_artifact.schema.json`
  (v1.2 additive). All nullable. Not in `required` array.
- Audit artifact impact: Three new fields when `chain_artifacts=True`
- Golden replays impact: New golden fixtures for chained artifacts. Chain
  verification golden replay.
- Structural impact: New `verify_chain()` function in `aigc._internal.audit`
  or `aigc._internal.chain`. Public export via `aigc.audit`.
- Backward compatibility: Fully backward compatible. Fields are optional and
  additive. Disabled by default.

---

## Validation

- `ci:signature` (v0.3.0): chain of 10 artifacts → `verify_chain()` returns
  valid. Remove artifact 5 → `verify_chain()` detects gap. Modify artifact 3 →
  `verify_chain()` detects checksum mismatch.
- Golden replay: 3-artifact chain with frozen timestamps. Assert
  `previous_audit_checksum` values match computed checksums.
- Determinism: same 3 enforcements with frozen time → identical chain
  checksums across 100 runs.
- Thread safety: 10-thread concurrent enforcement with `chain_artifacts=True`.
  Assert `chain_index` is monotonic with no gaps.
