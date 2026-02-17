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

## Enforced Phase 1 Controls

- Invocation shape validation (typed errors, no raw `KeyError`)
- Policy loading with safe YAML + Draft-07 schema validation
- Role allowlist enforcement
- Preconditions + output schema validation
- Postcondition enforcement (`output_schema_valid`)
- Deterministic audit artifact generation with canonical SHA-256 checksums

## Explicitly Not Implemented Yet (Fail-Closed)

If a policy includes these features, enforcement raises
`FeatureNotImplementedError`:

- `guards`
- `tools`
- `retry_policy`

## Audit Artifact Contract

Audit artifacts follow `schemas/audit_artifact.schema.json` and include:

- policy identity: `policy_file`, `policy_version`, `policy_schema_version`
- model identity: `model_provider`, `model_identifier`, `role`
- result: `enforcement_result`, structured `failures`
- integrity + traceability: `input_checksum`, `output_checksum`, `timestamp`
- deterministic metadata container: `metadata`

## CI Gates

`.github/workflows/sdk_ci.yml` enforces:

- `python -m pytest` with coverage gate (`--cov-fail-under=85`)
- `flake8` for `src` and `aigc`
- markdown lint
- policy YAML validation against the Draft-07 policy schema
