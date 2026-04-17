# AIGC Workflow Governance — Quickstart (v0.9.0 Beta)

> This is a beta surface. Install from source; it is not yet on PyPI.

## Prerequisites

- Python 3.10 or later
- AIGC installed in editable mode from the `feat/v0.9-07-beta-proof` branch:

```bash
git clone https://github.com/nealsolves/aigc
cd aigc
git checkout feat/v0.9-07-beta-proof
pip install --no-build-isolation -e ".[dev]"
```

No external API keys, Bedrock credentials, or A2A setup are required. The
minimal starter runs entirely locally.

## Step 1 — Generate a minimal starter

```bash
aigc workflow init --profile minimal
```

This creates a `governance/` directory containing:

- `policy.yaml` — a governance policy with role, preconditions, and output schema
- `workflow_example.py` — a two-step governed workflow you can run immediately
- `README.md` — usage notes for the generated starter

## Step 2 — Run the starter

```bash
cd governance
python workflow_example.py
```

Expected output:

```
Status:  COMPLETED
Steps:   2
Session: <uuid>
```

## What just happened

The starter script exercised the full workflow governance lifecycle in six actions:

1. **`AIGC.open_session`** — Creates a `GovernanceSession` instance bound to the
   policy file. All subsequent invocations in the workflow run through this
   session. There is no module-level `open_session()`; this is always called on
   an `AIGC` instance.

2. **`enforce_step_pre_call`** (Step 1) — Runs the pre-call side of governance for
   the first step: loads the policy, evaluates guards, validates role and
   preconditions, and checks tool constraints. Returns a `SessionPreCallResult`
   token that is single-use and must be completed through the owning session.

3. **`enforce_step_post_call`** (Step 1) — Runs the post-call side of governance:
   validates the output schema, evaluates postconditions, scores risk, and
   emits a signed invocation audit artifact correlated to this session.

4. **`enforce_step_pre_call`** (Step 2) — Same pre-call flow for the second step,
   with replay protection. Each step gets its own `SessionPreCallResult`.

5. **`enforce_step_post_call`** (Step 2) — Post-call governance for the second step.

6. **`session.complete()`** — Marks the workflow as successfully finished.
   Transitions the session to `COMPLETED` and emits the workflow artifact.

After the `with` block exits, `session.workflow_artifact` holds the completed
workflow record with `status: COMPLETED`, a step checksum list, and the session
UUID that correlates all invocation artifacts.

## Next steps

- **Run a different profile:** Try `aigc workflow init --profile standard` for a
  three-step workflow with an approval checkpoint (pause/resume). See
  [STARTER_INDEX.md](STARTER_INDEX.md) for all profiles.

- **Diagnose issues:** If your workflow raises an error, run
  `aigc workflow doctor <starter-dir>/` for structured advice. See
  [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for all reason codes.

- **CLI reference:** See [WORKFLOW_CLI.md](WORKFLOW_CLI.md) for full command
  documentation.

- **Migrating existing code:** See [../migration.md](../migration.md) for the
  minimal diff to add workflow governance to an invocation-only integration.
