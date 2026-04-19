# AIGC Workflow Starter Recipes

Each section below covers one starter profile: how to generate it, what it
contains, how to run it, what output to expect, and the key customization points.

All starters run without external API keys, Bedrock credentials, or A2A setup.

---

## minimal

The `minimal` profile produces the shortest possible governed workflow: two
steps, a straightforward policy, and no external dependencies.

**Generate:**

```bash
aigc workflow init --profile minimal
```

**Generated files:**

- `governance/policy.yaml` — role, preconditions, and output schema
- `governance/workflow_example.py` — two-step governed workflow
- `governance/README.md` — usage notes

**Run:**

```bash
cd governance
python workflow_example.py
```

**Expected output:**

```
Status:  COMPLETED
Steps:   2
Session: <uuid>
```

**Key customization:**

- Add preconditions to `policy.yaml` to require additional context keys.
- Add a second role to `policy.yaml` and update `role=` in the invocation to
  exercise role validation.
- Increase `Steps:` by calling `enforce_step_pre_call` / `enforce_step_post_call`
  additional times inside the `with` block.

---

## standard

The `standard` profile produces a three-step workflow with an approval
checkpoint. The second step pauses the session and waits for a resume signal,
demonstrating the `PAUSED` lifecycle state.

**Generate:**

```bash
aigc workflow init --profile standard
```

**Generated files:**

- `standard-starter/policy.yaml` — role, preconditions, output schema, and
  approval checkpoint configuration
- `standard-starter/workflow_example.py` — three-step workflow with pause/resume
- `standard-starter/README.md` — usage notes

**Run:**

```bash
cd standard-starter
python workflow_example.py
```

**Expected output:**

```
[Step 1] PASS
[Approval] Requesting approval... approved.
[Step 2] PASS (post-approval)
[Step 3] PASS
Status:  COMPLETED
Steps:   3
Session: <uuid>
```

**Key customization:**

- Replace the simulated approval callback in `_request_human_approval()` with a
  real approval mechanism (webhook, Slack message, database record).
- Call `session.cancel()` explicitly in the approval callback when approval is
  denied.
- Add additional pre- and post-approval steps to model a multi-stage review
  workflow.

---

## regulated-high-assurance

The `regulated-high-assurance` profile adds `ProvenanceGate` source-ID
enforcement and a tool budget cap. This profile is designed to demonstrate the
failure-and-fix pattern documented in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Generate:**

```bash
aigc workflow init --profile regulated-high-assurance
```

**Generated files:**

- `regulated-starter/policy.yaml` — provenance gate, tool budget enforcement,
  strict role and precondition rules
- `regulated-starter/workflow_example.py` — two-step workflow requiring
  `context.provenance.source_ids`
- `regulated-starter/README.md` — usage notes including provenance setup

**Run:**

```bash
cd regulated-starter
python workflow_example.py
```

**Expected output (with source_ids present):**

```
Status:  COMPLETED
Steps:   2
Session: <uuid>
```

**Key customization:**

- Adjust `ProvenanceGate(require_source_ids=True)` and the `source_ids` list in
  the context to match your actual document or data identifiers.
- Change `max_calls` in `policy.yaml` under `tools.allowed_tools` to raise or
  lower the tool budget.
- Add additional risk scoring factors to `policy.yaml` under the `risk:` block.

---

## Using `--role` with any starter

All starters accept `--role` to set the role that appears in generated code:

```bash
aigc workflow init --profile minimal --role reviewer
```

The generated `workflow_example.py` will use `role="reviewer"` in its invocation
builder, and `policy.yaml` will include `reviewer` in the `roles` list.
