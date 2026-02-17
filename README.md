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
