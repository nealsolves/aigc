# AIGC Governance SDK

Python SDK for deterministic governance enforcement over AI model invocations.

## What AIGC Enforces

The SDK is designed to ensure model-assisted behavior is:

1. Explicitly specified
2. Deterministically enforced
3. Observable
4. Replayable and auditable
5. Model/provider independent at the governance layer

## Core Concepts

- `policy`: YAML contract defining allowed roles and conditions
- `invocation`: input payload to be validated and governed
- `audit artifact`: structured output generated after enforcement

## Repository Layout

```text
docs/       Documentation, checklists, and CI guidance
policies/   Policy definitions and DSL spec
schemas/    JSON schemas for policy validation
scripts/    Utilities (for example golden trace generation)
src/        SDK implementation
tests/      Unit tests and golden trace fixtures
```

## Installation

```bash
pip install -e .
```

## Usage

See:

- `docs/USAGE.md`
- `docs/GOLDEN_TRACES_README.md`
- `docs/GOLDEN_TRACES_CI_GUIDE.md`

## CI

The workflow in `.github/workflows/sdk_ci.yml` runs:

- tests
- flake8 lint
- markdown lint
- policy schema validation
