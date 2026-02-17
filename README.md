# AIGC Governance SDK

Python SDK for deterministic, fail-closed governance enforcement over AI model
invocations.

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

Legacy `src.*` imports remain available for compatibility.

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
      policy_file="policies/trace_planner.yaml",
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
- integrity + traceability: `input_checksum`, `output_checksum`, `timestamp`
- deterministic metadata container: `metadata`

## CI Gates

`.github/workflows/sdk_ci.yml` enforces:

- `python -m pytest` with coverage gate (`--cov-fail-under=90`)
- `flake8` for `src` and `aigc`
- markdown lint
- policy YAML validation against the Draft-07 policy schema
