# AIGC Operations Runbook (`v0.9.0` Beta)

This runbook covers the source-only `v0.9.0` beta workflow path on local
`develop`.

## Core Validation Commands

```bash
python -m pytest
flake8 aigc
python scripts/check_doc_parity.py
pytest demo-app-api/tests -q
npm --prefix demo-app-react test
npm --prefix demo-app-react run build
```

## Clean-Environment Beta Proof

Run the stop-ship harness:

```bash
python scripts/validate_v090_beta_proof.py
```

The harness proves:

1. fresh editable install in a new venv
2. minimal starter -> `COMPLETED`
3. standard starter -> `COMPLETED`
4. regulated starter broken in place -> failure
5. `aigc workflow doctor` on that same starter directory -> `WORKFLOW_SOURCE_REQUIRED`
6. same starter fixed in place -> rerun -> `COMPLETED`

The harness does not claim to run `workflow lint` or the entire golden-replay
suite. Those remain separate commands in the core validation set above.

## Demo Validation

The workflow beta lab is backed by:

- `demo-app-api/workflow_routes.py`
- `demo-app-react/src/labs/Lab11WorkflowLab.tsx`

The failure-and-fix tab should:

1. trigger a real broken regulated starter
2. diagnose that same starter directory
3. rerun the same starter after the fix is restored

## Operator Commands — Trace and Export

`aigc workflow trace` and `aigc workflow export` are the two operator inspection
tools for governed workflow evidence. Both consume a JSONL file produced by an
`AuditSink` and produce JSON output.

### When to use `aigc workflow trace`

Use `workflow trace` to reconstruct a session timeline and verify audit sink
completeness after a workflow run. It shows which steps were resolved (invocation
artifact found in the JSONL) and which were not (possible sink failure).

```bash
aigc workflow trace --input audit.jsonl
aigc workflow trace --input audit.jsonl --output timeline.json
```

### When to use `aigc workflow export --mode operator`

Use `operator` mode for a full technical evidence dump — each step embeds the
entire invocation artifact dict. Appropriate for incident reviews, debugging
governance decisions, or cross-referencing enforcement results with raw model
output.

```bash
aigc workflow export --input audit.jsonl --mode operator --output operator_export.json
```

### When to use `aigc workflow export --mode audit`

Use `audit` mode for compliance handoff or external audit. Each step includes
only `step_id`, `participant_id`, `invocation_artifact_checksum`, and
`enforcement_result`. No raw invocation payload is included.

```bash
aigc workflow export --input audit.jsonl --mode audit --output audit_export.json
```

### Interpreting `unresolved_invocation_checksums`

Both commands report `unresolved_invocation_checksums` in the integrity block.
A checksum appears here when a workflow step references an invocation artifact
by SHA-256 that is not present in the JSONL file. This typically indicates one of:

- an audit sink write failure during the session
- a truncated or partial JSONL export
- a JSONL file that covers only some sessions

Run `aigc workflow doctor` on the individual artifact file to diagnose further.
Both commands exit `0` even when checksums are unresolved — the gap is advisory
evidence, not an enforcement failure. The enforcement decision was already made
at the session layer.

## Beta Scope Boundaries

Not in the current beta surface:

- `AgentIdentity`
- `AgentCapabilityManifest`
- `ValidatorHook` as a public API
- `BedrockTraceAdapter`
- `A2AAdapter`
- gRPC workflow transport support
