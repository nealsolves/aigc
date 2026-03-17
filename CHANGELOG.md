# Changelog

All notable changes to AIGC are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-03-15

### Added

- **Custom gate isolation** — Custom gates receive immutable read-only views
  of policy and invocation data; mutation attempts are caught and converted
  to governance failures (`CUSTOM_GATE_MUTATION`)
- **Custom gate metadata preservation** — Gate metadata from all insertion
  points is merged deterministically into audit artifacts under
  `metadata.custom_gate_metadata`
- **`CustomGateViolationError`** — Explicit error type for custom gate
  failures, replacing heuristic string-matching classification
- **`custom_gate_violation` failure gate** — Audit artifact `failure_gate`
  enum extended with `custom_gate_violation` for accurate forensic
  classification
- **Pluggable PolicyLoader runtime wiring** — `AIGC(policy_loader=...)`
  now routes enforcement through the custom loader; non-filesystem policy
  references supported
- **Pre-pipeline FAIL artifact validity** — Pre-pipeline failure paths
  produce schema-valid artifacts with deterministic placeholder
  `policy_version: "unknown"`
- **Risk scoring engine** — Configurable risk scoring with strict and
  warn-only modes
- **Artifact signing** — HMAC-SHA256 artifact signing via `ArtifactSigner`
- **Tamper-evident audit chain** — `AuditChain` for chained artifact
  verification
- **OpenTelemetry integration** — Enforcement spans and gate events via
  `aigc.telemetry`
- **Policy testing framework** — Programmatic policy testing via
  `aigc.policy_testing`
- **Policy version dates** — `effective_date` / `expiration_date`
  enforcement
- **Composition strategies** — `intersect`, `union`, `replace` for policy
  composition
- **Compliance export CLI** — `aigc compliance export` command

### Changed

- Custom gate failures now raise `CustomGateViolationError` instead of
  generic `GovernanceViolationError` (backward-compatible:
  `CustomGateViolationError` is a subclass)
- Markdown lint scope excludes `.claude/` and `demo-app/` directories

### Fixed

- Custom gates could mutate policy/invocation objects, bypassing governance
  (Critical)
- Pre-pipeline FAIL artifacts had `policy_version: null`, violating schema
  contract (Critical)
- `AIGC(policy_loader=...)` parameter was accepted but not used at runtime
  (High)
- Custom gate metadata was captured but not merged into audit artifacts
  (High)
- Custom gate failures were misclassified as `postcondition_validation`
  (High)

---

## [0.2.0] - 2026-03-06

### Added

- **Instance-scoped enforcement** — `AIGC` class with per-instance sink,
  failure mode, strict mode, and redaction patterns; thread-safe (WS-1)
- **Typed preconditions** — `pre_conditions.required` accepts typed dict format
  with value constraints (`type`, `pattern`, `enum`, `min/max`); bare-string
  format deprecated with `DeprecationWarning` (WS-2, D-01)
- **Exception message sanitization** — API keys, bearer tokens, emails, SSNs
  redacted from FAIL audit artifact messages; custom patterns supported (WS-3, D-05)
- **Policy caching** — `PolicyCache` with LRU eviction keyed by
  `(canonical_path, mtime)`; thread-safe via `threading.Lock` (WS-4, D-03)
- **Sink failure mode configuration** — `set_sink_failure_mode("raise")`
  propagates sink errors as `AuditSinkError`; `"log"` (default) preserves
  backward-compatible behavior (WS-5, D-02)
- **JSON serializability validation** — `input`, `output`, `context` fields
  validated for JSON serializability before enforcement (WS-6, D-14)
- **Audit schema bounds** — `maxItems: 1000` on failures, `maxProperties: 100`
  on metadata and context; truncation with logging (WS-7, D-13)
- **Strict mode** — `AIGC(strict_mode=True)` rejects policies without roles,
  preconditions, or typed preconditions (WS-13)
- **Internal import deprecation** — `from aigc._internal import X` emits
  `DeprecationWarning`; public imports unaffected (WS-14)
- **Audit schema v1.2** — `risk_score` (null) and `signature` (null)
  forward-compatibility placeholders (WS-15)
- **InvocationBuilder** — fluent builder API for constructing invocation
  dicts (WS-16)
- **AST-based guard expressions** — guard conditions compiled to AST; supports
  `and`, `or`, `not`, comparison operators, `in` operator, parenthesized
  expressions (WS-19, D-07)
- **Policy CLI** — `aigc policy lint` and `aigc policy validate` commands;
  `python -m aigc` entry point (WS-20, D-07)

### Changed

- `@governed` decorator uses `inspect.signature()` for robust parameter
  binding (WS-8, D-11)
- Condition resolution logs `INFO` for skipped optional conditions; error
  details include `available_conditions` (WS-9, D-12)
- Guard evaluation uses single-copy optimization instead of per-guard
  `deepcopy` (WS-10, D-15)

### Fixed

- `@governed` decorator handles reordered function parameters correctly

---

## [0.1.3] - 2026-02-23

### Fixed

- Schema files now bundled inside the wheel (`aigc/schemas/`); installed users
  previously got `PolicyLoadError` because schemas only existed at the repo root
- Policy loader resolves schemas from package-internal path first, falling back
  to repo-root for editable/dev installs

---

## [0.1.2] - 2026-02-23

### Fixed

- `@governed` decorator now correctly captures the `input_data` keyword
  argument for both sync and async call sites; previously only the `input`
  keyword and positional arguments were checked, causing governance to audit
  `{}` when callers used the documented `input_data` keyword name

### Added

- API stability note in `docs/USAGE.md`: only symbols exported from the
  top-level `aigc` package are stable public API; `aigc._internal.*` is
  private and may change between releases
- PR template at `.github/pull_request_template.md` for contributor guidance
- Public audit reports tracked in `docs/audits/` and included in markdown lint

### Changed

- **PyPI distribution name: `aigc` → `aigc-sdk`** (`pip install aigc-sdk`);
  import name is unchanged (`import aigc`)
- `docs/PUBLIC_INTEGRATION_CONTRACT.md`: LLM stub in decorator quickstart
  replaced with a self-contained `_StubLLM` class so the example is
  independently runnable without an external `llm` reference
- `.gitignore`: audit reports now tracked in-tree (public artifacts)
- `.markdownlint-cli2.yaml`: `docs/audits/` no longer excluded from lint
- `PROJECT.md`: `CLAUDE.md` removed from public file structure listing

---

## [0.1.1] - 2026-02-17

### Added

- Invocation `context` included in audit artifacts for sink correlation
  (session ID, tenant ID, correlation_id) — ADR-0006
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
  - Golden replay regression testing framework

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

[0.3.0]: https://github.com/nealsolves/aigc/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/nealsolves/aigc/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/nealsolves/aigc/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/nealsolves/aigc/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/nealsolves/aigc/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/nealsolves/aigc/releases/tag/v0.1.0
