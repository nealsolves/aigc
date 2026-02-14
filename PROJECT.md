# Project Structure

```text
aigc-governance-sdk/
|-- .github/workflows/sdk_ci.yml
|-- docs/
|   |-- GOLDEN_TRACES_CI_GUIDE.md
|   |-- GOLDEN_TRACES_README.md
|   |-- GOLDEN_TRACE_CHECKLIST.md
|   `-- USAGE.md
|-- policies/
|   |-- base_policy.yaml
|   `-- policy_dsl_spec.md
|-- schemas/
|   |-- invocation_policy.schema.json
|   `-- policy_dsl.schema.json
|-- scripts/
|   `-- generate_golden_traces.py
|-- src/
|   |-- audit.py
|   |-- enforcement.py
|   |-- errors.py
|   |-- policy_loader.py
|   `-- validator.py
|-- tests/
|   |-- golden_traces/
|   |   |-- golden_expected_audit.json
|   |   |-- golden_invocation_failure.json
|   |   |-- golden_invocation_success.json
|   |   |-- golden_policy_v1.yaml
|   |   `-- golden_schema.json
|   |-- test_audit_artifact_contract.py
|   |-- test_golden_trace_failure.py
|   |-- test_golden_trace_success.py
|   `-- test_validation.py
|-- LICENSE
|-- README.md
`-- requirements.txt
```
