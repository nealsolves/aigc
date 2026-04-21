# AIGC Public Integration Contract

This document is the primary onboarding reference for integrating AIGC into your system.
It contains a minimal hello-world example, a realistic production integration, the available
extension points, and a troubleshooting/FAQ section.

It describes the current public runtime surface for the shipped `v0.3.3`
package and CLI plus the source-only `v0.9.0` beta workflow surface that lives
on local `develop`. The target-state `1.0.0` architecture contract, including
later adapters and exports, is captured separately in
[docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md](architecture/AIGC_HIGH_LEVEL_DESIGN.md).

The following surfaces are available in the source-only `v0.9.0` beta line and
are not part of the installable `v0.3.3` artifact: `AIGC.open_session(...)`,
`GovernanceSession`, and `SessionPreCallResult`. This is beta, not yet stable.
There is no module-level `open_session()` convenience — workflow adoption is
always instance-scoped through `AIGC.open_session(...)`.

See [docs/reference/WORKFLOW_QUICKSTART.md](reference/WORKFLOW_QUICKSTART.md)
for the fastest path to a working workflow with these surfaces.

Also available in the source-only `v0.9.0` beta line: `aigc workflow init`,
`aigc policy init`, `aigc workflow lint`, `aigc workflow doctor`,
`aigc.presets.MinimalPreset`, `aigc.presets.StandardPreset`,
`aigc.presets.RegulatedHighAssurancePreset`, `WorkflowStarterIntegrityError`,
and `docs/migration.md` (migration guide from invocation-only to workflow
governance). This is beta, not yet stable.

The following surfaces remain planned-only beyond `v0.9.0` beta and are not
part of the `v0.3.3` artifact or the current beta public surface:
`AgentIdentity`, `AgentCapabilityManifest`, `ValidatorHook`,
`BedrockTraceAdapter`, and `A2AAdapter`. Do not build integrations against
those names until they ship through the public package exports, instance API,
CLI surface, and contract tests.

`aigc workflow trace` and `aigc workflow export` shipped in PR-09 and are part
of the current beta CLI surface.

All public examples, starter packs, presets, demo code, and docs snippets
must use public `aigc` imports only and must not depend on `aigc._internal`.

---

## 1. Hello AIGC — Minimal Runnable Example

Install and run governance enforcement in under five minutes.

### 1.1 Install

```bash
pip install aigc-sdk
```

Or from source (editable, with dev dependencies):

```bash
git clone https://github.com/nealsolves/aigc
cd aigc
python -m pip install --upgrade pip setuptools wheel
pip install --no-build-isolation -e '.[dev]'
```

### 1.2 Write a policy

Create `policies/hello_policy.yaml`:

```yaml
policy_version: "1.0"
roles:
  - assistant
pre_conditions:
  required:
    - user_id
output_schema:
  type: object
  required:
    - reply
  properties:
    reply:
      type: string
```

### 1.3 Call `enforce_invocation`

```python
from aigc import enforce_invocation, GovernanceViolationError, PreconditionError

invocation = {
    "policy_file": "policies/hello_policy.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4o",
    "role": "assistant",
    "input": {"prompt": "Hello!"},
    "output": {"reply": "Hello, I am your assistant."},
    "context": {"user_id": "user-001"},
}

artifact = enforce_invocation(invocation)
print(artifact["enforcement_result"])  # PASS
```

The call returns an audit artifact on success and raises a typed exception on any governance
violation. No silent fallbacks. No best-effort checks.

---

## 2. Production Integration

This section builds a single, realistic integration from the ground up: a governed analytics
service that uses the full pre-split governance stack (M2 plus production runtime features).
The additive v0.3.2 split-enforcement APIs are covered separately in Section 3.15. Each
subsection extends the same example rather than introducing a separate one.

### 2.1 Policy with guards, tool constraints, and risk scoring

Create `policies/analyst_policy.yaml`:

```yaml
policy_version: "1.0"
effective_date: "2025-01-01"
expiration_date: "2027-12-31"
roles:
  - analyst
conditions:
  is_enterprise:
    type: boolean
    default: false
pre_conditions:
  required:
    tenant_id:
      type: string
    session_id:
      type: string
output_schema:
  type: object
  required:
    - analysis
  properties:
    analysis:
      type: string
post_conditions:
  required:
    - output_schema_valid
guards:
  - when:
      condition: "is_enterprise"
    then:
      tools:
        allowed_tools:
          - name: internal_search
            max_calls: 10
risk:
  mode: strict
  threshold: 0.7
  factors:
    - name: no_schema
      weight: 0.4
      condition: no_output_schema
    - name: external_provider
      weight: 0.3
      condition: external_model
    - name: broad_access
      weight: 0.3
      condition: broad_roles
```

This policy declares:

- **Typed preconditions**: `tenant_id` and `session_id` must be present strings in context.
- **Output schema**: Model output must contain an `analysis` string.
- **Guards**: When `is_enterprise` is true in context, tool constraints activate, allowing
  `internal_search` with a cap of 10 calls.
- **Risk scoring**: Strict mode with a 0.7 threshold. Three weighted factors evaluate whether
  the policy itself is well-formed (has a schema, uses a narrow role set, runs an internal
  model). If the composite score exceeds 0.7, enforcement fails with `RiskThresholdError`.
- **Policy dates**: Active from 2025-01-01 through 2027-12-31. Loading the policy outside this
  window raises `PolicyValidationError`.

### 2.2 Custom enforcement gate

Custom gates inject governance logic at defined insertion points in the pipeline without
modifying the core enforcement code. This gate enforces tenant isolation:

```python
from aigc import EnforcementGate, GateResult, INSERTION_PRE_AUTHORIZATION


class TenantIsolationGate(EnforcementGate):
    """Verify tenant_id is present before any authorization gate runs."""

    @property
    def name(self) -> str:
        return "tenant_isolation"

    @property
    def insertion_point(self) -> str:
        return INSERTION_PRE_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        tenant_id = invocation.get("context", {}).get("tenant_id")
        if not tenant_id:
            return GateResult(
                passed=False,
                failures=[{
                    "code": "MISSING_TENANT",
                    "message": "tenant_id is required for all invocations",
                    "field": "context.tenant_id",
                }],
            )
        return GateResult(passed=True, metadata={"verified_tenant": tenant_id})
```

The gate runs at `pre_authorization`, before role validation and precondition checks. It
receives read-only views of `invocation` and `policy`. If it fails, the pipeline stops and a
FAIL artifact is generated with the gate's failure details. The gate's `metadata` dict is
merged into the audit artifact's `metadata` on PASS.

Custom gates appear as `"custom:tenant_isolation"` in the artifact's `metadata.gates_evaluated`
list. Gate metadata is merged into `metadata.custom_gate_metadata`. If a gate raises an
unhandled exception, the pipeline converts it to a failure with code `CUSTOM_GATE_ERROR` —
governance never crashes.

### 2.3 Application startup

Wire everything together once at startup. The `AIGC` class is the production entry point —
it owns its sink, signer, gates, and policy cache with no global mutable state:

```python
from aigc import AIGC, HMACSigner, AuditChain, JsonFileAuditSink

signer = HMACSigner(key=b"your-256-bit-secret-key-here-!!!")
chain = AuditChain(chain_id="analytics-session-001")

aigc = AIGC(
    sink=JsonFileAuditSink("audit/governance.jsonl"),
    on_sink_failure="log",
    signer=signer,
    custom_gates=[TenantIsolationGate()],
)
```

Configuration is immutable after construction. `AIGC.enforce()` is thread-safe.

- **`sink`**: Every enforcement call (PASS and FAIL) emits an artifact as a JSON line.
- **`signer`**: HMAC-SHA256 signs every artifact automatically — both PASS and FAIL.
- **`custom_gates`**: Validated at construction time. Invalid insertion points raise immediately.
- **`on_sink_failure`**: `"log"` (default) logs a warning on sink errors; `"raise"` propagates
  them as `AuditSinkError`. Sink errors never replace governance exceptions.

### 2.4 Building and enforcing invocations

Use `InvocationBuilder` for a fluent, validated construction:

```python
from aigc import InvocationBuilder

invocation = (
    InvocationBuilder()
    .policy("policies/analyst_policy.yaml")
    .model("anthropic", "claude-sonnet-4-6")
    .role("analyst")
    .input({"question": "Summarize Q4 results"})
    .output({"analysis": "Revenue increased 12% QoQ."})
    .context({
        "tenant_id": "acme-corp",
        "session_id": "sess-42",
        "is_enterprise": True,
    })
    .build()
)

artifact = aigc.enforce(invocation)
```

`build()` validates that all required fields are present and raises `InvocationValidationError`
if any are missing. The returned dict is independent — calling `build()` again produces a
new object.

On PASS, `artifact` is a signed audit artifact dict. On failure, a typed exception propagates
with the FAIL artifact attached at `exc.audit_artifact`.

### 2.5 Audit chain for artifact integrity

Append each enforcement artifact to the chain for tamper-evident sequencing:

```python
chain.append(artifact)
print(chain.length)  # 1
```

Each `append()` adds three fields to the artifact:

- `chain_id`: links the artifact to this chain
- `chain_index`: 0-based position in the chain
- `previous_audit_checksum`: SHA-256 of the prior artifact (null for the first)

After a session, verify the full chain:

```python
valid, errors = chain.verify()
assert valid, f"Chain integrity broken: {errors}"
```

To verify a chain loaded from storage (e.g., from the audit sink's JSONL file):

```python
import json
from aigc import verify_chain

with open("audit/governance.jsonl") as f:
    artifacts = [json.loads(line) for line in f]

valid, errors = verify_chain(artifacts)
```

### 2.6 Decorator pattern

For simpler call sites that don't need instance-scoped configuration, the `@governed`
decorator wraps a function and runs enforcement transparently:

```python
from aigc import governed, set_audit_sink, JsonFileAuditSink

set_audit_sink(JsonFileAuditSink("audit/governance.jsonl"))


@governed(
    policy_file="policies/analyst_policy.yaml",
    role="analyst",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-6",
)
async def analyze(input_data: dict, context: dict) -> dict:
    result = await llm.generate(input_data, context)
    return {"analysis": result}


output = await analyze(
    {"question": "Summarize Q4 results"},
    {"tenant_id": "acme-corp", "session_id": "sess-42", "is_enterprise": True},
)
```

The decorator captures `input_data` as input, `context` as context, and runs split
enforcement by default (since v0.3.3): Phase A (`enforce_pre_call_async()`) runs before
the wrapped function; Phase B (`enforce_post_call_async()`) validates the return value.
Pass `pre_call_enforcement=False` for legacy unified mode (deprecated).
Governance exceptions propagate unchanged.

The decorator uses the global audit sink (via `set_audit_sink`). For per-instance sinks,
signers, or custom gates, use the `AIGC` class directly as shown in sections 2.3–2.5.

### 2.7 Error handling

Every governance failure raises a typed exception with a FAIL artifact attached:

```python
from aigc import (
    AIGCError,
    GovernanceViolationError,
    PreconditionError,
    SchemaValidationError,
    ToolConstraintViolationError,
    RiskThresholdError,
    CustomGateViolationError,
)

try:
    artifact = aigc.enforce(invocation)
    chain.append(artifact)
except RiskThresholdError as exc:
    # Risk score exceeded threshold in strict mode
    print(f"Risk: {exc.details['score']:.3f} > {exc.details['threshold']:.3f}")
    chain.append(exc.audit_artifact)
except CustomGateViolationError as exc:
    # A custom gate failed (e.g., tenant isolation)
    print(f"Gate failure: {exc}")
    chain.append(exc.audit_artifact)
except ToolConstraintViolationError as exc:
    # Tool not in allowed list or max_calls exceeded
    chain.append(exc.audit_artifact)
except PreconditionError as exc:
    # Required context key missing or wrong type
    chain.append(exc.audit_artifact)
except SchemaValidationError as exc:
    # Model output doesn't match policy output_schema
    chain.append(exc.audit_artifact)
except GovernanceViolationError as exc:
    # Role not in policy, or other governance violation
    chain.append(exc.audit_artifact)
except AIGCError as exc:
    # Catch-all for any governance error
    chain.append(exc.audit_artifact)
```

Every exception carries `exc.audit_artifact` (a complete, signed FAIL artifact),
`exc.code` (machine-readable error code), and `exc.details` (structured metadata).
FAIL artifacts are emitted to the sink before the exception propagates.

### 2.8 Testing your policies

Use the policy testing framework to validate policies in isolation, without a running LLM:

```python
from aigc import PolicyTestCase, PolicyTestSuite, expect_pass, expect_fail

# Quick single-case assertions
expect_pass(PolicyTestCase(
    name="valid analyst call",
    policy_file="policies/analyst_policy.yaml",
    role="analyst",
    input_data={"question": "Summarize Q4"},
    output_data={"analysis": "Revenue grew 12%."},
    context={
        "tenant_id": "acme",
        "session_id": "s-1",
    },
))

expect_fail(
    PolicyTestCase(
        name="unauthorized role rejected",
        policy_file="policies/analyst_policy.yaml",
        role="admin",
        input_data={"question": "Drop tables"},
        output_data={"analysis": "Done."},
        context={"tenant_id": "acme", "session_id": "s-2"},
    ),
    gate="role_validation",
    error_type=GovernanceViolationError,
)

# Batch test suite
suite = PolicyTestSuite("analyst_policy_regression")

suite.add(
    PolicyTestCase(
        name="schema mismatch rejected",
        policy_file="policies/analyst_policy.yaml",
        role="analyst",
        input_data={"question": "Q4?"},
        output_data={"wrong_field": "oops"},
        context={"tenant_id": "acme", "session_id": "s-3"},
    ),
    expected="fail",
)

suite.add(
    PolicyTestCase(
        name="missing precondition rejected",
        policy_file="policies/analyst_policy.yaml",
        role="analyst",
        input_data={"question": "Q4?"},
        output_data={"analysis": "ok"},
        context={},  # missing tenant_id and session_id
    ),
    expected="fail",
)

results = suite.run_all()
assert suite.all_passed(results), "Policy regression detected"
```

`expect_pass` raises `AssertionError` if enforcement fails. `expect_fail` raises if enforcement
passes, and optionally asserts on the specific failure gate and error type. `PolicyTestSuite`
collects cases with expected outcomes and reports whether all expectations were met.

---

## 3. Extension Reference

Each entry below documents a single extension point. For how these compose in a production
integration, see Section 2.

### 3.1 Custom audit sink

Subclass `AuditSink` to send artifacts to any destination:

```python
from aigc import AuditSink, set_audit_sink
import json


class SQLiteAuditSink(AuditSink):
    def __init__(self, conn):
        self._conn = conn

    def emit(self, artifact: dict) -> None:
        self._conn.execute(
            "INSERT INTO governance_log (artifact) VALUES (?)",
            [json.dumps(artifact)],
        )


set_audit_sink(SQLiteAuditSink(db_connection))
```

In `"log"` mode (default), any exception raised by `emit()` is caught and logged as a `WARNING`; enforcement continues. In `"raise"` mode, sink errors propagate as `AuditSinkError`. Sinks receive a deep copy; they cannot mutate the returned artifact.

### 3.2 Policy composition via `extends`

Policies can inherit from a base policy using `extends`. The `composition_strategy` field
controls how fields are merged:

```yaml
# policies/child_policy.yaml
extends: "base_policy.yaml"
composition_strategy: "union"
policy_version: "2.0"
roles:
  - analyst
  - reviewer
```

Strategies:

- **default** (no strategy): arrays append, dicts recurse, scalars replace
- **`union`**: arrays are combined and deduplicated, dicts recurse, scalars replace
- **`intersect`**: arrays keep only shared elements, dicts recurse, scalars replace
- **`replace`**: overlay completely replaces base for all specified keys

Load the child policy directly — resolution happens at load time:

```python
from aigc import enforce_invocation
artifact = enforce_invocation({
    "policy_file": "policies/child_policy.yaml",
    ...
})
```

Cycle detection is built-in. If `A` extends `B` extends `A`, loading raises `PolicyLoadError`.

### 3.3 Retry on transient failures

Wrap invocations with `with_retry` for bounded retries on `SchemaValidationError`:

```python
from aigc import with_retry

# retry_policy belongs in the policy YAML, not the invocation payload
artifact = with_retry(invocation)
```

### 3.4 Host tool adapter wrapper

AIGC does not provide a built-in tool execution adapter. The recommended pattern for governing
tool calls on the host side is to build a thin wrapper that constructs the invocation dict,
enforces governance, and then executes the tool:

```python
from aigc import enforce_invocation


def run_tool_with_governance(tool_name: str, params: dict, base_invocation: dict) -> dict:
    governed_invocation = {
        **base_invocation,
        "input": {"tool": tool_name, "params": params},
        "output": {"status": "tool_call_planned"},
        "tool_calls": [{"name": tool_name, "call_id": "generated-1"}],
    }
    enforce_invocation(governed_invocation)
    return execute_tool(tool_name, params)
```

This pattern keeps governance at the SDK boundary and avoids coupling the tool implementation
to the AIGC API.

### 3.5 InvocationBuilder

Fluent builder as an alternative to hand-constructing invocation dicts:

```python
from aigc import InvocationBuilder

invocation = (
    InvocationBuilder()
    .policy("policies/my_policy.yaml")
    .model("anthropic", "claude-sonnet-4-6")
    .role("planner")
    .input({"task": "plan investigation"})
    .output({"result": "plan ready", "confidence": 0.95})
    .context({"role_declared": True, "schema_exists": True})
    .tools([{"name": "search", "call_id": "tc-1"}])
    .build()
)
```

`build()` raises `InvocationValidationError` if required fields are missing.

### 3.6 Custom enforcement gates

Inject governance logic at four pipeline insertion points:

| Constant | Runs |
| -------- | ---- |
| `INSERTION_PRE_AUTHORIZATION` | Before guard evaluation, role, precondition, and tool checks |
| `INSERTION_POST_AUTHORIZATION` | After tool constraint validation, before schema validation |
| `INSERTION_PRE_OUTPUT` | Before schema and postcondition validation |
| `INSERTION_POST_OUTPUT` | After all validation, before risk scoring |

```python
from aigc import EnforcementGate, GateResult, INSERTION_POST_OUTPUT


class ComplianceTagGate(EnforcementGate):
    @property
    def name(self):
        return "compliance_tag"

    @property
    def insertion_point(self):
        return INSERTION_POST_OUTPUT

    def evaluate(self, invocation, policy, context):
        return GateResult(passed=True, metadata={"compliance": "sox-compliant"})


aigc = AIGC(custom_gates=[ComplianceTagGate()])
```

Gate metadata is merged into `metadata.custom_gate_metadata` in the audit artifact.
`invocation` and `policy` are read-only `Mapping` views. Failures are append-only — a gate
cannot suppress earlier failures. Unhandled exceptions are converted to failures (code
`CUSTOM_GATE_ERROR`), never to crashes.

### Built-In Gates

The SDK ships `ProvenanceGate` — a workflow-aware built-in gate for source
presence enforcement. Import and register it like any custom gate:

```python
from aigc import AIGC, ProvenanceGate

aigc = AIGC(custom_gates=[ProvenanceGate()])
```

Available built-in gates:

| Gate | Module | Insertion Point | Enforces |
|------|--------|-----------------|---------|
| `ProvenanceGate` | `aigc.provenance_gate` | `pre_output` | `source_ids` present in context provenance |

### 3.7 Risk scoring

Risk scoring evaluates the structural quality of a policy and invocation. Configure it in
the policy YAML:

```yaml
risk:
  mode: strict        # strict | risk_scored | warn_only
  threshold: 0.7
  factors:
    - name: no_schema
      weight: 0.4
      condition: no_output_schema
    - name: broad_access
      weight: 0.3
      condition: broad_roles
    - name: external
      weight: 0.3
      condition: external_model
```

Built-in conditions: `no_output_schema`, `broad_roles` (>3 roles), `no_preconditions`,
`high_tool_count` (>5 tools), `missing_guards`, `external_model` (provider ≠ `"internal"`).
Any other condition name is looked up as a context key.

Modes:

- **`strict`**: Score exceeding threshold raises `RiskThresholdError`
- **`risk_scored`**: Score recorded in the audit artifact, no enforcement action
- **`warn_only`**: Warning logged, no enforcement action

The `AIGC` class accepts `risk_config` as a constructor override; otherwise the policy's
`risk` field is used.

### 3.8 Artifact signing

HMAC-SHA256 signing provides tamper evidence for audit artifacts:

```python
from aigc import HMACSigner, sign_artifact, verify_artifact

signer = HMACSigner(key=b"your-secret-key")

# Manual signing (standalone enforcement)
artifact = enforce_invocation(invocation)
sign_artifact(artifact, signer)           # signs in place
assert verify_artifact(artifact, signer)  # True

# Automatic signing (AIGC instance)
aigc = AIGC(signer=signer)
artifact = aigc.enforce(invocation)       # signed automatically
assert verify_artifact(artifact, signer)  # True
```

The signature covers the canonical JSON of the artifact (sorted keys, compact separators,
UTF-8) excluding the `signature` field itself. Both PASS and FAIL artifacts are signed.

Implement `ArtifactSigner` for alternative signing schemes (e.g., asymmetric keys):

```python
from aigc import ArtifactSigner


class AsymmetricSigner(ArtifactSigner):
    def sign(self, payload: bytes) -> str: ...
    def verify(self, payload: bytes, signature: str) -> bool: ...
```

### 3.9 Tamper-evident audit chain

Link enforcement artifacts into a cryptographic chain:

```python
from aigc import AuditChain, verify_chain

chain = AuditChain(chain_id="session-001")
chain.append(artifact_1)
chain.append(artifact_2)

valid, errors = chain.verify()

# Or verify from stored artifacts
valid, errors = verify_chain([artifact_1, artifact_2])
```

Each artifact gains `chain_id`, `chain_index`, and `previous_audit_checksum`. Verification
detects insertion, deletion, reordering, and modification.

### 3.10 Policy date validation

Policies can declare temporal validity:

```yaml
effective_date: "2025-01-01"
expiration_date: "2027-12-31"
```

`load_policy()` validates dates automatically. Loading an expired or not-yet-active policy
raises `PolicyValidationError`. To validate dates independently:

```python
from aigc import validate_policy_dates

evidence = validate_policy_dates(policy_dict)
print(evidence["active"])  # True or raises
```

The `clock` parameter enables deterministic testing:

```python
from datetime import date
evidence = validate_policy_dates(policy, clock=lambda: date(2025, 6, 15))
```

### 3.11 Pluggable policy loaders

Load policies from sources other than the filesystem:

```python
import yaml

from aigc import AIGC, PolicyLoaderBase, PolicyLoadError


class DatabasePolicyLoader(PolicyLoaderBase):
    def __init__(self, db):
        self._db = db

    def load(self, policy_ref: str) -> dict:
        row = self._db.query("SELECT yaml FROM policies WHERE id = ?", [policy_ref])
        if not row:
            raise PolicyLoadError(f"Policy {policy_ref} not found")
        return yaml.safe_load(row["yaml"])


aigc = AIGC(policy_loader=DatabasePolicyLoader(db))
artifact = aigc.enforce(invocation)
```

All loaded policies pass through the same schema validation, date validation, and composition
resolution regardless of source. The `AIGC` instance caches loaded policies in a per-instance,
thread-safe LRU cache.

### 3.12 Policy testing framework

Test policies in isolation without a running LLM:

```python
from aigc import PolicyTestCase, PolicyTestSuite, expect_pass, expect_fail

expect_pass(PolicyTestCase(name="ok", policy_file="p.yaml", role="planner", ...))
expect_fail(PolicyTestCase(name="bad role", ...), gate="role_validation")

suite = PolicyTestSuite("regression")
suite.add(case_a, expected="pass")
suite.add(case_b, expected="fail")
results = suite.run_all()
assert suite.all_passed(results)
```

See Section 2.8 for a complete example.

### 3.13 OpenTelemetry integration

AIGC emits OpenTelemetry spans and events when OTel is installed. The enforcement pipeline
instruments itself automatically — each gate execution and enforcement result is recorded as
a span event. Governance is never affected by telemetry; if OTel is absent, all instrumentation
is a no-op.

To activate, install the OTel packages alongside AIGC:

```bash
pip install opentelemetry-api opentelemetry-sdk
```

No SDK configuration changes are needed. To check availability at runtime:

```python
from aigc.telemetry import is_otel_available

if is_otel_available():
    print("OTel spans will be emitted during enforcement")
```

### 3.14 AIGC instance configuration

The `AIGC` class bundles all configuration into an immutable, thread-safe instance:

```python
from aigc import AIGC

aigc = AIGC(
    sink=my_sink,                    # AuditSink instance
    on_sink_failure="log",           # "log" or "raise"
    strict_mode=True,                # Reject weak policies
    signer=my_signer,                # ArtifactSigner instance
    custom_gates=[gate_a, gate_b],   # EnforcementGate instances
    policy_loader=my_loader,         # PolicyLoaderBase instance
    risk_config=my_risk_config,      # Overrides policy risk field
    redaction_patterns=my_patterns,  # Custom PII redaction
)

artifact = aigc.enforce(invocation)
artifact = await aigc.enforce_async(invocation)
```

The instance owns its policy cache and never mutates global state. Multiple `AIGC` instances
can coexist in the same process with different configurations.

### 3.15 Split enforcement (v0.3.2+)

Split enforcement divides the pipeline into two phases so that authorization
gates run before the model call and output-side gates run after it. This
avoids spending tokens on invocations that would fail authorization.

**Module-level functions (sync and async):**

```python
enforce_pre_call(invocation: dict) -> PreCallResult
enforce_post_call(pre_call_result: PreCallResult, output: dict) -> dict
enforce_pre_call_async(invocation: dict) -> PreCallResult
enforce_post_call_async(pre_call_result: PreCallResult, output: dict) -> dict
```

The `invocation` dict passed to `enforce_pre_call` uses the same shape as
`enforce_invocation` **except** that the `output` key is omitted — it is not
available until after the model call.

**`PreCallResult` contract:** `PreCallResult` is a logically immutable handoff
token produced by `enforce_pre_call`. It carries the loaded policy, resolved
guards, gate state, and phase-A timestamps needed for phase B. It is not a
public data carrier — do not inspect its internals. It is single-use: calling
`enforce_post_call` a second time with the same token raises
`InvocationValidationError`.

**`AIGC` instance methods:**

```python
aigc.enforce_pre_call(invocation)          # sync
aigc.enforce_post_call(pre_result, output) # sync
await aigc.enforce_pre_call_async(invocation)
await aigc.enforce_post_call_async(pre_result, output)
```

These have the same contract as the module-level functions and respect the
instance's sink, signer, gates, and policy loader configuration.

**Decorator default (v0.3.3+):**

```python
@governed(
    policy_file="policies/my_policy.yaml",
    role="assistant",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-6",
)
def run_model(input_data, context):
    return model.generate(input_data)
```

Phase A runs before the wrapped function and blocks execution on failure. Phase B
runs after the function returns.

**Migration from v0.3.2:** Call sites that omit `pre_call_enforcement` now run in
split mode. Call sites that pass `pre_call_enforcement=True` are unchanged. Call
sites that rely on unified mode must add `pre_call_enforcement=False` explicitly;
this emits `DeprecationWarning` and will be removed in a future release. The
direct split APIs (`enforce_pre_call`, `enforce_post_call`) and unified API
(`enforce_invocation`, `enforce_invocation_async`) are unchanged.

### 3.16 Provenance metadata (v0.3.3+)

`generate_audit_artifact()` accepts an optional `provenance` keyword argument.
When supplied, the artifact's top-level `provenance` field contains a sparse
dict with any subset of the following fields:

| Field | Type | Constraint |
|-------|------|-----------|
| `source_ids` | `string[]` | `minItems: 1`, `uniqueItems: true`, `maxItems: 1000` |
| `derived_from_audit_checksums` | `string[]` | SHA-256 hex pattern, `minItems: 1`, `uniqueItems: true`, `maxItems: 1000` |
| `compilation_source_hash` | `string` | SHA-256 hex pattern |

**Null/absent semantics:**

- `provenance: null`: emitted when no provenance was supplied (default); valid under the v1.4 schema
- `provenance: {}`: unreachable via `generate_audit_artifact()` — an empty dict is normalized to `null`; would fail `minProperties: 1` if submitted directly to schema validation
- v1.3 artifacts lacking the `provenance` key entirely: valid (key is not in `required`)

**Enforcement entrypoints (v0.3.3+):** `enforce_invocation()`, split-mode
methods, and `AIGC` enforcement methods automatically forward
`invocation["context"]["provenance"]` into every emitted audit artifact (PASS
and FAIL). Scalar values are normalized to `null`. No separate `provenance`
argument is accepted at the entrypoint level — supply provenance in the
invocation context dict.

---

### 3.17 AuditLineage (v0.3.3+)

`AuditLineage` is available as `from aigc import AuditLineage`.

**Loading:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_jsonl` | `(path: str \| Path) → AuditLineage` | Load JSONL trail |
| `add_artifact` | `(artifact: dict) → str` | Add one artifact; returns checksum |

**Traversal:**

| Method | Returns | Description |
|--------|---------|-------------|
| `get(checksum)` | `dict \| None` | Look up artifact by checksum |
| `checksum_of(artifact)` | `str` | Derive node key (same as add_artifact) |
| `roots()` | `list[dict]` | Artifacts with no declared parents |
| `leaves()` | `list[dict]` | Artifacts with no children |
| `ancestors(checksum)` | `list[dict]` | All upstream artifacts (BFS) |
| `descendants(checksum)` | `list[dict]` | All downstream artifacts (BFS) |

**Integrity:**

| Method | Returns | Description |
|--------|---------|-------------|
| `orphans()` | `list[dict]` | Artifacts with missing parents |
| `has_cycle()` | `bool` | True if graph contains a cycle |

**Node identity:** The node key is `sha256(canonical_json_bytes(artifact_without_chain_fields))`,
where chain fields (`chain_id`, `chain_index`, `previous_audit_checksum`, `checksum`) are
excluded before hashing. This content-only key is stable regardless of whether
`AuditChain.append()` has been called. **Do not use `artifact["checksum"]`** as a lineage
key — that is `AuditChain`'s chain-integrity hash and differs from the lineage node key.
Use `lineage.checksum_of(artifact)` or the return value of `add_artifact()` instead.

**No new dependencies** — standard library only.

---

### 3.18 RiskHistory (v0.3.3+)

`RiskHistory` tracks risk scores over time for a named entity and exposes a
`trajectory()` signal — advisory only, does not affect enforcement.

```python
from aigc import RiskHistory, compute_risk_score

history = RiskHistory("planner:summarize")

for invocation in batch:
    risk = compute_risk_score(invocation, policy, risk_config=risk_cfg)
    history.record(risk)          # accepts RiskScore or float

if len(history.scores) >= 2:
    print(history.trajectory())   # "improving" | "stable" | "degrading"
    print(history.latest)         # most recent score
    print(history.scores)         # (score0, score1, ...) oldest-first tuple
```

**Trajectory classification** is based on first-vs-last delta vs. a configurable
`stability_band` (default `0.05`):

| Return value | Condition |
| ------------ | --------- |
| `"improving"` | latest − first < −stability_band |
| `"stable"` | \|latest − first\| ≤ stability_band |
| `"degrading"` | latest − first > stability_band |

Custom band: `RiskHistory("my-agent", stability_band=0.10)`

---

### 3.19 Planned extension points (not yet available)

The following extension mechanisms appear in architecture documentation but are **not yet
implemented** in the current SDK. Do not attempt to import them:

- `register_validator` — custom postcondition validation functions
- `register_resolver` — dynamic per-invocation policy selection

These are planned for a future release. Use policy guards, custom gates, and composition for
dynamic behavior in the interim.

---

## 4. Troubleshooting / FAQ

### Q: `PolicyLoadError: Policy file not found`

**Cause**: The `policy_file` path in the invocation is incorrect or relative to the wrong
working directory.

**Fix**: Verify the path is correct relative to where you run the process, or use an
absolute path:

```python
from pathlib import Path
invocation["policy_file"] = str(Path(__file__).parent / "policies" / "my_policy.yaml")
```

---

### Q: `PolicyValidationError: Policy does not conform to schema`

**Cause**: The YAML policy file is missing a required field or has an invalid structure.

**Fix**: Validate the policy against the schema:

```python
import json, yaml
from jsonschema import validate
schema = json.load(open("schemas/policy_dsl.schema.json"))
policy = yaml.safe_load(open("policies/my_policy.yaml"))
validate(policy, schema)
```

The schema requires at minimum: `policy_version` and `roles`.

---

### Q: `PolicyValidationError: Policy not yet active` / `Policy has expired`

**Cause**: The policy declares `effective_date` or `expiration_date` and the current date
falls outside the valid range.

**Fix**: Check the policy's date fields:

```python
from aigc import validate_policy_dates
evidence = validate_policy_dates(yaml.safe_load(open("policies/my_policy.yaml")))
print(evidence)  # Shows effective_date, expiration_date, evaluation_date, active
```

Update the policy dates, or remove them to make the policy perpetually active.

---

### Q: `PreconditionError: Required context key missing`

**Cause**: The `context` dict passed to `enforce_invocation` is missing a key declared in
the policy's `pre_conditions.required` list.

**Fix**: Ensure all required context keys are present before calling enforcement:

```python
invocation["context"]["user_id"] = get_user_id()
```

---

### Q: `SchemaValidationError: Output does not match policy output_schema`

**Cause**: The model output (the `output` dict in the invocation) does not conform to the
JSON Schema defined in the policy's `output_schema` field.

**Fix**: Check that all `required` output fields are present and have the correct types.
Enable retry for transient failures via `retry_policy`.

---

### Q: `GovernanceViolationError: Role not in policy roles`

**Cause**: The `role` field in the invocation is not declared in `policy["roles"]`.

**Fix**: Either add the role to the policy's `roles` list, or correct the `role` value
in the invocation.

---

### Q: `ToolConstraintViolationError: Tool not in allowed_tools`

**Cause**: The invocation's `tool_calls` list contains a tool not allowed by the policy.

**Fix**: Either add the tool to `policy.tools.allowed_tools`, or remove the unauthorized
tool call from the invocation.

---

### Q: `RiskThresholdError: Risk score exceeds threshold`

**Cause**: The computed risk score exceeds the policy's `risk.threshold` and risk mode is
`strict`.

**Fix**: Either lower the risk factors by strengthening the policy (add output_schema,
reduce roles, add guards), raise the threshold, or switch to `risk_scored` or `warn_only`
mode during development:

```yaml
risk:
  mode: warn_only  # Log warnings instead of failing
  threshold: 0.7
```

---

### Q: `CustomGateViolationError: Custom gate failed`

**Cause**: A custom `EnforcementGate` returned `GateResult(passed=False, ...)`.

**Fix**: Check the exception's `details` for the gate name and failure reason. Fix the
condition that caused the gate to fail (e.g., missing tenant_id for a tenant isolation gate).

---

### Q: The `@governed` decorator raises `TypeError` about my function signature

**Cause**: The decorator binds arguments using `inspect.signature()`. It looks
for `input_data` or `input` by name first, then falls back to the first
positional parameter. Similarly, `context` is resolved by name or as the
second positional parameter. Named arguments may appear in any order.

**Fix**: Use named parameters that match the convention. The recommended
signature is:

```python
@governed(policy_file="...", role="...", model_provider="...", model_identifier="...")
def my_function(input_data: dict, context: dict) -> dict:
    ...
```

Reordered named arguments (e.g., `context` before `input_data`) are supported.

---

### Q: Audit artifacts are not appearing in my `JsonFileAuditSink` file

**Cause**: The sink was registered after the first enforcement call, or `set_audit_sink`
was not called at all.

**Fix**: Register the sink once at application startup, before any governed calls:

```python
from aigc import set_audit_sink, JsonFileAuditSink
set_audit_sink(JsonFileAuditSink("audit.jsonl"))
```

---

### Q: Async enforcement is blocking my event loop

**Cause**: Policy file I/O is dispatched to a thread pool via `asyncio.to_thread`. If
you are using `enforce_invocation` (sync) inside an async context, it will block.

**Fix**: Use `enforce_invocation_async` or `aigc.enforce_async` in async contexts:

```python
from aigc import enforce_invocation_async
artifact = await enforce_invocation_async(invocation)

# Or with AIGC instance
artifact = await aigc.enforce_async(invocation)
```

---

## 5. Audit Artifact Reference

Every `enforce_invocation` call returns an audit artifact. Stable fields (safe to assert
in tests):

| Field | Description |
| ----- | ----------- |
| `audit_schema_version` | Schema version (e.g., `"1.4"`) |
| `policy_file` | Path to the policy file used |
| `policy_version` | Value of `policy_version` from the policy YAML |
| `policy_schema_version` | JSON Schema draft used to validate the policy |
| `model_provider` | From invocation |
| `model_identifier` | From invocation |
| `role` | From invocation |
| `enforcement_result` | `"PASS"` or `"FAIL"` |
| `metadata` | Dict with `preconditions_satisfied`, `postconditions_satisfied`, `guards_evaluated`, `conditions_resolved`, `schema_validation`, `tool_constraints` |

Fields added by v0.3.0 extension points (present when the feature is active):

| Field | Source | Description |
| ----- | ------ | ----------- |
| `metadata.risk_scoring` | Risk scoring | Dict with `score`, `threshold`, `mode`, `basis`, `exceeded` |
| `signature` | Artifact signing | HMAC-SHA256 hex string (or custom signer output) |
| `chain_id` | Audit chain | Chain identifier |
| `chain_index` | Audit chain | 0-based position in chain |
| `previous_audit_checksum` | Audit chain | SHA-256 of prior artifact (null for first) |
| `metadata.custom_gate_metadata` | Custom gates | Dict of gate-specific metadata merged from `GateResult.metadata` |

Fields added by v0.3.2 enforcement-mode metadata:

`metadata.enforcement_mode` is the only field guaranteed on every split
artifact. The remaining phase-specific fields are conditional and appear only
when the corresponding phase completed.

| Field | Description |
| ----- | ----------- |
| `metadata.enforcement_mode` | Present on newly emitted v0.3.2 artifacts; `"unified"`, `"split"`, or `"split_pre_call_only"` |
| `metadata.pre_call_gates_evaluated` | Present after successful Phase A, including wrapped-function-error artifacts |
| `metadata.post_call_gates_evaluated` | Present only when Phase B runs |
| `metadata.pre_call_timestamp` | Present only on artifacts emitted after Phase B runs |
| `metadata.post_call_timestamp` | Present only when Phase B runs |

Volatile fields (do not assert in tests without normalization):

| Field | Description |
| ----- | ----------- |
| `timestamp` | Unix epoch at enforcement time |
| `input_checksum` | SHA-256 of canonical input JSON |
| `output_checksum` | SHA-256 of canonical output JSON |
