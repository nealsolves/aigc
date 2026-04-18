# AIGC Operations Runbook (v0.9.0 Beta)

This runbook covers common operational tasks for the v0.9.0-beta line.

## Running the test suite

Run all tests from the repository root:

```bash
python -m pytest
```

Run a specific test file:

```bash
python -m pytest tests/test_golden_replay_success.py
```

Run a specific test case:

```bash
python -m pytest tests/test_golden_replay_success.py::test_golden_success_produces_audit
```

Run with coverage:

```bash
python -m pytest --cov=aigc --cov-report=term-missing
```

Lint the Python source:

```bash
flake8 aigc
```

Validate all policy files against the JSON Schema:

```bash
python -c "
import json, yaml, jsonschema
from pathlib import Path
schema = json.load(open('schemas/policy_dsl.schema.json'))
for p in Path('policies').glob('*.yaml'):
    jsonschema.validate(yaml.safe_load(open(p)), schema)
    print(f'OK: {p}')
"
```

## Running the demo

The demo follows the quickstart flow documented in
[WORKFLOW_QUICKSTART.md](WORKFLOW_QUICKSTART.md). The default demo path requires
no external API keys or credentials:

```bash
aigc workflow init --profile minimal
cd governance
python workflow_example.py
```

Expected terminal output:

```
Status:  COMPLETED
Steps:   2
Session: <uuid>
```

For the failure-and-fix demo flow, use the regulated profile and follow the
steps in [TROUBLESHOOTING.md](TROUBLESHOOTING.md#the-failure-and-fix-flow-regulated-profile).

## Clean-environment validation

To validate that the v0.9.0-beta installation is fully working in a clean
environment, run the beta proof script:

```bash
python scripts/validate_v090_beta_proof.py
```

This script exercises:

1. Clean install from source (no cached state)
2. The minimal starter generation and run
3. The regulated profile failure-and-fix flow
4. The `aigc workflow lint` and `aigc workflow doctor` commands
5. All golden-replay tests

The script exits 0 if all checks pass and 1 if any check fails. Run this
before declaring the beta green.

## What is NOT in v0.9.0-beta scope

The following features are planned for later releases and are **not available**
in v0.9.0-beta:

- `aigc workflow trace` — workflow step trace visualization
- `aigc workflow export` — audit export in operator and compliance formats
- `BedrockTraceAdapter` — Bedrock trace normalization and alias-backed identity
- `A2AAdapter` — Agent-to-Agent task envelope validation
- `ValidatorHook` — custom postcondition validation plug-in
- `register_validator` and `register_resolver` extension points
- gRPC protocol binding support (explicitly out of scope)

Do not attempt to import or invoke these surfaces in v0.9.0-beta. They are
documented in [docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md](../architecture/AIGC_HIGH_LEVEL_DESIGN.md)
as planned-only additions.
