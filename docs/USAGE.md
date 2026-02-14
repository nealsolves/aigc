# AIGC Governance SDK Usage Guide

This guide shows how to use the Python SDK to:

- Load policies
- Validate preconditions and output schemas
- Enforce invocation governance
- Generate audit artifacts

## Concepts

- `policy`: Rules for roles and constraints
- `invocation`: Input payload passed to enforcement
- `audit artifact`: Structured record returned after enforcement

## Installation

Install in editable mode during development:

```bash
pip install -e .
```

## Example 1: Simple Enforcement

```python
from src.enforcement import enforce_invocation

invocation = {
    "policy_file": "policies/base_policy.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4.1",
    "role": "planner",
    "input": {"task": "Generate high-level architecture"},
    "output": {"result": "Architecture proposal v1"},
    "context": {
        "role_declared": True,
        "schema_exists": True,
    },
}

audit = enforce_invocation(invocation)
print(audit)
```

## Example 2: Handling Validation Failures

Precondition validation raises `PreconditionError` when required conditions are
missing.

```python
from src.enforcement import enforce_invocation
from src.errors import PreconditionError

try:
    enforce_invocation(
        {
            "policy_file": "policies/base_policy.yaml",
            "model_provider": "openai",
            "model_identifier": "gpt-4.1",
            "role": "planner",
            "input": {},
            "output": {},
            "context": {},
        }
    )
except PreconditionError as err:
    print(f"Precondition failed: {err}")
```

## Example 3: Integrating an External LLM Call

```python
from src.enforcement import enforce_invocation
import openai

task_input = {"task": "Draft API design"}

response = openai.ChatCompletion.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": str(task_input)}],
)

wrapped_output = {
    "result": response["choices"][0]["message"]["content"],
}

invocation = {
    "policy_file": "policies/base_policy.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4.1",
    "role": "planner",
    "input": task_input,
    "output": wrapped_output,
    "context": {
        "role_declared": True,
        "schema_exists": True,
    },
}

audit_record = enforce_invocation(invocation)
print(audit_record)
```

## Example 4: Persisting Audit Artifacts

```python
import json

with open("audit.json", "w", encoding="utf-8") as file_obj:
    json.dump(audit_record, file_obj, indent=2)
```

## Best Practices

- Enforce before writing model outputs to downstream systems
- Keep policy paths explicit and versioned
- Keep `context` complete so required preconditions can be checked
- Persist audit artifacts for replay and compliance workflows
