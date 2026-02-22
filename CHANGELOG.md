# Changelog

All notable changes to AIGC are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] - 2026-02-17

### Added

- Invocation `context` included in audit artifacts for sink correlation
  (session ID, tenant ID, trace ID) — ADR-0006
- Absolute policy paths supported for installed-library use — ADR-0005
- CI parity with network-restricted environments (`--no-build-isolation`)

## [0.1.0] - 2026-02-16

### Initial Release

- **Phase 1 — Core Pipeline**
  - `enforce_invocation()` single entry point with fail-closed semantics
  - YAML policy loading with Draft-07 JSON Schema validation
  - Role allowlist enforcement
  - Precondition and output schema validation
  - Postcondition enforcement (`output_schema_valid`)
  - Deterministic audit artifact generation with canonical SHA-256 checksums
  - FAIL audit artifacts emitted before exception propagation — ADR-0001
  - Typed exception hierarchy (`PreconditionError`, `SchemaValidationError`,
    `GovernanceViolationError`)
  - Golden trace regression testing framework

- **Phase 2 — Full DSL**
  - Conditional guards (`when/then` rules with additive effects) — Phase 2.1
  - Named conditions (boolean flags from context with defaults) — Phase 2.2
  - Tool constraints (allowlists and per-tool `max_calls` caps) — Phase 2.3
  - Retry policy (`with_retry()` for transient `SchemaValidationError`) — Phase 2.4
  - Policy composition (`extends` inheritance with recursive merge and
    cycle detection) — Phase 2.6
  - Extended audit metadata (guards, conditions, tools) — Phase 2.5
  - Error taxonomy additions — ADR-0003

- **Phase 3 — Production Readiness**
  - Async enforcement via `enforce_invocation_async()` — Phase 3.1
  - Pluggable audit sinks (`JsonFileAuditSink`, `CallbackAuditSink`) — Phase 3.2
  - Structured logging (`aigc` logger namespace, `NullHandler` default) — Phase 3.3
  - `@governed` decorator for sync and async LLM call sites — Phase 3.4
  - ADR-0004 production readiness decisions

---

[0.1.1]: https://github.com/nealsolves/aigc/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nealsolves/aigc/releases/tag/v0.1.0
