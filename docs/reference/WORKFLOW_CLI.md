# AIGC Workflow CLI Guide (`v0.9.0` Beta)

The beta CLI covers six workflow-adoption commands:

- `aigc policy init`
- `aigc workflow init`
- `aigc workflow lint`
- `aigc workflow doctor`
- `aigc workflow trace`
- `aigc workflow export`

For `workflow lint` and `workflow doctor`, exit code `0` means no error-severity
findings and exit code `1` means at least one error-severity finding.

For `workflow trace` and `workflow export`, exit code `0` means success even
when checksums are unresolved (unresolved checksums are advisory, not errors);
exit code `1` means the input file was not found, was unreadable, or contained
no workflow artifacts.

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

---

## `aigc workflow trace`

```text
aigc workflow trace --input FILE [--output FILE]
```

Reconstruct workflow timelines from a JSONL artifact file containing workflow
and invocation artifacts. Outputs a JSON array — one trace object per workflow
session found in the input.

Arguments:

- `--input` — JSONL file containing workflow and invocation artifacts (required)
- `--output` — Write JSON output to this file instead of stdout (optional)

Exit codes:

- `0` — Success (unresolved checksums are advisory — exit 0 even when gaps exist)
- `1` — File not found, unreadable, or contains no workflow artifacts

Output fields per trace object:

| Field | Description |
|-------|-------------|
| `trace_schema_version` | `"0.9.0"` |
| `session_id` | Session identifier from the workflow artifact |
| `status` | `COMPLETED`, `FAILED`, `CANCELED`, or `INCOMPLETE` |
| `step_count` | Number of steps in the workflow |
| `steps[]` | Per-step timeline with resolved/unresolved status |
| `unresolved_checksums` | Checksums that could not be matched to invocation artifacts |
| `failure_summary` | Failure context recorded at session finalization, or `null` |

Each step in `steps[]` includes:

| Field | Description |
|-------|-------------|
| `sequence` | 1-based step position |
| `step_id` | Step identifier |
| `participant_id` | Agent or participant identifier, or `null` |
| `invocation_artifact_checksum` | SHA-256 checksum of the correlated invocation artifact |
| `resolved` | `true` if the invocation artifact was found in the input |
| `invocation_summary` | Key fields from the invocation artifact, or `null` if unresolved |

`unresolved_checksums` indicates sink failures or an incomplete export — the
invocation artifacts referenced by those steps were not present in the JSONL
file. Investigate with `aigc workflow doctor`.

Examples:

```bash
aigc workflow trace --input audit.jsonl
aigc workflow trace --input audit.jsonl --output timeline.json
```

---

## `aigc workflow export`

```text
aigc workflow export --input FILE --mode {operator|audit} [--output FILE]
```

Export governed workflow evidence in operator or audit mode.

Arguments:

- `--input` — JSONL file containing workflow and invocation artifacts (required)
- `--mode` — `operator` for a full technical dump; `audit` for compliance-focused step summaries (required)
- `--output` — Write JSON output to this file instead of stdout (optional)

Exit codes:

- `0` — Success (unresolved checksums are advisory — exit 0 even when gaps exist)
- `1` — File not found, unreadable, or contains no workflow artifacts

Modes:

**`operator`** — Embeds the full invocation artifact dict in each step under
`invocation_artifact`. Use for debugging, audit trail reconstruction, or
operator inspection. Output shape:

```json
{
  "export_schema_version": "0.9.0",
  "export_mode": "operator",
  "generated_at": 1700000000,
  "sessions": [{ "steps": [{ "invocation_artifact": { ... } }] }],
  "integrity": {
    "total_workflow_artifacts": 1,
    "total_invocation_artifacts": 1,
    "unresolved_invocation_checksums": [],
    "unresolved_count": 0,
    "verification_guidance": "..."
  }
}
```

**`audit`** — Includes only `step_id`, `enforcement_result`, and checksum per
step. Use for compliance reporting and external audit handoff. Output shape:

```json
{
  "export_schema_version": "0.9.0",
  "export_mode": "audit",
  "generated_at": 1700000000,
  "sessions": [{ "steps": [{ "enforcement_result": "PASS" }] }],
  "compliance_summary": {
    "total_sessions": 1,
    "COMPLETED": 1, "FAILED": 0, "CANCELED": 0, "INCOMPLETE": 0
  },
  "integrity": {
    "unresolved_invocation_checksums": [],
    "unresolved_count": 0,
    "verification_guidance": "..."
  }
}
```

`integrity.unresolved_invocation_checksums` lists any invocation artifacts
referenced by workflow steps that were not found in the input JSONL. Investigate
missing evidence with `aigc workflow doctor`.

Examples:

```bash
aigc workflow export --input audit.jsonl --mode operator
aigc workflow export --input audit.jsonl --mode audit --output compliance.json
```
