# Contributing to AIGC

Thank you for your interest in contributing to AIGC.

## Development Setup

```bash
python3 -m venv aigc-env
source aigc-env/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install --no-build-isolation -e '.[dev]'
```

## Running Tests

```bash
python -m pytest
```

CI enforces a 90% coverage gate:

```bash
python -m pytest --cov=aigc --cov-fail-under=90
```

## Linting

```bash
flake8 aigc
npx markdownlint-cli2 "**/*.md"
```

## Policy Schema Validation

```bash
python - <<'PY'
import json
from pathlib import Path
import jsonschema
import yaml

schema = json.load(open("schemas/policy_dsl.schema.json"))
for policy_file in Path("policies").glob("*.yaml"):
    policy = yaml.safe_load(open(policy_file))
    jsonschema.validate(policy, schema)
PY
```

## Pull Requests

All PRs must follow `.github/pull_request_template.md`.

Before submitting:

1. All tests pass (`python -m pytest`)
2. Linters pass (`flake8 aigc` and `npx markdownlint-cli2 "**/*.md"`)
3. Golden replays updated if governance behavior changed
4. Documentation updated if architecture changed

## Governance Hard Gates

- All enforcement flows through `enforce_invocation()`
- Policy validation fails closed — no "best-effort" governance
- Determinism preserved — identical inputs produce identical audit artifacts
- Typed error taxonomy preserved — no collapsing into generic errors

## Architecture Decision Records

When changing enforcement order, policy semantics, determinism rules,
error taxonomy, or structural architecture, add an ADR in `docs/decisions/`.

Use the template in `.github/pull_request_template.md`.

## Code of Conduct

Be respectful. Focus on the work.

## License

By contributing, you agree that your contributions will be licensed under
the MIT License.
