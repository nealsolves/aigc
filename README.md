# AIGC — Auditable Intelligence Governance Contract

![AIGC Banner](graphics/AIGC_banner.png)

AIGC makes AI invocation governance deterministic, enforceable, and auditable by design.

AIGC enforces deterministic, fail-closed policy evaluation over every model invocation. No silent fallbacks. No advisory-only checks. No prompt-based governance.

Every model call is validated against a declared policy, checked for role authorization, schema compliance, and tool constraints, and produces a tamper-evident audit artifact.

Governance is not documentation. It is runtime enforcement.

---

**SDK Implementation:** Reference implementation of constitutional governance for AI-assisted systems.

**Status:** v0.3.0 — 559 tests, 93% coverage. M2 features: risk scoring, artifact signing (HMAC-SHA256), tamper-evident audit chain, composition semantics, pluggable PolicyLoader, policy dates, OTel integration, policy testing framework, compliance export CLI, custom gate plugins. Audit schema v1.2.

---

## Governance Invariant

> **No AI-influenced behavior is valid unless it is:**
>
> 1. Explicitly specified
> 2. Deterministically enforceable
> 3. Externally observable
> 4. Replayable and auditable
> 5. Governed independently of any specific model or provider

This invariant is not aspirational. Every enforcement path in this SDK is
designed to satisfy all five conditions or fail closed.

## Five Governance Layers

| Layer | Concern | Implementation |
| ----- | ------- | -------------- |
| Behavioral Specification | No implicit behavior | YAML policies validated against JSON Schema (Draft-07) |
| Deterministic Enforcement | Machine-verifiable constraints | `enforce_invocation()` pipeline — fail-closed on any violation |
| Observability | Structured, persistent artifacts | SHA-256 checksummed audit records per invocation |
| Replay & Audit | Replayable execution paths | Golden replays + deterministic artifact generation |
| Model-Independent Governance | Provider-agnostic control | Roles, schemas, and policies — not prompts |

---

## Installation

```bash
pip install aigc-sdk
```

The import name is `aigc`:

```python
from aigc import enforce_invocation
```

**From source** (editable install with dev dependencies):

```bash
python3 -m venv aigc-env
source aigc-env/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install --no-build-isolation -e '.[dev]'
```

**Note:** The `--no-build-isolation` flag is required in network-restricted
environments. It uses the already-installed `setuptools` and `wheel` instead of
trying to download them fresh into an isolated build environment.

If using an internal PyPI mirror or wheelhouse, ensure `pip`, `setuptools`, and
`wheel` are available before running the editable install.

## Public API

Preferred imports:

```python
from aigc import enforce_invocation, AIGC
from aigc.errors import (
    InvocationValidationError,
    PreconditionError,
    SchemaValidationError,
    GovernanceViolationError,
)
```

Instance-scoped enforcement (recommended for new code):

```python
from aigc import AIGC
from aigc.sinks import JsonFileAuditSink

engine = AIGC(sink=JsonFileAuditSink("audit.jsonl"))
audit = engine.enforce(invocation)
```

## Enforced Controls

### Phase 1 (Core Pipeline)

- Invocation shape validation (typed errors, no raw `KeyError`)
- Policy loading with safe YAML + Draft-07 schema validation
- Role allowlist enforcement
- Preconditions + output schema validation
- Postcondition enforcement (`output_schema_valid`)
- Deterministic audit artifact generation with canonical SHA-256 checksums
- FAIL audit artifacts emitted before exception propagation

### Phase 2 (Full DSL)

- **Conditional guards** — `when/then` rules expand effective policy from
  runtime context; evaluated before role validation; effects are additive
- **Named conditions** — boolean flags resolved from invocation context with
  defaults and required enforcement
- **Tool constraints** — per-tool `max_calls` cap and tool allowlist
  enforcement; violations emit FAIL audits
- **Retry policy** — opt-in `with_retry()` wrapper for transient
  `SchemaValidationError` failures with linear backoff
- **Policy composition** — `extends` inheritance with recursive merge
  (arrays append, dicts recurse, scalars replace) and cycle detection

### Phase 3 (Production Readiness)

- **Async enforcement** — `enforce_invocation_async()` runs policy I/O off the
  event loop via `asyncio.to_thread`; identical governance behavior to sync
- **Pluggable audit sinks** — every enforcement emits to the configured
  sink automatically; configurable failure mode (`log` or `raise`).
  Prefer instance-scoped configuration:

  ```python
  from aigc import AIGC
  from aigc.sinks import JsonFileAuditSink
  engine = AIGC(sink=JsonFileAuditSink("audit.jsonl"))
  ```

  The global `set_audit_sink()` function is retained for backward
  compatibility but is not recommended for new code.

- **Instance-scoped enforcement** — `AIGC` class for thread-safe, isolated
  configuration (sink, failure mode, strict mode, redaction patterns)
- **Structured logging** — `aigc.*` logger namespace with `NullHandler` default;
  host applications configure log levels and handlers
- **`@governed` decorator** — wraps sync and async LLM call sites:

  ```python
  from aigc.decorators import governed

  @governed(
      policy_file="policies/governance.yaml",
      role="planner",
      model_provider="anthropic",
      model_identifier="claude-sonnet-4-5-20250929",
  )
  async def plan_investigation(input_data: dict, context: dict) -> dict:
      return await llm.generate(input_data)
  ```

### Milestone 2 (Governance Hardening)

- **Risk scoring engine** — factor-based risk computation with
  `strict`, `risk_scored`, and `warn_only` modes; `RiskThresholdError`
  raised in strict mode when threshold exceeded
- **Artifact signing** — HMAC-SHA256 signing via pluggable
  `ArtifactSigner` interface; constant-time signature verification
- **Tamper-evident audit chain** — hash-chained artifacts with
  `chain_id`, `chain_index`, `previous_audit_checksum` fields
- **Composition restriction semantics** — `intersect`, `union`, and
  `replace` strategies for policy inheritance via `composition_strategy`
- **Pluggable PolicyLoader** — `PolicyLoaderBase` ABC for custom policy
  sources (database, API, vault); `FilePolicyLoader` default
- **Policy version dates** — `effective_date` / `expiration_date`
  enforcement with injectable clock for testing
- **OpenTelemetry integration** — optional spans and gate events; no-op
  when OTel is not installed; governance unaffected by telemetry
- **Policy testing framework** — `PolicyTestCase`, `PolicyTestSuite`,
  `expect_pass()`, `expect_fail()` for policy validation
- **Compliance export CLI** — `aigc compliance export` generates JSON
  compliance reports from JSONL audit trails
- **Custom EnforcementGate plugins** — `EnforcementGate` ABC with four
  insertion points (`pre_authorization`, `post_authorization`,
  `pre_output`, `post_output`) for host-specific gates

## Audit Artifact Contract

Audit artifacts follow `schemas/audit_artifact.schema.json` and include:

- policy identity: `policy_file`, `policy_version`, `policy_schema_version`
- model identity: `model_provider`, `model_identifier`, `role`
- result: `enforcement_result`, structured `failures`
- integrity + auditability: `input_checksum`, `output_checksum`, `timestamp`
- deterministic metadata container: `metadata`

## CI Gates

`.github/workflows/sdk_ci.yml` enforces:

- build-tool bootstrap (`pip`, `setuptools`, `wheel`) and editable install with
  `--no-build-isolation` for restricted-environment parity
- `python -m pytest` with coverage gate (`--cov-fail-under=90`)
- `flake8` for `aigc`
- markdown lint
- policy YAML validation against the Draft-07 policy schema

## Release Checklist

Before tagging a release, confirm all gates pass locally:

```bash
python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90
flake8 aigc
npx markdownlint-cli2 "**/*.md"
python - <<'PY'
import json; from pathlib import Path; import yaml; from jsonschema import Draft7Validator, validate
schema = json.loads(Path("schemas/policy_dsl.schema.json").read_text())
[validate(yaml.safe_load(p.read_text()), schema) or print(f"ok: {p}") for p in Path("policies").glob("*.yaml")]
PY
```

Then tag and push to trigger CI + PyPI publish:

```bash
git tag v<version>
git push origin v<version>
```

## Documentation

| Document | Purpose |
| -------- | ------- |
| [Integration Contract](docs/PUBLIC_INTEGRATION_CONTRACT.md) | Runnable hello-world, end-to-end example, extension points, troubleshooting |
| [PROJECT.md](PROJECT.md) | Authoritative structure and architecture |
| [Architecture Design](docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md) | Enforcement pipeline and design principles |
| [Integration Guide](docs/INTEGRATION_GUIDE.md) | Host system integration patterns and compliance checklist |
| [Policy DSL Spec](policies/policy_dsl_spec.md) | Full policy YAML specification |
| [Usage Guide](docs/USAGE.md) | Code examples and best practices |
