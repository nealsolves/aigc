# AIGC Workflow CLI Guide (`v0.9.0` Beta)

`aigc workflow trace` and `aigc workflow export` are not shipped yet. The beta
CLI covers four workflow-adoption commands:

- `aigc policy init`
- `aigc workflow init`
- `aigc workflow lint`
- `aigc workflow doctor`

For `workflow lint` and `workflow doctor`, exit code `0` means no error-severity
findings and exit code `1` means at least one error-severity finding.

---

## `aigc policy init`

```text
aigc policy init --profile {minimal,standard,regulated-high-assurance} [--output OUTPUT] [--role ROLE]
```

Use this to generate a standalone `policy.yaml` from one of the shipped starter
profiles.

Examples:

```bash
aigc policy init --profile minimal
aigc policy init --profile regulated-high-assurance --output policies/regulated.yaml
aigc policy init --profile standard --role reviewer
```

---

## `aigc workflow init`

```text
aigc workflow init --profile {minimal,standard,regulated-high-assurance} [--output-dir OUTPUT_DIR] [--role ROLE]
```

Generates a starter directory containing `policy.yaml`, `workflow_example.py`,
and `README.md`.

Examples:

```bash
aigc workflow init --profile minimal
aigc workflow init --profile standard --output-dir governance-standard
aigc workflow init --profile regulated-high-assurance --role analyst
```

---

## `aigc workflow lint`

```text
aigc workflow lint [--kind {auto,policy,starter_dir,workflow_artifact}] [--json] targets [targets ...]
```

Static lint for governance targets. In the beta it covers:

- policy schema and YAML validity
- starter integrity
- public-import safety
- impossible workflow budgets
- invalid transition references
- unsupported protocol/binding references

Examples:

```bash
aigc workflow lint policy.yaml
aigc workflow lint governance/
aigc workflow lint --kind workflow_artifact workflow_artifact.json
aigc workflow lint --json governance/
```

---

## `aigc workflow doctor`

```text
aigc workflow doctor [--kind {auto,policy,starter_dir,workflow_artifact,audit_artifact}] [--json] target
```

Runtime and evidence diagnosis for policy files, starter directories, workflow
artifacts, and invocation audit artifacts.

Examples:

```bash
aigc workflow doctor governance/
aigc workflow doctor workflow_artifact.json
aigc workflow doctor audit.json --kind audit_artifact --json
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for reason-code guidance and the
regulated failure-and-fix walkthrough.
