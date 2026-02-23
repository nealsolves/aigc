# AIGC — Auditable Intelligence Governance Contract

Reference implementation of constitutional governance for AI-assisted systems.

AIGC enforces deterministic, fail-closed policy evaluation over every model
invocation — no silent fallbacks, no advisory-only checks, no prompt-based
governance.

**Status:** Feature-complete — 180 tests, 100% coverage, all three phases shipped.

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
from aigc.enforcement import enforce_invocation
from aigc.errors import (
    InvocationValidationError,
    PreconditionError,
    SchemaValidationError,
    GovernanceViolationError,
)
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
- **Pluggable audit sinks** — register a sink once; every enforcement emits to
  it automatically:

  ```python
  from aigc.sinks import JsonFileAuditSink, set_audit_sink
  set_audit_sink(JsonFileAuditSink("audit.jsonl"))
  ```

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
