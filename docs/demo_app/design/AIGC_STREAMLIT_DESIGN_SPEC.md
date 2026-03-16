# AIGC Milestone 2 — Streamlit Demo App Design Specification

**Version:** 1.3
**Date:** 2026-03-08
**Status:** Ready for Implementation (guide rail UX addition)
**Target AIGC Version:** 0.3.0 (builds on top of 0.2.0)

---

## 1. Purpose

This document is the authoritative build specification for a Streamlit-based demo application that implements, tests, and showcases all 10 AIGC Milestone 2 capabilities. It is written for Claude Code to execute step-by-step.

The app serves three purposes: (1) drive M2 feature development by requiring each capability to work end-to-end, (2) provide interactive testing for each feature in isolation, and (3) demo governance concepts to stakeholders who don't read code.

---

## 2. Build Order

The implementation follows a strict dependency chain. Each phase must be complete before the next begins.

**Phase 1 — SDK Extensions (M2 features in `aigc/`)**
Build the 10 new SDK capabilities inside the existing AIGC codebase. These are the real features; the Streamlit app is just a frontend.

**Phase 2 — Shared Streamlit Infrastructure**
Build the app shell, navigation, session state, and reusable components.

**Phase 3 — Lab Implementations (7 labs)**
Build each lab in priority order, each isolating one or more M2 features.

**Phase 4 — Integration Testing & Polish**
End-to-end tests, error handling, and final UX cleanup.

---

## 3. Architecture Overview

```
aigc/                              # Existing SDK (v0.2.0 baseline)
├── __init__.py                    # Public API — add new M2 exports here
├── _internal/                     # All implementation logic
│   ├── enforcement.py             # Core pipeline — extend with custom gates
│   ├── audit.py                   # Extend with signing + chaining
│   ├── risk.py                    # NEW: Risk scoring engine
│   ├── signing.py                 # NEW: Audit artifact signing
│   ├── chain.py                   # NEW: Tamper-evident audit chain
│   ├── composition.py             # NEW: Policy composition restrictions
│   ├── loaders.py                 # NEW: Pluggable policy loaders
│   ├── versioning.py              # NEW: Policy versioning
│   ├── gates.py                   # NEW: Custom enforcement gate plugin
│   ├── otel.py                    # NEW: OpenTelemetry integration
│   ├── testing.py                 # NEW: Policy testing framework
│   └── export.py                  # NEW: Compliance export
│
├── testing.py                     # Public re-export for aigc.testing
│
streamlit_app/                     # NEW: Demo application
├── app.py                         # Entry point + navigation
├── shared/
│   ├── __init__.py
│   ├── ai_client.py               # Claude/GPT wrapper
│   ├── aigc_runner.py             # AIGC enforcement helper
│   ├── artifact_display.py        # Reusable artifact viewer
│   ├── policy_editor.py           # YAML editor + validator
│   ├── guide_rail.py              # Lab guide rail (contextual help panel)
│   └── state.py                   # Session state management
├── labs/
│   ├── __init__.py
│   ├── lab1_risk_scoring.py
│   ├── lab2_signing.py
│   ├── lab3_chain.py
│   ├── lab4_composition.py
│   ├── lab5_loaders.py
│   ├── lab6_custom_gates.py
│   └── lab7_compliance.py
└── sample_policies/
    ├── medical_ai.yaml
    ├── finance_ai.yaml
    ├── content_moderation.yaml
    ├── medical_ai_child.yaml
    └── high_risk.yaml
```

---

## 4. Phase 1 — SDK Extensions (M2 Features)

Each feature below is a new module under `aigc/_internal/`. Every feature must have unit tests, golden replays where applicable, and be re-exported from `aigc/__init__.py`.

### 4.1 Risk Scoring Engine (`aigc/_internal/risk.py`)

**Design Issue:** D-08
**Wireframe:** Lab 1

**What it does:** Computes a 0.0–1.0 risk score for each invocation based on configurable weighted signals, then uses the score to determine enforcement behavior.

**Public API:**

```python
# In aigc/_internal/risk.py

from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class RiskSignal:
    """A single risk signal with name, weight, and computed value."""
    name: str
    weight: float       # 0.0 to 1.0
    value: float        # 0.0 to 1.0
    reason: str         # Human-readable explanation

@dataclass(frozen=True)
class RiskScore:
    """Composite risk score with breakdown."""
    score: float               # Weighted composite 0.0–1.0
    signals: list[RiskSignal]  # Individual signal breakdown
    threshold: float           # Policy-defined threshold
    action: str                # "allow", "warn", "block"

def compute_risk_score(
    invocation: Mapping[str, Any],
    policy: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> RiskScore:
    """Compute risk score from policy-defined signals.

    Deterministic: same inputs always produce same score.
    """
    ...
```

**Policy DSL extension:**

```yaml
# New top-level key in policy YAML
risk_scoring:
  mode: "risk_scored"          # "strict" | "risk_scored" | "warn_only"
  threshold: 0.7               # Block above this score
  signals:
    - name: "model_capability"
      weight: 0.3
      rule: "'gpt-4' in model_identifier or 'claude-3-opus' in model_identifier"
    - name: "sensitive_domain"
      weight: 0.4
      rule: "context.domain in ['medical', 'financial', 'legal']"
    - name: "missing_guardrails"
      weight: 0.3
      rule: "not context.human_review_required"
```

**Rule expression language:** Risk signal rules use the **same AST-based expression evaluator** as guards
(defined in `aigc/_internal/guards.py`). The canonical operator set is defined in `AIGC_HIGH_LEVEL_DESIGN.md`
§7.4 and consists of: simple boolean lookup, `==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `not`,
parenthesised grouping, and membership (`in`). The `contains` keyword is **not** supported — use
`'substring' in field` (Python `in` operator) instead.

**M2 expression extensions required:** The sample risk rules above use two constructs not yet documented in
the v0.2.0 guard evaluator: **dotted attribute access** (`context.domain`) and **list literals**
(`['medical', 'financial', 'legal']`). These must be added to the guard expression evaluator in M2 and
documented in `AIGC_HIGH_LEVEL_DESIGN.md` §7.4 before risk scoring is implemented. Until then, sample rules
should be treated as target syntax, not current capability. If M2 elects not to extend the evaluator, the
sample rules must be rewritten using only the v0.2.0 operator set
(e.g., `"domain == 'medical' or domain == 'financial' or domain == 'legal'"`).

**Enforcement modes:**

| Mode | Behavior |
|------|----------|
| `strict` | All failures block. Risk score recorded but not used for decisions. |
| `risk_scored` | Score < threshold → PASS. Score >= threshold → FAIL. |
| `warn_only` | Always PASS. Score recorded in artifact. Warning logged if above threshold. |

**Integration with enforcement pipeline:**

Risk scoring runs after precondition validation but before schema validation. The computed `risk_score` value is written into the audit artifact's `risk_score` field (currently `null` in v0.2.0 schema).

In `aigc/_internal/enforcement.py`, add a new gate constant:

```python
GATE_RISK = "risk_scoring"
```

Insert between `GATE_PRECONDS` and `GATE_TOOLS` in the pipeline. Update `AUTHORIZATION_GATES` tuple accordingly.

**Schema changes:**

Update `schemas/policy_dsl.schema.json` to add the `risk_scoring` property with its sub-schema.

The `audit_artifact.schema.json` already has `risk_score` as `["number", "null"]` — no schema change needed, but the field will now be populated.

**Tests required:**

- `test_risk_scoring.py` — Unit tests for `compute_risk_score()` with deterministic inputs
- Risk score determinism golden replay (same inputs → same score across 1000 runs)
- Each enforcement mode tested (strict blocks on any failure, risk_scored uses threshold, warn_only always passes)
- Signal evaluation edge cases (missing context keys, empty signals list, all-zero weights)
- Integration test: risk score appears in audit artifact

**Determinism constraint:** Signal evaluation must use sorted key iteration. No randomness. No floating-point accumulation drift (use `decimal.Decimal` or pre-multiply to integers).

---

### 4.2 Audit Artifact Signing (`aigc/_internal/signing.py`)

**Design Issue:** D-05 (extended)
**Wireframe:** Lab 2

**What it does:** Cryptographically signs audit artifacts using HMAC-SHA256 with a pluggable signer interface. Enables verification that artifacts haven't been tampered with.

**Public API:**

```python
# In aigc/_internal/signing.py

from abc import ABC, abstractmethod
from typing import Any

class AuditSigner(ABC):
    """Pluggable signing interface."""

    @abstractmethod
    def sign(self, canonical_bytes: bytes) -> str:
        """Produce a signature string from canonical artifact bytes."""
        ...

    @abstractmethod
    def verify(self, canonical_bytes: bytes, signature: str) -> bool:
        """Verify a signature against canonical artifact bytes."""
        ...

class HMACSigner(AuditSigner):
    """HMAC-SHA256 signer with a shared secret key."""

    def __init__(self, secret_key: str | bytes):
        ...

    def sign(self, canonical_bytes: bytes) -> str:
        """Returns hex-encoded HMAC-SHA256."""
        ...

    def verify(self, canonical_bytes: bytes, signature: str) -> bool:
        """Constant-time comparison."""
        ...

def sign_artifact(artifact: dict[str, Any], signer: AuditSigner) -> dict[str, Any]:
    """Sign an artifact in-place, populating the 'signature' field.

    Signing is computed over canonical_json_bytes() of the artifact
    with the 'signature' field set to null.
    """
    ...

def verify_artifact(artifact: dict[str, Any], signer: AuditSigner) -> bool:
    """Verify an artifact's signature.

    Returns True if signature is valid, False otherwise.
    Raises ValueError if artifact has no signature.
    """
    ...
```

**Integration with AIGC class:**

```python
# Extended AIGC constructor
class AIGC:
    def __init__(
        self,
        *,
        sink=None,
        on_sink_failure="log",
        strict_mode=False,
        redaction_patterns=None,
        signer: AuditSigner | None = None,  # NEW
    ):
        ...
```

When a signer is configured, `enforce()` calls `sign_artifact()` on the audit artifact before emitting to the sink.

**Signing process:**

1. Generate audit artifact as normal (with `signature: null`)
2. Compute `canonical_json_bytes()` of the artifact
3. Call `signer.sign(canonical_bytes)` to get signature
4. Set `artifact["signature"] = signature`
5. Emit to sink

**Verification process:**

1. Extract `signature` from artifact, store it
2. Set `artifact["signature"] = null`
3. Compute `canonical_json_bytes()` of the artifact
4. Call `signer.verify(canonical_bytes, signature)`
5. Restore original signature value

**Tests required:**

- `test_signing.py` — sign/verify round-trip passes
- Tampered artifact → verify fails
- Missing signature → ValueError
- Custom signer implementation works
- Constant-time comparison (no timing side-channel)
- Integration: AIGC(signer=...) produces signed artifacts

---

### 4.3 Tamper-Evident Audit Chain (`aigc/_internal/chain.py`)

**Design Issue:** ADR-0008
**Wireframe:** Lab 3

**What it does:** Links consecutive audit artifacts into a hash chain where each artifact references the hash of the previous one. Any modification to a historical artifact breaks the chain.

**Public API:**

```python
# In aigc/_internal/chain.py

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ChainLink:
    """A single link in the audit chain."""
    sequence: int
    artifact_checksum: str              # SHA-256 of canonical_json_bytes(artifact)
    previous_chain_checksum: str | None # None for genesis link
    chain_checksum: str                 # SHA-256(artifact_checksum + previous_chain_checksum)

class AuditChain:
    """Tamper-evident audit chain.

    Thread-safe: uses a lock for append operations.

    The chain stores both the ChainLink objects (checksums only) AND
    the full artifact dicts. Verification recomputes checksums from
    stored artifacts and compares against stored ChainLink values.
    This means modifying a stored artifact will be detected.
    """

    def __init__(self) -> None:
        self._links: list[ChainLink] = []
        self._artifacts: list[dict[str, Any]] = []
        ...

    def append(self, artifact: dict[str, Any]) -> ChainLink:
        """Add an artifact to the chain. Returns the new link.

        Stores a deep copy of the artifact.
        Computes artifact_checksum = SHA-256(canonical_json_bytes(artifact)).
        chain_checksum = SHA-256(artifact_checksum + previous_chain_checksum).
        """
        ...

    def verify(self) -> tuple[bool, int | None]:
        """Verify entire chain integrity by recomputing from stored artifacts.

        For each link at index i:
          1. Recompute artifact_checksum from self._artifacts[i]
          2. Compare against self._links[i].artifact_checksum
          3. Recompute chain_checksum from (artifact_checksum + previous_chain_checksum)
          4. Compare against self._links[i].chain_checksum

        Returns (True, None) if all links valid.
        Returns (False, break_index) if tampered — break_index is the
        first link where recomputed checksums don't match stored values.
        """
        ...

    def get_link(self, sequence: int) -> ChainLink:
        """Get a specific link by sequence number."""
        ...

    @property
    def length(self) -> int:
        ...

    @property
    def head(self) -> ChainLink | None:
        """Most recent link."""
        ...

    def export(self) -> list[dict[str, Any]]:
        """Export chain as a list of serializable dicts."""
        ...
```

**Integration with AIGC class:**

```python
class AIGC:
    def __init__(self, *, chain: AuditChain | None = None, ...):
        self._chain = chain
```

After signing (if signer configured) and before sink emission, if a chain is configured, `enforce()` calls `chain.append(artifact)`. The chain link metadata is added to the artifact's metadata:

```python
artifact["metadata"]["chain_sequence"] = link.sequence
artifact["metadata"]["chain_checksum"] = link.chain_checksum
artifact["metadata"]["previous_chain_checksum"] = link.previous_chain_checksum
```

**Tests required:**

- `test_chain.py` — append, verify, tamper detection
- Genesis link has `previous_chain_checksum: null`
- Modifying any link breaks verification from that point forward
- Thread safety under concurrent appends
- Chain export/import round-trip
- Integration: AIGC(chain=...) appends to chain on enforce

---

### 4.4 Policy Composition with Restriction Semantics (`aigc/_internal/composition.py`)

**Design Issue:** D-06
**Wireframe:** Lab 4

**What it does:** Extends the existing `extends` keyword with merge
strategies that prevent privilege escalation and governance weakening.
A child policy can restrict the parent but cannot grant new permissions
or weaken governance constraints (postconditions).
**Escalation validation is mandatory** — `compose_policies()` calls `validate_no_escalation()` internally and raises `PolicyValidationError` on any violation. Callers cannot bypass this check.

**Public API:**

```python
# In aigc/_internal/composition.py

from typing import Any

class EscalationError(PolicyValidationError):
    """Raised when a child policy attempts to escalate privileges beyond its parent."""
    ...

def compose_policies(
    base: dict[str, Any],
    child: dict[str, Any],
    *,
    allow_escalation: bool = False,
) -> dict[str, Any]:
    """Compose child policy onto base using child's _merge strategy.

    Merge strategies per field (when _merge directive is present):
      - intersect: result is intersection (child can only restrict)
      - union: result is union (child can extend)
      - replace: child completely replaces parent value

    Default per-field strategy (when _merge is present but field not
    listed) is 'intersect' for security.

    When _merge directive is absent entirely, falls back to v0.2.0
    legacy merge semantics: lists=concat, dicts=recursive-merge,
    scalars=replace. This preserves backward compatibility with
    existing extends-without-_merge policies.

    SECURITY INVARIANT: After merging (regardless of merge mode),
    validate_no_escalation() is called automatically. If escalation
    is detected and allow_escalation is False, raises EscalationError.
    This is not optional — callers cannot skip it. The strategies
    themselves don't require allow_escalation; the flag controls
    whether post-merge validation violations are raised or suppressed.

    The allow_escalation=True escape hatch exists for testing only and
    must not be exposed in the Streamlit UI.
    """
    ...

def validate_no_escalation(
    base: dict[str, Any],
    composed: dict[str, Any],
) -> list[str]:
    """Check that composition didn't escalate privileges or weaken governance.

    Returns list of escalation violations (empty = safe).
    Checks:
      - composed roles ⊆ base roles
      - composed tools ⊆ base tools
      - composed preconditions ⊇ base preconditions (can add, not remove)
      - composed postconditions ⊇ base postconditions (can add, not remove)
    """
    ...
```

**Policy DSL extension:**

```yaml
# Child policy with merge directives
extends: "base_policy.yaml"
_merge:
  roles: "intersect"         # Only roles in BOTH parent and child
  tools: "intersect"         # Only tools in BOTH
  pre_conditions: "union"    # Combine preconditions (additive = more restrictive, so safe)
  output_schema: "replace"   # Child's schema wins entirely

roles:
  - planner                  # Must exist in parent; 'synthesizer' from parent is dropped
```

**Security model for merge strategies:**

Escalation risk depends on the **field** being merged, not just the
strategy. Fields are classified into three categories:

- **Permission-granting** (roles, tools, guards) — control what the
  caller can do
- **Governance-constraint** (pre\_conditions, post\_conditions) — control
  what checks are enforced
- **Structural** (output\_schema) — define output shape, not privilege

| Strategy | Permission-granting fields | Governance-constraint fields | Structural fields |
|----------|---------------------------|-----------------------------|--------------------|
| `intersect` | Allowed (can only restrict) | Allowed (can only restrict) | Allowed |
| `union` | Blocked — raises `EscalationError` | Allowed (adding conditions = more restrictive) | Allowed |
| `replace` | Blocked — raises `EscalationError` | Blocked — raises `EscalationError` (can remove conditions) | Allowed |

`validate_no_escalation()` enforces two invariants: (1) permission-granting
fields cannot be expanded beyond the parent, and (2) governance-constraint
fields cannot be reduced below the parent. Structural fields like
`output_schema` are unrestricted because they define data shape, not
governance privilege — and the right mitigation for schema strictness is a
postcondition like `output_schema_valid`, which *is* protected by the
governance-constraint invariant.

**M3 revisit:** Evaluate whether to extend monotonic restriction to
`output_schema` via JSON Schema subsumption checking, based on real-world
composition usage in M2.

**Integration with policy loader:**

Modify `aigc/_internal/policy_loader.py` `load_policy()` to call
`compose_policies()` when `extends` is present. Two modes:

- **With `_merge` directive:** Field-level merge strategies apply.
  Unlisted fields default to `intersect`.
- **Without `_merge` directive:** Falls back to v0.2.0 legacy merge
  (lists=concat, dicts=recursive-merge, scalars=replace) via the
  existing `_merge_policies()` function.

In both modes, `compose_policies()` enforces
`validate_no_escalation()` internally after merging. The loader does
not need a separate escalation check — the security boundary is
inside the composition function itself, not at the call site.

**Schema changes:**

Update `schemas/policy_dsl.schema.json` to add `_merge` as an optional top-level property:

```json
"_merge": {
  "type": "object",
  "additionalProperties": {
    "type": "string",
    "enum": ["intersect", "union", "replace"]
  }
}
```

**Tests required:**

- `test_composition_m2.py` — each merge strategy for each policy field
- Escalation detection: child adding a role not in parent → violation
- Escalation detection: child removing a precondition → violation
- Escalation detection: child removing a postcondition → violation
- Schema replacement: child replacing output\_schema → allowed (structural field)
- Adversarial: 100 random child policies cannot escalate base
- Golden replay: composition produces deterministic results
- Backward compatibility: existing `extends` without `_merge` uses v0.2.0 legacy merge (lists=concat, dicts=recursive-merge, scalars=replace) — then passes through `validate_no_escalation()`

---

### 4.5 Pluggable Policy Loader (`aigc/_internal/loaders.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 5 (combined with versioning)

**What it does:** Abstracts policy loading behind a `PolicyLoader` interface so policies can come from filesystem, remote registries, or in-memory stores.

**Public API:**

```python
# In aigc/_internal/loaders.py

from abc import ABC, abstractmethod
from typing import Any

class PolicyLoader(ABC):
    """Abstract interface for policy loading."""

    @abstractmethod
    def load(self, policy_ref: str) -> dict[str, Any]:
        """Load and return a parsed policy dict.

        :param policy_ref: A reference string (file path, URL, key, etc.)
        :raises PolicyLoadError: If policy cannot be loaded
        """
        ...

    @abstractmethod
    def exists(self, policy_ref: str) -> bool:
        """Check if a policy reference is valid."""
        ...

class FileSystemLoader(PolicyLoader):
    """Load policies from YAML files on disk (existing behavior)."""
    ...

class InMemoryLoader(PolicyLoader):
    """Load policies from an in-memory dict. Useful for testing."""

    def __init__(self, policies: dict[str, dict[str, Any]] | None = None):
        self._policies = policies or {}

    def register(self, name: str, policy: dict[str, Any]) -> None:
        ...

    def load(self, policy_ref: str) -> dict[str, Any]:
        ...

    def exists(self, policy_ref: str) -> bool:
        ...

class RemoteLoader(PolicyLoader):
    """Load policies from an HTTP endpoint.

    Caches with TTL. Validates schema on fetch.
    """

    def __init__(self, base_url: str, cache_ttl_seconds: int = 300):
        ...
```

**Integration with AIGC class:**

```python
class AIGC:
    def __init__(self, *, loader: PolicyLoader | None = None, ...):
        self._loader = loader or FileSystemLoader()
```

When `self._loader` is set, `enforce()` uses `self._loader.load()` instead of the module-level `load_policy()`.

**Tests required:**

- `test_loaders.py` — FileSystemLoader (existing behavior), InMemoryLoader, RemoteLoader (mocked HTTP)
- Custom loader subclass works
- PolicyLoadError raised for missing policy
- Schema validation happens after loading regardless of source

---

### 4.6 Policy Versioning (`aigc/_internal/versioning.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 5 (combined with loaders)

**What it does:** Adds `effective_date` and `expiration_date` to policies so policies can be time-bounded. Expired policies fail governance.

**Public API:**

```python
# In aigc/_internal/versioning.py

from datetime import date
from typing import Any

def validate_policy_version(
    policy: dict[str, Any],
    reference_date: date | None = None,
) -> tuple[bool, str | None]:
    """Check if a policy is valid for the given date.

    Returns (True, None) if valid.
    Returns (False, reason) if expired or not yet effective.

    If reference_date is None, uses today's date.
    """
    ...
```

**Policy DSL extension:**

```yaml
policy_version: "2.1"
effective_date: "2026-01-01"
expiration_date: "2026-12-31"
```

**Integration:** Called in `_run_pipeline()` after policy loading but before guard evaluation. If invalid, raises `PolicyValidationError`.

**Schema changes:** Add `effective_date` and `expiration_date` as optional string fields in `policy_dsl.schema.json` with pattern `"^\\d{4}-\\d{2}-\\d{2}$"`.

**Tests required:**

- `test_versioning.py` — effective before start date, within range, after expiration
- Missing dates → always valid (backward compatible)
- Deterministic with explicit reference_date

---

### 4.7 Custom Enforcement Gate Plugin (`aigc/_internal/gates.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 6

**What it does:** Allows users to inject custom enforcement logic at defined extension points in the pipeline without modifying core code.

**Public API:**

```python
# In aigc/_internal/gates.py (note: existing guards.py is for guard expressions)

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Mapping

class GatePosition(Enum):
    PRE_SCHEMA = "pre_schema"    # After tool validation, before schema validation
    POST_SCHEMA = "post_schema"  # After schema validation, before postconditions

class GateResult:
    """Result of a custom gate evaluation."""

    def __init__(self, passed: bool, message: str = "", metadata: dict | None = None):
        self.passed = passed
        self.message = message
        self.metadata = metadata or {}

class EnforcementGate(ABC):
    """Base class for custom enforcement gates."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique gate identifier (used in gates_evaluated list)."""
        ...

    @property
    @abstractmethod
    def position(self) -> GatePosition:
        """Where in the pipeline this gate runs."""
        ...

    @abstractmethod
    def evaluate(
        self,
        invocation: Mapping[str, Any],
        policy: dict[str, Any],
        context: dict[str, Any],
    ) -> GateResult:
        """Evaluate the gate. Return GateResult.

        MUST NOT suppress core gate exceptions (pipeline short-circuits
        on the first failure; custom gates follow the same semantics).
        MUST be deterministic given same inputs.
        """
        ...
```

**Integration with AIGC class:**

```python
class AIGC:
    def __init__(self, *, custom_gates: list[EnforcementGate] | None = None, ...):
        self._custom_gates = custom_gates or []
```

**Pipeline integration in `_run_pipeline()`:**

```
guards → role → preconditions → risk_scoring → tools
  → [PRE_SCHEMA custom gates]
  → schema
  → [POST_SCHEMA custom gates]
  → postconditions
```

Each custom gate's `name` is appended to `gates_evaluated`. If a gate returns `passed=False`, it raises a `GovernanceViolationError` with the gate's message.

**Isolation guarantees (v0.3.0 release gate):**

Custom gates follow the same **short-circuit semantics** as core gates (see `AIGC_HIGH_LEVEL_DESIGN.md` §6 and §11.3): each gate either passes or raises a typed exception. There is no accumulated-failures model. Specifically:

- Custom gate failure raises `GovernanceViolationError`, short-circuiting the pipeline — identical to core gate behavior
- A FAIL audit artifact is generated and attached to the exception before it propagates (per CLAUDE.md §Audit Artifact Guarantee)
- Custom gate exceptions produce the same audit evidence as core gate exceptions (artifact with `gates_evaluated`, failure reason, checksums)
- Core gates that ran before the custom gate are reflected in `gates_evaluated`; gates after the failure point are not reached

**Tests required:**

- `test_custom_gates_m2.py` — PRE_SCHEMA and POST_SCHEMA execution
- Gate name appears in `gates_evaluated`
- Gate failure produces proper FAIL audit artifact with exception
- Custom gate exception short-circuits pipeline (subsequent gates do not run)
- Custom gate failure artifact is schema-valid and checksum-deterministic
- Determinism: same inputs → same gate evaluation order and outcome

---

### 4.8 OpenTelemetry Integration (`aigc/_internal/otel.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 7 (metrics shown in compliance dashboard)

**What it does:** Emits OpenTelemetry spans and metrics for enforcement operations. Optional dependency: `pip install aigc[opentelemetry]`.

**Public API:**

```python
# In aigc/_internal/otel.py

from typing import Any

def instrument_enforcement(
    tracer_name: str = "aigc.enforcement",
) -> None:
    """Instrument the enforcement pipeline with OpenTelemetry spans.

    Creates spans for:
      - aigc.enforce (root span)
      - aigc.gate.{gate_name} (child spans per gate)
      - aigc.risk_scoring (if risk scoring enabled)
      - aigc.signing (if signing enabled)

    Records attributes:
      - aigc.policy_file
      - aigc.role
      - aigc.enforcement_result (PASS/FAIL)
      - aigc.risk_score (if computed)
      - aigc.failure_gate (if FAIL)
    """
    ...
```

**Integration:** The Streamlit app does **not** run a full OTel collector, so Lab 7 does **not** exercise
real OTel instrumentation at runtime. Instead, Lab 7's compliance dashboard shows a **simulated** trace-style
view reconstructed from audit artifact metadata (gates_evaluated, timestamps, risk_score). This demonstrates
the UX of how OTel data would appear, not the actual instrumentation pipeline.

The real OTel SDK feature (`instrument_enforcement()`) is validated exclusively through unit tests with a
`MockTracer` in `tests/test_otel.py`. Those tests verify span creation, attribute propagation, and no-op
behavior when `opentelemetry` is not installed. This is the true coverage for feature 4.8 — Lab 7's trace
view is a UX mockup only.

**Dependency handling:** Guard all OTel imports behind try/except. If `opentelemetry` is not installed, `instrument_enforcement()` is a no-op that logs a warning.

**Tests required:**

- `test_otel.py` — mock tracer receives expected spans
- No-op when opentelemetry not installed (no ImportError)
- Span attributes match audit artifact fields

---

### 4.9 Policy Testing Framework (`aigc/_internal/testing.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 5 (combined with loaders)

**What it does:** Provides a test harness for policy authors to validate their policies without a full application.

**Public API:**

```python
# In aigc/_internal/testing.py

from typing import Any
import unittest

class PolicyTestCase(unittest.TestCase):
    """Base class for policy tests.

    Usage:
        class TestMedicalPolicy(PolicyTestCase):
            policy_file = "policies/medical_ai.yaml"

            def test_doctor_role_passes(self):
                self.assert_passes(
                    role="doctor",
                    input={"query": "patient symptoms"},
                    output={"result": "diagnosis"},
                    context={"role_declared": True, "schema_exists": True},
                )

            def test_unauthorized_role_fails(self):
                self.assert_fails(
                    role="janitor",
                    expected_gate="role_validation",
                )
    """

    policy_file: str = ""
    model_provider: str = "test"
    model_identifier: str = "test-model"

    def assert_passes(
        self,
        role: str,
        input: dict | None = None,
        output: dict | None = None,
        context: dict | None = None,
    ) -> dict[str, Any]:
        """Assert enforcement passes and return the artifact."""
        ...

    def assert_fails(
        self,
        role: str = "test",
        input: dict | None = None,
        output: dict | None = None,
        context: dict | None = None,
        expected_gate: str | None = None,
        expected_error: type | None = None,
    ) -> dict[str, Any]:
        """Assert enforcement fails and return the FAIL artifact."""
        ...

    def assert_risk_score(
        self,
        role: str,
        context: dict,
        min_score: float | None = None,
        max_score: float | None = None,
    ) -> float:
        """Assert risk score falls within expected range."""
        ...
```

**Tests required:**

- `test_testing_framework.py` — assert_passes, assert_fails, assert_risk_score
- Error messages are helpful when assertions fail
- Works with InMemoryLoader for policies defined inline

---

### 4.10 Compliance Export CLI (`aigc/_internal/export.py`)

**Design Issue:** M2 roadmap
**Wireframe:** Lab 7

**What it does:** Exports audit artifacts from a sink into compliance-ready formats (JSON, CSV, and optionally PDF report bundles).

**Public API:**

```python
# In aigc/_internal/export.py

from pathlib import Path
from typing import Any

def export_artifacts(
    artifacts: list[dict[str, Any]],
    format: str = "json",         # "json" | "csv" | "pdf" (optional) | "bundle"
    output_path: Path | str = ".",
    filters: dict[str, Any] | None = None,
) -> Path:
    """Export artifacts to the specified format.

    Filters:
      - policy_file: str — only artifacts for this policy
      - enforcement_result: "PASS" | "FAIL"
      - date_range: (start_timestamp, end_timestamp)
      - signed_only: bool — only signed artifacts

    Returns path to the generated file or directory.
    """
    ...

def generate_compliance_summary(
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a compliance summary from artifacts.

    Returns:
      - total_count, pass_count, fail_count
      - pass_rate
      - avg_risk_score (if risk scores present)
      - failure_breakdown by gate
      - policies_evaluated (unique list)
      - date_range
      - signing_coverage (% of artifacts signed)
    """
    ...
```

**CLI extension in `aigc/_internal/cli.py`:**

```bash
# New subcommand
aigc audit export --format csv --days 7 --policy medical_ai --output report.csv
aigc audit export --format json --signed-only --output evidence.json
aigc audit summary --days 30
```

**PDF dependency:** PDF export is an optional feature gated behind
`pip install aigc-sdk[pdf]`. The PDF backend is `fpdf2` (MIT-licensed,
pure Python, no system dependencies). Guard the import behind try/except;
if `fpdf2` is not installed, `export_artifacts(format="pdf")` raises
`FeatureNotImplementedError` with an install hint.

**Tests required:**

- `test_export.py` — each format produces valid output
- Filters work correctly
- Summary statistics are accurate
- CSV contains expected columns
- JSON output is schema-valid
- PDF export without `fpdf2` installed raises `FeatureNotImplementedError`

---

## 5. Phase 2 — Shared Streamlit Infrastructure

### 5.1 Dependencies

Add to a new `streamlit_app/requirements.txt`:

```
streamlit>=1.30.0
anthropic>=0.40.0
openai>=1.0.0
pyyaml>=6.0
aigc @ file://../  # Install AIGC from local source
```

### 5.2 Session State (`streamlit_app/shared/state.py`)

```python
"""Centralized session state management."""

import streamlit as st
from aigc import AIGC, JsonFileAuditSink, AuditChain, HMACSigner

def init_state() -> None:
    """Initialize all session state keys with defaults."""
    defaults = {
        # AI configuration
        "ai_provider": "anthropic",       # "anthropic" | "openai"
        "api_key": "",
        "model_id": "claude-sonnet-4-5-20250929",

        # AIGC configuration
        "aigc_instance": None,
        "signer": None,
        "chain": AuditChain(),
        "custom_gates": [],

        # Audit history (in-memory for demo)
        "audit_history": [],

        # Lab-specific state
        "current_lab": "lab1",
        "risk_score_history": [],
        "chain_verified": None,
        "composition_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_aigc() -> AIGC:
    """Get or create the AIGC instance with current configuration."""
    ...

def record_artifact(artifact: dict) -> None:
    """Append artifact to session history only.

    NOTE: Do NOT append to the chain here. The chain is managed exclusively
    by AIGC.enforce() when the AIGC instance is constructed with chain=.
    Appending here would double-count artifacts in the chain, skewing
    chain length and breaking verification demos.

    The session_state.audit_history list is a UI-only view of all artifacts
    for display in the sidebar and compliance dashboard. The chain is the
    SDK's tamper-evident structure and must not be modified outside enforce().
    """
    st.session_state.audit_history.append(artifact)
```

### 5.3 AI Client (`streamlit_app/shared/ai_client.py`)

```python
"""Thin wrapper around Claude/GPT for demo invocations."""

import streamlit as st
from typing import Any

def call_ai(
    prompt: str,
    system: str = "You are a helpful assistant.",
    model: str | None = None,
) -> dict[str, Any]:
    """Call the configured AI provider.

    Returns: {"result": str, "model": str, "usage": dict}

    Uses st.session_state.ai_provider and st.session_state.api_key.
    If no API key is configured, returns a mock response for demo purposes.
    """
    ...

def mock_ai_response(prompt: str) -> dict[str, Any]:
    """Generate a deterministic mock response (no API key needed)."""
    return {
        "result": f"[Mock response to: {prompt[:50]}...]",
        "model": "mock-model",
        "usage": {"input_tokens": len(prompt.split()), "output_tokens": 20},
    }
```

### 5.4 Artifact Display (`streamlit_app/shared/artifact_display.py`)

A reusable Streamlit component that renders an audit artifact as an expandable card. Used across all labs.

```python
"""Reusable audit artifact viewer."""

import streamlit as st
from typing import Any

def render_artifact(artifact: dict[str, Any], expanded: bool = False) -> None:
    """Render an audit artifact as a Streamlit card.

    Shows:
      - PASS/FAIL badge (green/red)
      - Policy file, role, model
      - Risk score gauge (if present)
      - Signature status (if present)
      - Chain position (if present)
      - Expandable: full artifact JSON
      - Expandable: gates_evaluated list
      - Expandable: failures list (if FAIL)
    """
    ...

def render_artifact_diff(a: dict, b: dict) -> None:
    """Render a side-by-side diff of two artifacts."""
    ...

def render_risk_gauge(score: float, threshold: float) -> None:
    """Render a visual risk score gauge.

    Shows a horizontal bar from 0.0 to 1.0 with:
      - Green zone: 0.0 to threshold
      - Red zone: threshold to 1.0
      - Marker at the current score
    """
    ...
```

### 5.5 Policy Editor (`streamlit_app/shared/policy_editor.py`)

```python
"""YAML policy editor with live validation."""

import streamlit as st

def render_policy_editor(
    default_policy: str = "",
    key: str = "policy_editor",
    height: int = 300,
) -> dict | None:
    """Render a YAML editor with live validation.

    Returns parsed policy dict if valid, None if invalid.
    Shows validation errors inline.
    """
    ...

def render_policy_selector(
    policy_dir: str = "streamlit_app/sample_policies",
    key: str = "policy_selector",
) -> str:
    """Dropdown to select from sample policies. Returns file path."""
    ...
```

### 5.6 App Shell (`streamlit_app/app.py`)

**Wireframe reference:** Wireframe 1 (App Shell + Navigation)

```python
"""AIGC Milestone 2 Demo — Entry Point"""

import streamlit as st
from shared.state import init_state

st.set_page_config(
    page_title="AIGC Governance Lab",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()

# Sidebar: Lab navigation
LABS = {
    "lab1": ("1. Risk Scoring", "labs.lab1_risk_scoring"),
    "lab2": ("2. Signing & Verification", "labs.lab2_signing"),
    "lab3": ("3. Audit Chain", "labs.lab3_chain"),
    "lab4": ("4. Policy Composition", "labs.lab4_composition"),
    "lab5": ("5. Loaders & Versioning", "labs.lab5_loaders"),
    "lab6": ("6. Custom Gates", "labs.lab6_custom_gates"),
    "lab7": ("7. Compliance Dashboard", "labs.lab7_compliance"),
}

with st.sidebar:
    st.title("AIGC Governance Lab")
    st.caption("Milestone 2 Demo App")
    st.divider()

    for key, (label, _) in LABS.items():
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.current_lab = key

    st.divider()

    # AI Provider config
    st.subheader("AI Configuration")
    st.session_state.ai_provider = st.selectbox(
        "Provider", ["anthropic", "openai", "mock"],
    )
    if st.session_state.ai_provider != "mock":
        st.session_state.api_key = st.text_input(
            "API Key", type="password",
        )

# Main content: render selected lab with optional guide rail
from shared.guide_rail import render_lab_guide

current = st.session_state.current_lab
module_path = LABS[current][1]
module = __import__(module_path, fromlist=["render", "get_guide"])

# Lab 7 uses full-width (no guide rail); all others get 75/25 split
if current == "lab7" or not hasattr(module, "get_guide"):
    module.render()
else:
    lab_col, guide_col = st.columns([3, 1])
    with lab_col:
        module.render()
    with guide_col:
        render_lab_guide(module.get_guide())
```

### 5.7 Lab Guide Rail (`streamlit_app/shared/guide_rail.py`)

**Wireframe references:** Wireframe 9 (Layout Integration), 10 (Linear Stepper), 11 (Workflow Cards), 12 (Iterative + Milestone), 13 (Cookbook)

An in-app contextual guide panel that tells users what to do, how to do it, and what to expect in each lab. Rendered in a right-side column alongside the lab content using `st.columns([3, 1])` (75% lab, 25% guide rail).

#### 5.7.1 Data Model

```python
"""Lab guide rail — contextual help system for each lab."""

import streamlit as st
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class GuideStep:
    """A single step in a lab guide."""
    title: str                              # e.g. "Choose a policy"
    instruction: str                        # What to do
    what_to_expect: str                     # What happens after this step
    completion_key: str | None = None       # session_state key that marks completion
    show_me: Callable | None = None         # Pre-fill callback for "Show Me" button

@dataclass
class GuideWorkflow:
    """A named workflow containing ordered steps (for branching labs)."""
    name: str                               # e.g. "Sign an Artifact"
    description: str                        # 1-line summary
    steps: list[GuideStep] = field(default_factory=list)

@dataclass
class GuideRecipe:
    """A code recipe for cookbook-mode labs."""
    name: str                               # e.g. "PII Detection Gate"
    description: str                        # What this recipe demonstrates
    code: str                               # Pre-written code to load
    what_it_demonstrates: str               # SDK concepts covered

@dataclass
class LabGuide:
    """Complete guide configuration for one lab."""
    lab_id: str                             # e.g. "lab1"
    title: str                              # e.g. "Risk Scoring Engine"
    overview: str                           # 1-line purpose summary
    mode: str                               # "linear" | "workflows" | "iterative" | "cookbook"
    steps: list[GuideStep] | None = None            # For "linear" mode
    workflows: list[GuideWorkflow] | None = None    # For "workflows" mode
    recipes: list[GuideRecipe] | None = None        # For "cookbook" mode
    iteration_target: int | None = None             # For "iterative" mode milestone
    glossary: dict[str, str] | None = None          # Term -> definition
```

#### 5.7.2 Display Modes

Each lab's guide rail renders in one of four modes, selected by the `mode` field:

**Linear Stepper** (`mode="linear"`) — Labs 1, 4:
Vertical numbered steps with completion dots (green = done, blue = active, grey = upcoming). Each step shows
title, instruction, and "what to expect." A "Show Me" button on the active step pre-fills the lab form with
known-good values. Steps unlock sequentially based on `completion_key` presence in `st.session_state`.

**Workflow Cards** (`mode="workflows"`) — Labs 2, 5:
User selects from a list of workflow cards (e.g., "Sign an Artifact", "Tamper Detection", "Key Rotation"). Selecting a card expands its steps as a linear sub-stepper. Each workflow is independent — no cross-workflow ordering. Lab 5 variant: workflows map to the loader tabs (YAML, JSON, env-var, programmatic).

**Iterative + Milestone** (`mode="iterative"`) — Lab 3:
A repeating 3-step cycle (configure → enforce → inspect) with a milestone progress bar (e.g., "2 / 5 linked artifacts"). A chain history section shows completed links. The `previous_artifact_id` is auto-linked from the last chain entry. Milestone target is configurable via `iteration_target`.

**Cookbook** (`mode="cookbook"`) — Lab 6:
A list of named recipes, each with a description, pre-written code, and a "Load" button. Loading a recipe
pre-fills the lab's code editor. No ordering constraint — user can explore recipes in any sequence. A "What
it demonstrates" section ties each recipe back to SDK concepts (CustomGate.evaluate(), short-circuit
semantics, etc.).

#### 5.7.3 Shared Renderer

```python
def render_lab_guide(guide: LabGuide) -> None:
    """Render the guide rail for a lab.

    Call this inside the right column of st.columns([3, 1]).
    Dispatches to the appropriate renderer based on guide.mode.

    Layout:
      - Toggle button: "Hide Guide" / "Show Guide"
      - Overview: 1-line lab purpose
      - Mode-specific content (stepper / cards / milestone / recipes)
      - "Show Me" or "Load" buttons (with confirmation if user has input)
      - Glossary expander (if guide.glossary is non-empty)
    """
    # Toggle visibility
    visible_key = f"guide_visible_{guide.lab_id}"
    if visible_key not in st.session_state:
        st.session_state[visible_key] = True

    if st.button(
        "Hide Guide" if st.session_state[visible_key] else "Show Guide",
        key=f"guide_toggle_{guide.lab_id}",
    ):
        st.session_state[visible_key] = not st.session_state[visible_key]

    if not st.session_state[visible_key]:
        return

    st.caption(guide.overview)

    if guide.mode == "linear":
        _render_linear(guide)
    elif guide.mode == "workflows":
        _render_workflows(guide)
    elif guide.mode == "iterative":
        _render_iterative(guide)
    elif guide.mode == "cookbook":
        _render_cookbook(guide)

    if guide.glossary:
        with st.expander("Glossary"):
            for term, definition in guide.glossary.items():
                st.markdown(f"**{term}:** {definition}")
```

#### 5.7.4 Post-Action Inline Annotations

After a user completes a step, the lab content area shows a brief contextual hint using `st.caption()`. These hints clear on the next Streamlit rerun. They are not part of the guide rail column — they appear inline in the lab content to provide immediate feedback tied to the user's action.

Example: after a user adjusts a risk signal weight, the lab shows: *"Hint: Each signal's weight affects the final composite score. Try setting 'domain' to 0.8."*

#### 5.7.5 "Show Me" Confirmation

When a user clicks "Show Me" (linear/workflow modes) or "Load" (cookbook mode) and the lab form already has user-provided input, a confirmation dialog appears:

```
Pre-fill with sample values? You have unsaved input.
[Yes, pre-fill]  [Keep mine]
```

This prevents accidental data loss. If the form is empty, "Show Me" pre-fills immediately.

#### 5.7.6 Edge Cases

**State persistence:** Guide rail state (which step is active, which workflow is selected, milestone progress) persists in `st.session_state` keyed by `guide_{lab_id}_*`. Switching labs preserves each lab's guide rail state.

**Narrow screens:** If viewport width < 768px, the guide rail auto-collapses and shows only the toggle button. On expand, it renders below the lab content (full-width) instead of beside it.

**First-time vs returning:** On first visit to a lab (no `completion_key` values set), the guide rail starts expanded. On return visits where at least one step is complete, it starts collapsed with a "Resume from step N" indicator.

**Cross-lab dependencies:** Lab 3 depends on Lab 2 output (signing). If the user enters Lab 3 without having completed signing setup, the guide rail shows a callout: *"This lab uses signed artifacts from Lab 2. Set up signing first."* with a link to Lab 2.

**Lab 7 (Compliance Dashboard):** No guide rail. Lab 7 is read-only and self-explanatory. The 25% column is not allocated; Lab 7 uses full-width layout.

#### 5.7.7 Lab-to-Mode Mapping

| Lab | Mode | Reason |
|-----|------|--------|
| Lab 1 — Risk Scoring | `linear` | Fixed step sequence: pick policy → configure signals → enforce → inspect |
| Lab 2 — Signing | `workflows` | Three independent workflows: sign, tamper-detect, key-rotate |
| Lab 3 — Audit Chain | `iterative` | Repeating cycle building a linked chain to milestone |
| Lab 4 — Policy Composition | `linear` | Fixed sequence: load parent → load child → compose → enforce |
| Lab 5 — Loaders | `workflows` | Each loader tab is an independent workflow |
| Lab 6 — Custom Gates | `cookbook` | User explores recipe code, no ordering required |
| Lab 7 — Compliance | *(none)* | Dashboard — full-width, no guide rail |

---

## 6. Phase 3 — Lab Implementations

### 6.1 Lab 1: Risk Scoring Engine

**Wireframe reference:** Wireframe 2
**M2 features exercised:** Risk Scoring Engine (4.1)

**Layout (top to bottom):**

1. **Header:** "Lab 1: Risk Scoring Engine" with mode selector (`strict` / `risk_scored` / `warn_only`)
2. **Two columns:**
   - Left: Policy editor (pre-loaded with `medical_ai.yaml` that has `risk_scoring` config), prompt input textarea, "Run Enforcement" button
   - Right: Risk gauge visualization, signal breakdown table, enforcement result
3. **Bottom:** Audit artifact card (via `render_artifact`)

**User flow:**

1. User selects enforcement mode
2. User optionally edits policy signals (weights, rules)
3. User types a prompt (or uses a preset scenario)
4. User clicks "Run Enforcement"
5. App calls AI (or mock), builds invocation, runs `aigc.enforce()`
6. Risk gauge animates to computed score
7. Signal breakdown shows each signal's name, weight, value, and reason
8. Artifact card shows full result with risk_score populated

**Preset scenarios (buttons):**

- "Low Risk: Simple FAQ" — score ~0.1
- "Medium Risk: Medical Advice" — score ~0.5
- "High Risk: Drug Interaction" — score ~0.85
- "Custom" — user defines everything

**Implementation file:** `streamlit_app/labs/lab1_risk_scoring.py`

```python
def render():
    st.header("Lab 1: Risk Scoring Engine")
    ...
```

---

### 6.2 Lab 2: Signing & Verification

**Wireframe reference:** Wireframe 5
**M2 features exercised:** Audit Artifact Signing (4.2)

**Layout:**

1. **Header:** "Lab 2: Signing & Verification"
2. **Key Configuration:** Input field for HMAC secret key, "Generate Key" button (random 32-byte hex), current key display
3. **Two columns:**
   - Left: "Sign" panel — Run a governed invocation, sign the artifact, show signature hex
   - Right: "Verify" panel — paste/load an artifact JSON, verify against key, show pass/fail
4. **Tamper Demo:** Button that modifies one byte of a signed artifact and re-verifies (shows failure)
5. **Bottom:** Before/after artifact comparison (via `render_artifact_diff`)

**Implementation file:** `streamlit_app/labs/lab2_signing.py`

---

### 6.3 Lab 3: Audit Chain

**Wireframe reference:** Wireframe 4
**M2 features exercised:** Tamper-Evident Audit Chain (4.3)

**Layout:**

1. **Header:** "Lab 3: Tamper-Evident Audit Chain"
2. **Chain Builder:** "Run & Append" button that runs enforcement and adds to the chain. Shows chain as a visual linked list (boxes with arrows, each showing sequence number, artifact checksum prefix, and chain checksum prefix)
3. **Chain Stats:** Length, genesis checksum, head checksum
4. **Integrity Check:** "Verify Chain" button → green checkmark or red X at broken link
5. **Tamper Simulation:** "Tamper with Link #N" dropdown + button → modifies an artifact, re-runs verify, highlights the broken link in red
6. **Chain Export:** "Export Chain" button → JSON download

**Visual chain rendering:** Each link is a card showing:
- `#1` sequence badge
- `artifact: a4f2...c8b1` (first 4, last 4 of checksum)
- `prev: null` or `prev: b3e1...d9a2`
- `chain: c7d4...e1f3`
- Arrow pointing to next link

**Implementation file:** `streamlit_app/labs/lab3_chain.py`

---

### 6.4 Lab 4: Policy Composition

**Wireframe reference:** Wireframe 3
**M2 features exercised:** Policy Composition Restriction (4.4)

**Layout:**

1. **Header:** "Lab 4: Policy Composition"
2. **Two columns (parent + child):**
   - Left: "Base Policy" — editor pre-loaded with `medical_ai.yaml`
   - Right: "Child Policy" — editor pre-loaded with `medical_ai_child.yaml` (has `_merge` directives)
3. **Merge Strategy Panel:** Dropdown per field (roles, tools, pre_conditions, output_schema) showing `intersect` / `union` / `replace`
4. **"Compose" button** → shows effective policy in a third panel below
5. **Escalation Check:** "Check for Privilege Escalation" button → shows violations or "No escalation detected"
6. **Diff View:** Highlights what changed between base and effective policy (roles removed, preconditions added, etc.)

**Implementation file:** `streamlit_app/labs/lab4_composition.py`

---

### 6.5 Lab 5: Loaders & Versioning

**Wireframe reference:** (uses app shell wireframe; no dedicated wireframe)
**M2 features exercised:** Pluggable Policy Loader (4.5), Policy Versioning (4.6), Policy Testing Framework (4.9)

**Layout:**

1. **Header:** "Lab 5: Loaders, Versioning & Testing"
2. **Loader Tab:**
   - Dropdown: "FileSystem" / "InMemory" / "Remote (mocked)"
   - For InMemory: inline editor to define policies by name
   - "Load Policy" button → shows parsed policy
3. **Versioning Tab:**
   - Policy editor with `effective_date` / `expiration_date` fields
   - Date picker for "reference date" (simulate checking on a different day)
   - "Validate Version" button → shows valid/expired/not-yet-effective
4. **Testing Tab:**
   - Policy selector + inline test case editor
   - Pre-built test cases (pass, fail, risk score range)
   - "Run Tests" button → shows unittest-style results (green dots / red Fs)

**Implementation file:** `streamlit_app/labs/lab5_loaders.py`

---

### 6.6 Lab 6: Custom Enforcement Gates

**Wireframe reference:** Wireframe 6
**M2 features exercised:** Custom Enforcement Gate Plugin (4.7)

**Layout:**

1. **Header:** "Lab 6: Custom Enforcement Gates"
2. **Gate Builder:**
   - Gate name input
   - Position selector: `PRE_SCHEMA` / `POST_SCHEMA`
   - Gate logic editor (Python code textarea with a template):
     ```python
     def evaluate(self, invocation, policy, context):
         # Your custom gate logic here
         if invocation["output"].get("confidence", 1.0) < 0.5:
             return GateResult(passed=False, message="Low confidence output")
         return GateResult(passed=True)
     ```
   - "Register Gate" button
3. **Pipeline Visualization:** Shows the current pipeline order as a vertical flowchart with the custom gate inserted at the correct position. Boxes colored by type (blue=core, purple=custom).
4. **Test Run:** Standard prompt input + "Run with Custom Gate" button
5. **Result:** Shows artifact with custom gate in `gates_evaluated`, plus gate-specific metadata

**Safety note:** The Python code editor does **not** use `exec()`. Instead, user-provided gate logic is parsed via `ast.parse()` and validated against an allowlist of safe AST node types before execution. The validator rejects:

- Import statements (`ast.Import`, `ast.ImportFrom`)
- Attribute access on disallowed modules (`os`, `sys`, `subprocess`, `socket`, `shutil`, `pathlib`, `io`, `builtins`)
- Calls to `open()`, `eval()`, `exec()`, `compile()`, `__import__()`
- Dunder attribute access (`__class__`, `__subclasses__`, etc.)

Only `GateResult`, `GatePosition`, and `EnforcementGate` are injected into the execution namespace. The AST validation function is `validate_gate_ast()` in `streamlit_app/shared/gate_sandbox.py`.

**Limitation acknowledged:** Even with AST filtering, Python sandboxing is not fully secure against
determined attackers (e.g., attribute introspection chains). The app displays a prominent warning banner:
"Custom gate code runs in a restricted sandbox. Do not paste untrusted code." This is a demo environment —
production custom gates should use a process-level sandbox or WASM runtime.

The `validate_gate_ast()` function itself must have its own test file (`tests/test_gate_sandbox.py`) covering bypass attempts: import smuggling, dunder traversal, `type()` tricks, and `getattr()` indirection.

**Implementation file:** `streamlit_app/labs/lab6_custom_gates.py`

---

### 6.7 Lab 7: Compliance Dashboard

**Wireframe reference:** Wireframe 7
**M2 features exercised:** Compliance Export CLI (4.10), OpenTelemetry Integration (4.8 — **simulated display only**, see note below)

**Layout:**

1. **Header:** "Lab 7: Compliance Dashboard"
2. **Summary Stats Row:** Total audits, PASS count (%), FAIL count (%), avg risk score — all computed from `st.session_state.audit_history`
3. **Report Configuration:**
   - Date range selector (last 24h / 7d / 30d / custom)
   - Policy filter dropdown (populated from audit history)
   - Status filter (All / PASS / FAIL)
4. **Export Format Selector:** JSON / CSV / PDF Report / Evidence Bundle (styled as button group, active one highlighted)
5. **"Export" button** → generates file and provides download link via `st.download_button`
6. **Audit Trail Table:** Sortable table showing timestamp, policy, result (color-coded), risk score, checksum (truncated), signed (Y/N)
7. **CLI Equivalent:** Dark terminal-style box showing the equivalent `aigc audit export` command

**Implementation file:** `streamlit_app/labs/lab7_compliance.py`

---

## 7. Phase 4 — Integration & Testing

### 7.1 Sample Policies

Create these in `streamlit_app/sample_policies/`:

**`medical_ai.yaml`**
```yaml
policy_version: "2.0"
effective_date: "2026-01-01"
expiration_date: "2026-12-31"
description: "Medical AI governance with risk scoring"

roles:
  - doctor
  - nurse
  - admin
  - researcher

risk_scoring:
  mode: "risk_scored"
  threshold: 0.7
  signals:
    - name: "sensitive_domain"
      weight: 0.4
      rule: "context.domain == 'medical'"
    - name: "model_capability"
      weight: 0.3
      rule: "'gpt-4' in model_identifier or 'opus' in model_identifier"
    - name: "no_human_review"
      weight: 0.3
      rule: "not context.human_review_required"

pre_conditions:
  required:
    role_declared:
      type: "boolean"
    schema_exists:
      type: "boolean"

post_conditions:
  required:
    - output_schema_valid

output_schema:
  type: object
  properties:
    result:
      type: string
  required:
    - result

tools:
  allowed_tools:
    - name: "search_medical_db"
      max_calls: 5
    - name: "lookup_drug_interaction"
      max_calls: 3
```

**`medical_ai_child.yaml`**
```yaml
extends: "medical_ai.yaml"
policy_version: "2.0-restricted"
description: "Restricted medical AI - nurses only, no drug interactions"

_merge:
  roles: "intersect"
  tools: "intersect"
  pre_conditions: "union"

roles:
  - nurse

tools:
  allowed_tools:
    - name: "search_medical_db"
      max_calls: 3
```

**`finance_ai.yaml`** — similar structure with finance-specific signals

**`content_moderation.yaml`** — content safety policy with strict mode

**`high_risk.yaml`** — policy with threshold=0.3 for demonstrating aggressive risk blocking

### 7.2 Test Plan

Create `streamlit_app/tests/` with:

- `test_shared.py` — state initialization, AI client mock, artifact display rendering
- `test_lab_integration.py` — each lab can render without crashing (Streamlit testing via `streamlit.testing`)
- `test_sample_policies.py` — all sample policies pass schema validation

### 7.3 SDK Test Requirements (in `tests/`)

For each M2 feature, create test files that satisfy the v0.3.0 release gates:

| Gate | Test File | What It Verifies |
|------|-----------|-----------------|
| Risk score determinism | `test_risk_scoring.py` | Same invocation → same score × 1000 runs |
| Signature round-trip | `test_signing.py` | Sign → verify passes; tamper → verify fails |
| Policy restriction | `test_composition_m2.py` | Intersect roles ⊆ base; 100 adversarial compositions |
| No privilege escalation | `test_composition_m2.py` | Fuzzer: random child cannot grant roles/tools not in base |
| Custom gate isolation | `test_custom_gates_m2.py` | Throwing gate doesn't suppress core failures |

### 7.4 Documentation Parity

Per CLAUDE.md rules, these documents must be updated when M2 ships:

1. `CLAUDE.md` — module layout (add new files), pipeline contract (add GATE_RISK, custom gate positions), current state (version → 0.3.0, test count, coverage)
2. `README.md` — test count, new features list, public API additions
3. `PROJECT.md` — architecture overview, new modules, feature list
4. `docs/AIGC_FRAMEWORK.md` — enforcement pipeline description with new gates
5. `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` — pipeline diagram update
6. `doc_parity_manifest.yaml` — version, test count, audit schema version
7. `CHANGELOG.md` — v0.3.0 release notes

Run `python scripts/check_doc_parity.py` before considering M2 complete.

### 7.5 Schema Updates Summary

**`schemas/policy_dsl.schema.json`** — add:
- `risk_scoring` object (mode, threshold, signals array)
- `_merge` object (field-name → merge strategy)
- `effective_date` string (date pattern)
- `expiration_date` string (date pattern)

**`schemas/audit_artifact.schema.json`** — already supports `risk_score` and `signature` as nullable fields. Add:
- `failure_gate` enum: add `"risk_scoring"` to the list

### 7.6 ADRs Required

Per CLAUDE.md, these changes require ADRs in `docs/decisions/`:

- **ADR-0011: Risk Scoring Gate Addition** — adds GATE_RISK to pipeline, changes gate ordering
- **ADR-0012: Custom Enforcement Gate Plugin Interface** — new extension points in pipeline
- **ADR-0013: Policy Composition Restriction Semantics** — `_merge` directive behavior
- **ADR-0014: Audit Artifact Signing** — signing process, verification contract
- **ADR-0015: Tamper-Evident Audit Chain** — chain structure, hash computation

---

## 8. Build Sequence (Step-by-Step for Claude Code)

This is the exact order of operations. Each step should be a committable unit.

### Step 1: Risk Scoring Engine
1. Create `aigc/_internal/risk.py` with `RiskSignal`, `RiskScore`, `compute_risk_score()`
2. Add `GATE_RISK` to `aigc/_internal/enforcement.py`
3. Integrate into `_run_pipeline()` after preconditions, before tools
4. Update `schemas/policy_dsl.schema.json` with `risk_scoring` property
5. Write `tests/test_risk_scoring.py` (determinism, modes, edge cases)
6. Add golden replay fixture for risk scoring
7. Re-export from `aigc/__init__.py`: `RiskScore`, `RiskSignal`, `compute_risk_score`

### Step 2: Audit Artifact Signing
1. Create `aigc/_internal/signing.py` with `AuditSigner`, `HMACSigner`, `sign_artifact()`, `verify_artifact()`
2. Add `signer` parameter to `AIGC.__init__()`
3. Integrate into `AIGC.enforce()` — sign after artifact generation, before sink emission
4. Write `tests/test_signing.py` (round-trip, tamper, constant-time)
5. Re-export from `aigc/__init__.py`: `AuditSigner`, `HMACSigner`, `sign_artifact`, `verify_artifact`

### Step 3: Tamper-Evident Audit Chain
1. Create `aigc/_internal/chain.py` with `ChainLink`, `AuditChain`
2. Add `chain` parameter to `AIGC.__init__()`
3. Integrate into `AIGC.enforce()` — append after signing, before sink emission
4. Write `tests/test_chain.py` (append, verify, tamper, thread safety, export)
5. Re-export from `aigc/__init__.py`: `AuditChain`, `ChainLink`

### Step 4: Policy Composition
1. Create `aigc/_internal/composition.py` with `compose_policies()`, `validate_no_escalation()`
2. Integrate with `aigc/_internal/policy_loader.py` — route all `extends` paths through `compose_policies()` (with `_merge`: per-field strategies; without `_merge`: v0.2.0 legacy merge + `validate_no_escalation()`)
3. Update `schemas/policy_dsl.schema.json` with `_merge` property
4. Write `tests/test_composition_m2.py` (merge strategies, escalation detection, adversarial fuzzing)
5. Re-export from `aigc/__init__.py`: `compose_policies`, `validate_no_escalation`

### Step 5: Pluggable Loaders + Versioning
1. Create `aigc/_internal/loaders.py` with `PolicyLoader`, `FileSystemLoader`, `InMemoryLoader`, `RemoteLoader`
2. Create `aigc/_internal/versioning.py` with `validate_policy_version()`
3. Add `loader` parameter to `AIGC.__init__()`
4. Integrate versioning into `_run_pipeline()` after policy load
5. Update `schemas/policy_dsl.schema.json` with date fields
6. Write `tests/test_loaders.py` and `tests/test_versioning.py`
7. Re-export from `aigc/__init__.py`

### Step 6: Custom Enforcement Gates
1. Create `aigc/_internal/gates.py` with `GatePosition`, `GateResult`, `EnforcementGate`
2. Add `custom_gates` parameter to `AIGC.__init__()`
3. Integrate into `_run_pipeline()` at PRE_SCHEMA and POST_SCHEMA positions
4. Write `tests/test_custom_gates_m2.py` (execution, isolation, determinism)
5. Re-export from `aigc/__init__.py`

### Step 7: OpenTelemetry Integration
1. Create `aigc/_internal/otel.py` with `instrument_enforcement()`
2. Add `opentelemetry` to optional dependencies in `pyproject.toml`
3. Write `tests/test_otel.py` (mock tracer, no-op when missing)
4. Re-export from `aigc/__init__.py`

### Step 8: Policy Testing Framework
1. Create `aigc/_internal/testing.py` with `PolicyTestCase`
2. Create `aigc/testing.py` public re-export
3. Write `tests/test_testing_framework.py`
4. Re-export from `aigc/__init__.py`

### Step 9: Compliance Export
1. Create `aigc/_internal/export.py` with `export_artifacts()`, `generate_compliance_summary()`
2. Extend `aigc/_internal/cli.py` with `aigc audit export` and `aigc audit summary` subcommands
3. Write `tests/test_export.py`
4. Re-export from `aigc/__init__.py`

### Step 10: Streamlit App — Shared Infrastructure
1. Create `streamlit_app/` directory structure
2. Create `streamlit_app/requirements.txt`
3. Implement `shared/state.py`, `shared/ai_client.py`, `shared/artifact_display.py`, `shared/policy_editor.py`
4. Implement `app.py` with navigation shell
5. Create sample policies in `streamlit_app/sample_policies/`

### Step 11: Streamlit App — Labs
1. Implement `lab1_risk_scoring.py`
2. Implement `lab2_signing.py`
3. Implement `lab3_chain.py`
4. Implement `lab4_composition.py`
5. Implement `lab5_loaders.py`
6. Implement `lab6_custom_gates.py`
7. Implement `lab7_compliance.py`

### Step 12: Documentation & Parity
1. Write ADRs (0011–0015)
2. Update CLAUDE.md, README.md, PROJECT.md, framework docs
3. Update `doc_parity_manifest.yaml`
4. Run `python scripts/check_doc_parity.py`
5. Update golden replay fixtures

### Step 13: Final Verification
1. Run full test suite: `python -m pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90`
2. Run schema validation: all policies + audit artifacts
3. Run lint: `flake8 aigc` + `npx markdownlint-cli2 "**/*.md"`
4. Run Streamlit app: `streamlit run streamlit_app/app.py` — verify all 7 labs render and function
5. Verify v0.3.0 release gates (Section 7.3)

---

## 9. Invariants & Constraints

These rules from CLAUDE.md apply throughout implementation:

1. **All governance routes through `enforce_invocation()`** — no bypass paths
2. **Fail closed on any violation** — never silently allow
3. **Deterministic** — same inputs → same audit checksums
4. **Every enforcement attempt produces an audit artifact** — on PASS the artifact is returned; on FAIL or
   exception the artifact is generated before the exception propagates and is attached via
   `exc.audit_artifact` (per CLAUDE.md §Audit Artifact Guarantee and `AIGC_HIGH_LEVEL_DESIGN.md` §6.1
   item 7, §11.3 invariant 1)
5. **Public API boundary** — only `aigc.*` exports are public; `aigc._internal.*` is private
6. **Policy-driven** — no hardcoded governance rules in business logic
7. **Golden replay contract** — behavior changes require replay + ADR updates
8. **No randomness in governance logic** — including risk scoring

---

## 10. Wireframe Checkpoint References

These Excalidraw checkpoints correspond to each wireframe created during design:

| Wireframe | Lab | Checkpoint ID |
|-----------|-----|---------------|
| 1. App Shell + Navigation | All | `b6a20565afce4d069c` |
| 2. Risk Scoring Engine | Lab 1 | `4dce4721b79d47eda5` |
| 3. Policy Composition | Lab 4 | `40c81f9d2334441182` |
| 4. Audit Chain | Lab 3 | `42acb6bd34b74e0a9a` |
| 5. Signing & Verification | Lab 2 | `62ffa016cd2349ad97` |
| 6. Custom Enforcement Gates | Lab 6 | `e4e7feae43d74553be` |
| 7. Compliance Dashboard | Lab 7 | `e8b232264825461daa` |
| 8. Policy Loaders & Versioning | Lab 5 | `32fd586c95fc42d1ac` |
| 9. Guide Rail — Layout Integration | All | `94da3161e9bf46a29b` |
| 10. Guide Rail — Linear Stepper Mode | Labs 1, 4 | `7d5bdf227a874326a9` |
| 11. Guide Rail — Workflow Cards Mode | Labs 2, 5 | `1e9f5418573d4b4c93` |
| 12. Guide Rail — Iterative + Milestone Mode | Lab 3 | `8dbfbdc702614ca884` |
| 13. Guide Rail — Cookbook Mode | Lab 6 | `d4873b40a40a401db1` |
