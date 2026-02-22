# ADR-0006: Include Invocation Context in Audit Artifact

Date: 2026-02-17
Status: Accepted
Owners: Neal

---

## Context

`generate_audit_artifact` in `src/audit.py` produced a flat artifact containing
enforcement metadata (role, checksums, gate results, etc.) but omitted
`invocation["context"]` — the caller-supplied session and tenant fields.

When a host application implemented `SQLiteAuditSink`, it needed to populate
a `session_id` column in the `aigc_audit_log` table.  Because `emit(artifact)`
receives only the artifact (not the raw invocation), and because `session_id`
was not in the artifact, every audit row had `session_id = NULL`.  Session-level
correlation of governance events was impossible.

The root cause: the audit artifact was designed around "what did AIGC enforce?"
rather than "what invocation produced this artifact?" — making artifacts
non-self-contained for replay and correlation purposes.

---

## Decision

Include `invocation.get("context", {})` verbatim in the audit artifact as a
top-level `context` key.  Every artifact now carries the caller-supplied
context dict (e.g. `session_id`, `tenant_id`, `execution_group`) alongside
the enforcement result.

Consequences:

- All `AuditSink.emit(artifact)` implementations can read context fields
  without changes to the sink interface.
- Artifacts are self-contained: a sink or replay tool no longer needs the
  original invocation to recover session/tenant identity.
- `AUDIT_SCHEMA_VERSION` bumps from `"1.0"` to `"1.1"` to signal the contract
  change.
- `context` is added to the `required` array in `schemas/audit_artifact.schema.json`.
- `golden_expected_audit.json` `audit_schema_version` field updated to `"1.1"`.

---

## Options Considered

### Option A: Include context in artifact (chosen)

Pros:
- No interface change to `AuditSink.emit()`
- Artifact is self-contained; sinks need only the artifact
- Consistent with the principle that the artifact is the authoritative record

Cons:
- Context may contain large or sensitive payloads; callers must sanitize
  context before passing to `enforce_invocation` if needed

### Option B: Pass invocation alongside artifact to `emit()`

Change `AuditSink.emit(artifact)` to `emit(artifact, invocation)`.

Pros:
- Sinks have access to all invocation data, not just what's in the artifact

Cons:
- Breaking change to `AuditSink` ABC — all existing sinks must update signatures
- Widens the sink interface; sinks could access raw input/output, creating
  privacy risk if sinks log or forward the invocation

### Option C: Leave session_id out (no change)

Cons:
- Audit rows have `NULL` session_id — correlation across sessions impossible
- Violates the intent of the `aigc_audit_log` table schema in host applications

---

## Consequences

- Audit artifacts now contain caller context fields.  Callers passing sensitive
  data in `context` (e.g. PII in tenant metadata) should sanitize before calling
  `enforce_invocation`.
- The `AUDIT_SCHEMA_VERSION = "1.1"` change is detectable by any consumer
  reading the `audit_schema_version` field in the artifact.
- Replay tools and golden replays that check `audit_schema_version == "1.0"`
  must be updated (golden_expected_audit.json updated in this same change).

---

## Contract Impact

- Enforcement pipeline impact: None (`generate_audit_artifact` signature
  unchanged; context read directly from `invocation`)
- Policy DSL impact: None
- Schema impact: `context` property added; `context` added to `required`;
  `audit_schema_version` in artifact changes from `"1.0"` to `"1.1"`
- Audit artifact impact: New `context` field always present
- Golden replays impact: `golden_expected_audit.json` `audit_schema_version`
  updated to `"1.1"`
- Structural impact: None
- Backward compatibility: `audit_schema_version` field allows consumers to
  detect the version; `"1.1"` artifacts are a strict superset of `"1.0"`
  artifacts (no fields removed)

---

## Validation

- `python -m pytest` passes with 180 tests (including `test_audit_contract`
  which validates the artifact against the schema).
- `test_golden_replay_success` passes because it asserts named fields only and
  the `audit_schema_version` comparison now uses `"1.1"`.
- Host application integration tests pass with `session_id` correctly
  populated in every `aigc_audit_log` row.
