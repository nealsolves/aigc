# AIGC SDK v0.3.0 — Release Package

AI Governance Client — deterministic enforcement of AI model invocations through
policy validation, audit artifact generation, and fail-closed governance.

## Contents

| Directory / File | Purpose |
|---|---|
| `dist/` | Installable wheel and source distribution |
| `demo/` | Interactive Streamlit demo app (7 hands-on labs) |
| `docs/` | Integration guides and public API contract |
| `policies/` | Reference policy YAML files and DSL spec |
| `schemas/` | JSON Schema definitions for policies and invocations |
| `CHANGELOG.md` | Release notes and version history |
| `SECURITY.md` | Security policy and vulnerability reporting |

## Install

```bash
pip install dist/aigc_sdk-0.3.0-py3-none-any.whl
```

Or from PyPI:

```bash
pip install aigc-sdk==0.3.0
```

## Quickstart

```python
from aigc import enforce_invocation

audit = enforce_invocation({
    "policy_file": "policies/base_policy.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-6",
    "role": "synthesizer",
    "input": {"prompt": "Summarize this document."},
    "output": {"result": "Here is a summary."},
    "context": {}
})

print(audit["enforcement_result"])  # "PASS" or "FAIL"
```

## Demo App

The `demo/` directory contains an interactive Streamlit app covering all major
v0.3.0 capabilities across 7 labs:

- **Lab 1** — Risk scoring
- **Lab 2** — Artifact signing and verification
- **Lab 3** — Tamper-evident audit chain
- **Lab 4** — Policy composition
- **Lab 5** — Custom policy loaders and version dates
- **Lab 6** — Custom enforcement gates
- **Lab 7** — Compliance export

Run it:

```bash
cd demo
pip install streamlit aigc-sdk==0.3.0
streamlit run app.py
```

## Integration Docs

| Document | What it covers |
|---|---|
| `docs/USAGE.md` | Core concepts, API reference, common patterns |
| `docs/INTEGRATION_GUIDE.md` | Wrapping model calls, authority separation, error handling |
| `docs/PUBLIC_INTEGRATION_CONTRACT.md` | Stable API contract with runnable examples |

## What's New in v0.3.0

See [CHANGELOG.md](CHANGELOG.md) for the full list. Highlights:

- Risk scoring engine with `strict`, `risk_scored`, and `warn_only` modes
- HMAC-SHA256 artifact signing via `ArtifactSigner`
- Tamper-evident `AuditChain`
- Custom gate isolation (immutable read-only views, mutation caught as governance failure)
- Pluggable `PolicyLoader` runtime wiring
- OpenTelemetry integration
- Policy testing framework (`aigc.policy_testing`)
- Policy version dates (`effective_date` / `expiration_date`)
- Compliance export CLI (`aigc compliance export`)

## Source

Repository: [github.com/nealsolves/aigc](https://github.com/nealsolves/aigc)
