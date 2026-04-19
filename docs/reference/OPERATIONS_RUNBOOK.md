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

## Beta Scope Boundaries

Not in the current beta surface:

- `aigc workflow trace`
- `aigc workflow export`
- `AgentIdentity`
- `AgentCapabilityManifest`
- `ValidatorHook` as a public API
- `BedrockTraceAdapter`
- `A2AAdapter`
- gRPC workflow transport support
