# The Three C's of AIGC: Contract, Control, Check

## The Framework

AIGC (Auditable Intelligence Governance Contract) enforces three governance
functions at the AI invocation boundary:

- `Contract`: what the system is allowed to do
- `Control`: how the system enforces those rules
- `Check`: what evidence the system produces

These are not optional features layered on after deployment. Together they form
the minimum governance architecture for a production AI system.

**Contract. Control. Check.**

This document is intentionally evolutionary. Each section starts with the base
capability and then shows how later releases extended it.

---

## 1. Contract: Policy-as-Code

The Contract defines what the AI system is allowed to do. Not as a guideline.
Not as a PDF. As a declarative policy enforced at runtime.

### What Contract governs

- role authorization
- output schema
- preconditions and postconditions
- conditional guards and policy expansion
- policy composition and policy lifecycle boundaries

### How Contract evolved

#### `v0.1.0`: the core contract

The first release established the basic governance contract:

- YAML policy files as the source of truth
- Draft-07 JSON Schema validation at load time
- exhaustive role allowlists
- required preconditions and postconditions
- output schemas as enforceable runtime contracts

This is the foundation of AIGC's design principle: governance is data, not
application code.

#### `v0.2.0`: a stronger, more usable contract

The next major step made the policy layer more expressive and more practical:

- typed preconditions replaced purely string-based checks as the preferred form
- guard expressions moved to an AST-based evaluator
- policy lint and validate commands made the contract easier to check before
  deployment
- `InvocationBuilder` and stricter validation improved how host code assembled
  compliant invocations

At this point, Contract was no longer just declarative; it was easier to
author, validate, and integrate consistently.

#### `v0.3.0`: contract hardening

`v0.3.0` expanded the policy layer into a fuller governance DSL:

- policy composition strategies: `intersect`, `union`, `replace`
- policy effective and expiration dates
- pluggable `PolicyLoader` support for loading policy from sources other than
  the filesystem
- policy testing helpers for evaluating contract behavior before release

This matters because the contract in a real system is not static. It changes by
tenant, by release, by effective date, and by operational source. `v0.3.0`
made those realities explicit without abandoning declarative governance.

#### `v0.3.2`: contract preserved across split execution

`v0.3.2` did not redefine what the Contract is. It changed where enforcement
can happen around the model call.

The key architectural point is that split enforcement preserves the same
effective policy across both phases. Phase B does not reload or reinterpret the
policy from scratch. It continues from the contract resolved in Phase A.

### The engineering principle

The Contract must be externally readable and structurally enforceable. An
auditor should be able to inspect a policy file and understand the declared
boundaries without reverse-engineering application code.

### What this replaces

Governance-by-documentation: AI policies written in prose, reviewed manually,
and never enforced by the running system.

---

## 2. Control: Fail-Closed Enforcement

Control answers the operational question: what happens when the invocation does
not satisfy the Contract?

For AIGC's core governance gates, the answer is fail-closed.

### What Control enforces

- policy load validity
- role authorization
- preconditions
- tool constraints
- output schema validity
- postconditions
- ordered gate execution

### How Control evolved

#### `v0.1.0`: unified fail-closed enforcement

The original release established the core enforcement model:

- one ordered runtime pipeline
- deterministic pass/fail behavior
- immediate stop on governance violations
- no advisory fallback for core gates

Missing preconditions, invalid output schemas, and unauthorized roles did not
generate warnings. They produced enforcement failures.

That baseline is still the heart of AIGC.

#### `v0.2.0`: operational control without weakening enforcement

`v0.2.0` made Control easier to embed safely in real applications:

- instance-scoped `AIGC` configuration reduced dependence on global mutable
  state
- sink failure handling became explicitly configurable with `"log"` and
  `"raise"` modes
- strict mode gave hosts a tighter validation profile
- async enforcement and the decorator made the control boundary easier to apply
  in orchestrators and wrapped call sites

These changes improved operational reliability, but the enforcement model
remained fail-closed for the core governance gates.

#### `v0.3.0`: controlled extensibility

`v0.3.0` introduced two important expansions of Control.

First, it added controlled extensibility:

- custom gates at `pre_authorization`, `post_authorization`, `pre_output`, and
  `post_output`
- read-only views of invocation and policy
- deterministic ordering with append-only failures

Second, it added explicitly scoped non-blocking behavior where the design
permits it:

- risk scoring can run in `strict`, `risk_scored`, or `warn_only` mode
- sink failures can be logged instead of raised when configured with
  `on_sink_failure="log"`

Those are not general escapes from fail-closed governance. They are narrow,
explicitly configured behaviors around risk assessment and artifact
persistence. Core authorization and validation gates remain blocking.

#### `v0.3.2`: split control without reordered gates

`v0.3.2` is the biggest evolution of Control in the current release line.

It adds:

- `enforce_pre_call()` for authorization-side enforcement before token spend
- `enforce_post_call()` for output-side enforcement after the model responds
- `PreCallResult` as the single-use handoff token between phases
- split-mode support in `@governed(pre_call_enforcement=True)`

The critical design constraint is that split mode does not change the relative
order of governance gates. It moves the host model call boundary, not the
governance semantics.

### Inbound and outbound control

Control operates in both directions:

- before the model call, it validates that the invocation is authorized and
  contextually valid
- after the model call, it validates that the output satisfies the policy

In unified mode, those checks run inside one call. In split mode, they run
across two phases while preserving the same effective policy and gate order.

### The engineering principle

Control must be deterministic. Given the same invocation and the same policy,
the system should reach the same governance decision every time.

### What this replaces

Advisory governance: systems that log policy violations but still allow the AI
action to proceed.

---

## 3. Check: Tamper-Evident Audit Trail

Check produces the evidence layer. Every enforcement attempt should leave a
record that can be inspected, persisted, and verified.

### What Check records

- policy identity
- model provider and model identifier
- role
- enforcement result
- failure gate and failure details
- input and output checksums
- timestamp
- invocation context for correlation
- additive metadata about how enforcement ran

### How Check evolved

#### `v0.1.0`: deterministic audit artifacts

The first release established the core artifact model:

- structured audit artifacts generated at enforcement time
- deterministic checksum generation from canonical JSON
- replayable evidence tied to the invocation and policy

This was the first step away from reconstructing AI behavior from scattered
application logs after an incident.

#### `v0.1.1` to `v0.1.3`: better evidence for integration reality

The patch releases strengthened the practical usefulness of audit evidence:

- invocation `context` became part of the artifact for sink correlation
- schema packaging issues were corrected so installed users could validate
  artifacts and policies reliably
- public API guidance reduced accidental reliance on private internals

These are small release notes individually, but they matter because audit
evidence is only useful when it is stable and portable in real deployments.

#### `v0.2.0`: cleaner and safer artifacts

`v0.2.0` improved artifact quality:

- audit schema moved to `v1.2`
- forward-compatible fields for `risk_score` and `signature` were introduced
- exception and audit-message sanitization reduced sensitive-data leakage
- schema bounds were added for failures, metadata, and context fields

This made Check more operationally safe without changing its core role.

#### `v0.3.0`: verifiable tamper evidence

`v0.3.0` turned the audit record into stronger forensic evidence:

- HMAC-SHA256 artifact signing
- optional hash-chained artifact sequences through `AuditChain`
- compliance export for JSONL audit trails
- custom-gate metadata preservation in emitted artifacts

At this point, Check was no longer just a structured log record. It became a
tamper-evident evidence package that could be validated and exported.

#### `v0.3.2`: split-mode evidence and post-release hardening

`v0.3.2` extended the audit schema to `v1.3` and added split-mode evidence:

- `enforcement_mode`
- `pre_call_gates_evaluated`
- `post_call_gates_evaluated`
- `pre_call_timestamp`
- `post_call_timestamp`

It also hardened the integrity model around split tokens and Phase B evidence:

- Phase B reads from verified evidence bytes rather than trusting mutable token
  state
- the Phase B gate manifest is checked against signed evidence
- replay via cloned tokens is blocked
- FAIL artifact identity fields are sourced from verified evidence

This is the most current expression of Check in AIGC: evidence must be
structurally hard to forge, not just convenient to emit.

### PASS and FAIL are both evidence

AIGC treats failed invocations as first-class audit events. An unauthorized
attempt, schema failure, or invalid split token is precisely the kind of event
that compliance and security teams need to inspect later.

If enforcement fails, the typed exception still carries the FAIL artifact at
`exc.audit_artifact`.

### The engineering principle

Audit is mandatory. There is no silent mode that bypasses evidence generation.

### What this replaces

Retroactive compliance: reconstructing what the AI did after the fact from
logs, screenshots, or engineer memory.

---

## The Three C's as Architectural Layers

| Function | Governance Question | Current expression |
| -------- | ------------------- | ------------------ |
| `Contract` | What is allowed? | Declarative policy, schema-validated, versioned, composable |
| `Control` | What happens when rules are broken? | Ordered fail-closed enforcement, deterministic execution, split-capable in `v0.3.2` |
| `Check` | What is the evidence? | Deterministic artifacts, optional signing and chaining, additive split-mode metadata |

The important point is not just that all three exist. It is that they evolved
together:

- Contract became more expressive without becoming arbitrary
- Control became more deployable without becoming advisory
- Check became stronger evidence without becoming optional

Remove Contract and the system has no declared boundary.
Remove Control and the boundary does not enforce.
Remove Check and enforcement cannot be proven.

All three must be present.

---

## Provider Independence

AIGC governs invocations, not model vendors. The Three C's apply the same way
whether the underlying model is from OpenAI, Anthropic, Google, AWS Bedrock, or
an internally hosted model.

That is an architectural requirement:

- Contract should not depend on provider-specific prompt controls
- Control should not depend on provider-specific safety features
- Check should not depend on provider-specific logging formats

Governance belongs to the operating system around the model, not to the model
vendor.

---

## Where the Three C's Sit in the Broader Architecture

The Three C's are the governance lens over the broader AIGC runtime:

- the policy layer expresses the Contract
- the enforcement pipeline expresses the Control
- the audit artifact and reporting path express the Check

They are not separate from the runtime design. They are the conceptual summary
of what the runtime is built to do.
