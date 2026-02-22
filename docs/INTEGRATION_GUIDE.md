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
from aigc.enforcement import enforce_invocation

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
from aigc.decorators import governed

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
from aigc.enforcement import enforce_invocation_async

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
from aigc.sinks import JsonFileAuditSink, CallbackAuditSink, set_audit_sink

# File sink — append one JSON line per enforcement
set_audit_sink(JsonFileAuditSink("audit.jsonl"))

# Callback sink — bridge to your own persistence
set_audit_sink(CallbackAuditSink(lambda artifact: db.insert(artifact)))
```

### Custom sinks

Subclass `AuditSink` for domain-specific storage (SQLite, DynamoDB,
message queues):

```python
from aigc.sinks import AuditSink

class MyDatabaseSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.db.insert("audit_log", artifact)
```

Sink failures log a `WARNING` and never block enforcement.

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
  behavior (see [Golden Replays Guide](GOLDEN_REPLAYS_README.md))
- **Coverage gate** — enforce minimum coverage on governance-related code

---

## 9. Compliance Checklist

An integration is AIGC-compliant when:

- [ ] Every model invocation is wrapped in `enforce_invocation()` or `@governed`
- [ ] Each invocation declares a role from the policy allowlist
- [ ] Output schemas are defined and validated for structured responses
- [ ] Audit artifacts are persisted via a registered sink
- [ ] Governance exceptions propagate (never silently swallowed)
- [ ] CI includes governance regression tests
- [ ] Model outputs never directly mutate system state
- [ ] Policy files are versioned and validated in CI
