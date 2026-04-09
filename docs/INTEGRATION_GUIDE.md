# AIGC Integration Guide

How to integrate AIGC governance into any system that invokes AI models.

For a copy-paste quickstart with runnable examples and troubleshooting, see the
[Public Integration Contract](PUBLIC_INTEGRATION_CONTRACT.md).

The SDK enforces policy validation, schema compliance, and audit artifact
generation. This guide covers what the **integrator** is responsible for
beyond what the SDK handles at runtime.

---

## 1. Authority Separation

Models propose outcomes. Systems decide actions.

The SDK enforces this boundary:

- Models have **roles**, not authority. Each invocation declares a role
  (`planner`, `verifier`, `synthesizer`, etc.) and the policy allowlist
  gates it.
- Model outputs are **validated**, not trusted. Schema validation and
  postconditions run after every invocation.
- Audit artifacts record every enforcement decision — PASS and FAIL.

**Your responsibility as the integrator:**

- Never execute state-changing operations directly from model output.
  Validate and transform model proposals in deterministic application code.
- Never let models approve their own actions. Governance checks must run
  outside the model's reasoning path.
- Never suppress governance exceptions. Let them propagate or handle them
  explicitly with structured error responses.

---

## 2. Wrapping Model Invocations

### Direct enforcement

```python
from aigc import enforce_invocation

response = llm.generate(messages)

audit = enforce_invocation({
    "policy_file": "policies/planner.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-5-20250929",
    "role": "planner",
    "input": {"messages": messages},
    "output": response,
    "context": {
        "session_id": session.id,
        "role_declared": True,
        "schema_exists": True,
    },
})
```

### Decorator pattern

```python
from aigc import governed

@governed(
    policy_file="policies/planner.yaml",
    role="planner",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-5-20250929",
)
async def plan_investigation(input_data: dict, context: dict) -> dict:
    return await llm.generate(input_data)
```

### Async enforcement

For async applications (FastAPI, agentic frameworks):

```python
from aigc import enforce_invocation_async

audit = await enforce_invocation_async(invocation)
```

Governance behavior is identical to the sync path. Policy I/O runs off
the event loop via `asyncio.to_thread`.

---

## 3. Governance Integration Points

A governed system typically enforces AIGC at these boundaries:

| Integration Point | What to Govern | Pattern |
| ----------------- | -------------- | ------- |
| Model invocation | Every LLM call | `@governed` decorator or `enforce_invocation()` |
| Tool execution | Tool allowlists, call caps | Pre-invocation enforcement with `tool_calls` field |
| Provider layer | Model/role authorization | Governed wrapper around the provider |
| Compliance pipeline | Domain-specific rules | Postcondition policies with custom schemas |

### Tool governance example

```python
invocation = {
    "policy_file": "policies/tool_governance.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-5-20250929",
    "role": "executor",
    "input": {"tool": tool_name, "params": params},
    "output": {},
    "context": {"session_id": session.id, "role_declared": True, "schema_exists": True},
    "tool_calls": [
        {"name": "search_kb", "call_id": "tc-001"},
        {"name": "search_kb", "call_id": "tc-002"},
    ],
}
audit = enforce_invocation(invocation)
```

The policy's `tools.allowed_tools` and `max_calls` constraints are
enforced automatically.

---

## 4. Policy Design for Your Application

Create role-specific policies that inherit from a shared base:

```text
policies/
├── base.yaml               ← shared preconditions and output schema
├── planner.yaml             ← extends base; planner-specific guards
├── verifier.yaml            ← extends base; stricter postconditions
└── synthesizer.yaml         ← extends base; tool constraints
```

Use `extends` for composition:

```yaml
# policies/planner.yaml
extends: "base.yaml"
policy_version: "v1.0"
roles:
  - planner
pre_conditions:
  required:
    - role_declared
    - schema_exists
    - planning_context_present
```

Merge semantics: arrays append, dicts recurse, scalars replace.
Circular `extends` chains are detected and rejected at load time.

---

## 5. Audit Persistence

The SDK generates audit artifacts. You choose where they go.

### Built-in sinks

```python
from aigc import JsonFileAuditSink, CallbackAuditSink, set_audit_sink

# File sink — append one JSON line per enforcement
set_audit_sink(JsonFileAuditSink("audit.jsonl"))

# Callback sink — bridge to your own persistence
set_audit_sink(CallbackAuditSink(lambda artifact: db.insert(artifact)))
```

### Custom sinks

Subclass `AuditSink` for domain-specific storage (SQLite, DynamoDB,
message queues):

```python
from aigc import AuditSink

class MyDatabaseSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.db.insert("audit_log", artifact)
```

Sink failure behavior is configurable: `"log"` mode (default) logs a `WARNING`; `"raise"` mode propagates as `AuditSinkError`. Sinks receive a deep copy and cannot mutate the caller's artifact.

### Correlation

Include `session_id`, `tenant_id`, or `correlation_id` in the invocation
`context` dict. These fields appear in the audit artifact's `context`
key, enabling cross-session governance reports.

---

## 6. Streaming Considerations

The SDK validates **complete outputs**. If your application uses streaming:

- Accumulate streamed tokens into a complete response before enforcement.
- Do not trigger state mutations from partial tokens.
- Treat streamed output as a presentation concern, not a governance event.
- Run `enforce_invocation()` on the final assembled output.

---

## 7. Model Swap Procedure

When changing models or providers:

1. Update `model_provider` and `model_identifier` in your invocations.
2. Run your test suite — golden replays and governance tests will catch
   any behavioral drift.
3. Verify audit artifacts still pass schema validation.
4. No policy changes are required unless role constraints differ.

AIGC governance is model-independent by design. Provider swaps do not
change enforcement guarantees.

---

## 8. CI Enforcement

Your CI pipeline should include:

- **Schema validation** — validate your policies against
  `schemas/policy_dsl.schema.json`
- **Governance tests** — test PASS and FAIL paths for each role
- **Golden replays** — deterministic regression fixtures for governance
  behavior (see `tests/golden_replays/` and authoring guidance in `CLAUDE.md`)
- **Coverage gate** — enforce minimum coverage on governance-related code

---

## 9. Split Enforcement (v0.3.2+)

### When to use split mode

Unified mode (`enforce_invocation`) validates the entire invocation in one call
after the model has already responded. Split mode is useful when you want to run
authorization gates **before** the model call, so that a policy or role violation
blocks the invocation without spending tokens.

Use split mode when:

- Pre-call authorization cost matters (token spend, rate limits)
- You need to record a phase-A audit timestamp separate from phase-B
- You want a clear boundary between "was the invocation authorized?" and
  "was the output valid?"

Unified mode remains the default and requires no changes for existing integrations.

### Invocation shape for `enforce_pre_call`

The invocation dict is identical to `enforce_invocation` **except that `output`
is omitted** — it is not yet available:

```python
from aigc import enforce_pre_call, enforce_post_call

pre_call_result = enforce_pre_call({
    "policy_file": "policies/planner.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-6",
    "role": "planner",
    "input": {"task": "Summarize Q4 results"},
    "context": {
        "session_id": "sess-42",
        "tenant_id": "acme-corp",
        "role_declared": True,
        "schema_exists": True,
    },
})
```

Phase A runs: policy load → custom gates (pre\_authorization) → guard evaluation →
role check → precondition check → tool constraints → custom gates (post\_authorization).
If any gate fails, a typed exception is raised with a FAIL artifact attached, exactly
as in unified mode.

### `PreCallResult` handoff contract

`enforce_pre_call` returns a `PreCallResult` token. It carries all phase-A state
needed for phase B (loaded policy, resolved guards, gate results, timestamps).
Treat it as an opaque handle — do not inspect or copy its internals.

### Completing enforcement with `enforce_post_call`

After the model responds, pass the token and the output to `enforce_post_call`:

```python
output = llm.generate(task)

artifact = enforce_post_call(pre_call_result, output)
```

Phase B runs: custom gates (pre\_output) → schema validation → postcondition check
→ custom gates (post\_output) → risk scoring → audit artifact generation.
The returned artifact covers the full invocation and is emitted to the configured sink.

**Warning: `PreCallResult` is single-use.** Calling `enforce_post_call` a second
time with the same token raises `InvocationValidationError`. This prevents one
phase-A authorization from being reused across multiple model outputs.

### Decorator pattern

For decorator-based call sites, opt in with `pre_call_enforcement=True`:

```python
from aigc import governed

@governed(
    policy_file="policies/planner.yaml",
    role="planner",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-6",
    pre_call_enforcement=True,
)
async def plan_investigation(input_data: dict, context: dict) -> dict:
    return await llm.generate(input_data)
```

Phase A runs before the function body executes. If phase A fails, the function
is never called. Phase B runs after the function returns. Without
`pre_call_enforcement=True`, `@governed` behaves identically to previous releases.

---

## 10. Provenance Metadata (v0.3.3+)

Starting in `v0.3.3`, audit artifacts carry an optional `provenance` field
that records workflow-level lineage information for a governed invocation.

### Artifact field contract

When `provenance` is supplied to `generate_audit_artifact()`, it appears as a
top-level key in the emitted artifact:

```python
from aigc.audit import generate_audit_artifact

artifact = generate_audit_artifact(
    invocation,
    policy,
    provenance={
        "source_ids": ["workflow-step-1", "workflow-step-2"],
        "derived_from_audit_checksums": [prior_audit["checksum"]],
        "compilation_source_hash": "e3b0c44298fc1c149afbf4c8996fb924"
                                   "27ae41e4649b934ca495991b7852b855",
    },
)
# artifact["provenance"] == {
#     "source_ids": ["workflow-step-1", "workflow-step-2"],
#     "derived_from_audit_checksums": [...],
#     "compilation_source_hash": "e3b0c44...",
# }
```

When omitted: `artifact["provenance"]` is `null`.

### Field semantics

| Field | Type | Meaning |
|-------|------|---------|
| `source_ids` | `string[]` | Caller-defined IDs of prior invocations that contributed to this one |
| `derived_from_audit_checksums` | `string[]` | SHA-256 checksums of prior AIGC audit artifacts (lineage graph edges) |
| `compilation_source_hash` | `string` | Orchestrator-supplied hash of the raw source compilation set |

All fields are optional within the object. Only supply the fields you have.
Supply at least one field — an empty provenance object is invalid.

### What is NOT available yet

`enforce_invocation()`, `enforce_pre_call()`, `enforce_post_call()`, and
`AIGC` enforcement methods do not accept caller-supplied provenance in `v0.3.3`.
Provenance-aware enforcement (via `ProvenanceGate`) is added in PR-05.

---

## 11. Compliance Checklist

An integration is AIGC-compliant when:

- [ ] Every model invocation is wrapped in `enforce_invocation()` or `@governed`
- [ ] Each invocation declares a role from the policy allowlist
- [ ] Output schemas are defined and validated for structured responses
- [ ] Audit artifacts are persisted via a registered sink
- [ ] Governance exceptions propagate (never silently swallowed)
- [ ] CI includes governance regression tests
- [ ] Model outputs never directly mutate system state
- [ ] Policy files are versioned and validated in CI
