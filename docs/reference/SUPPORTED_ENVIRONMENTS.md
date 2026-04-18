# AIGC Supported Environments (v0.9.0 Beta)

## Python versions

| Version | Status |
|---------|--------|
| Python 3.10 | Supported |
| Python 3.11 | Supported |
| Python 3.12 | Supported |

Python 3.9 and earlier are not tested and not supported. Python 3.13 is not
yet validated.

## Operating systems

| OS | Status |
|----|--------|
| macOS (Apple Silicon and Intel) | Supported |
| Linux (x86-64) | Supported |
| Windows (x86-64) | Supported |

## Required packages

| Package | Minimum version | Purpose |
|---------|----------------|---------|
| `PyYAML` | `>=6.0` | Policy file parsing |
| `jsonschema` | `>=4.0` | Policy and artifact schema validation |

Both packages are listed in `pyproject.toml`. Normal source installs require
PyPI access (or an internal mirror). Install with:

```bash
pip install -e .
```

## Development extras

Install with the dev extras to also get the test runner and linter:

```bash
pip install -e ".[dev]"
```

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `flake8` | Python linting |

## Restricted-network proof runs

The PR-07 clean-environment proof harness uses a separate maintainer path for
restricted-network environments:

```bash
python scripts/validate_v090_beta_proof.py
```

That harness creates a fresh venv with `system_site_packages=True` and installs
this checkout with `pip install --no-deps --no-build-isolation -e .`, reusing
the current interpreter's installed `setuptools`, `PyYAML`, `jsonschema`, and
their transitive dependencies instead of contacting a package index.

## Not required

The following are explicitly **not required** for the default demo path or for
running any starter:

- External API keys (OpenAI, Anthropic, etc.)
- AWS Bedrock credentials
- A2A (Agent-to-Agent) setup
- `opentelemetry-api` or `opentelemetry-sdk`

`opentelemetry` is an optional integration. When it is not installed, all OTel
instrumentation is a no-op and governance is unaffected.
