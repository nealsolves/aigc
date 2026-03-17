# AIGC Governance Lab — Project Documentation

## Project Overview

The AIGC Governance Lab is a Streamlit-based interactive demo application for the AIGC (AI Governance and Compliance) SDK. It provides seven self-contained labs that demonstrate every major capability of the SDK's enforcement pipeline — risk scoring, cryptographic signing, tamper-evident audit chains, policy composition, pluggable loaders, custom gates, and compliance reporting.

The app is designed to run entirely offline using deterministic mock responses, making it suitable for demos, onboarding, and governance workflow prototyping without API token costs.

**Version:** v0.3.0 (Milestone 2)
**Framework:** Streamlit ≥ 1.30
**Runtime:** Python 3.10+

## Architecture

### Entry Point

`app.py` is the single entry point. It configures Streamlit page settings, bootstraps session state, renders sidebar navigation with audit statistics, and dynamically imports the selected lab module.

```
app.py
  → shared/state.py        (init_state, get_aigc factory)
  → labs/lab{N}_*.py        (dynamic import via importlib)
  → shared/guide_rail.py    (right-column contextual help)
```

### Execution Flow

Every lab follows a consistent pattern:

1. **Scenario selection** — User picks a mock scenario from `shared/ai_client.py` (preset prompts, outputs, and context dicts).
2. **Invocation assembly** — `InvocationBuilder` from the AIGC SDK constructs a standardized invocation dict.
3. **Enforcement** — `AIGC.enforce(invocation)` runs the full governance pipeline: guards → role validation → preconditions → tool constraints → schema validation → postconditions → risk scoring → custom gates → audit generation.
4. **Result display** — The audit artifact is rendered with PASS/FAIL badge, risk gauge, signal breakdown, and raw JSON.
5. **Audit sink** — A `CallbackAuditSink` appends every artifact to `st.session_state.audit_history`, feeding the Compliance Dashboard (Lab 7).

### Session State Management

`shared/state.py` centralizes all session state. `init_state()` is called on every rerun and only sets keys that don't yet exist — safe for Streamlit's rerun model. Key state categories:

- **Navigation** — `current_lab` tracks the active lab.
- **AIGC objects** — `signer` (HMACSigner), `chain` (AuditChain), `custom_gates` (list).
- **Audit history** — `audit_history` is an in-memory list of all artifacts.
- **Per-lab state** — Each lab has dedicated keys (e.g., `lab1_last_artifact`, `lab2_signed_artifact`).

`get_aigc(**overrides)` builds a fresh AIGC instance per call. This prevents cross-lab pollution — each lab can swap signers, gates, and risk config without side effects.

### Mock AI Client

`shared/ai_client.py` provides `SCENARIOS`, a dict keyed by scenario name containing pre-built prompt/output/context tuples. Scenarios are designed to trigger specific governance outcomes:

- `low_risk_faq` — Simple nutrition question, all context flags true.
- `high_risk_drug_interaction` — Drug interaction query with `human_review_required: False`.
- `gate_pii_present` — Output contains email and SSN to trigger PII detection.
- `gate_low_confidence` — Output includes `confidence: 0.3` to trigger the confidence gate.

No real API calls are ever made.

## Lab Details

### Lab 1: Risk Scoring Engine

**File:** `labs/lab1_risk_scoring.py`
**Guide mode:** linear

Demonstrates factor-based risk scoring. Users pick from three preset scenarios (low/medium/high risk) and toggle between three risk modes:

- **strict** — Score above threshold fails enforcement immediately.
- **risk_scored** — Score is recorded and enforced; scores at or below threshold pass.
- **warn_only** — Score is recorded but never blocks.

The policy uses five medical risk factors: `no_output_schema`, `broad_roles`, `missing_guards`, `external_model`, `no_preconditions`. Renders a color-coded risk gauge and signal breakdown table.

### Lab 2: Signing & Verification

**File:** `labs/lab2_signing.py`
**Guide mode:** workflows (3 workflows: Sign, Tamper Detection, Key Rotation)

Demonstrates HMAC-SHA256 artifact signing. Users generate a 32-byte random key, run enforcement to produce a signed artifact, then verify the signature. The tamper detection workflow flips the `enforcement_result` field in-place and re-verifies — showing that any modification invalidates the signature. Key rotation demonstrates cross-key verification failure.

Uses `aigc.signing.sign_artifact` and `verify_artifact` directly.

### Lab 3: Tamper-Evident Audit Chain

**File:** `labs/lab3_chain.py`
**Guide mode:** iterative (target: 5 artifacts)

Builds a hash-linked chain of audit artifacts. Each "Run & Append" call enforces a scenario and appends the resulting artifact to an `AuditChain`. The chain visualization shows each link with its checksum and previous_audit_checksum. Users can tamper with any link (flipping its enforcement_result) and verify the chain to see where it breaks. Includes JSON export.

### Lab 4: Policy Composition

**File:** `labs/lab4_composition.py`
**Guide mode:** linear

Loads `medical_ai.yaml` (base) and `medical_ai_child.yaml` (child) in side-by-side YAML editors. Users choose a composition strategy — intersect, union, or replace — and merge the policies. The diff summary shows roles kept/removed/added and tool changes. An escalation detector flags any privilege expansion (new roles, new tools, or removed postconditions).

### Lab 5: Loaders, Versioning & Testing

**File:** `labs/lab5_loaders.py`
**Guide mode:** workflows (3 workflows: Loaders, Versioning, Testing)

Three tabs:

1. **Loaders** — Toggle between `FilePolicyLoader` (reads YAML from disk) and InMemory loading (define policy inline in a text editor).
2. **Versioning** — Set `effective_date` and `expiration_date` on a policy, pick a reference date with a date picker, and validate. Includes a visual timeline bar.
3. **Testing** — `PolicyTestSuite` runner with three pre-built test cases: valid role passes, unauthorized role fails, missing precondition fails.

### Lab 6: Custom Enforcement Gates

**File:** `labs/lab6_custom_gates.py`
**Guide mode:** cookbook

Four pre-built `EnforcementGate` subclasses:

| Gate | Insertion Point | Behavior |
|------|----------------|----------|
| `ConfidenceGate` | pre_output | Fails if `output.confidence < 0.5` |
| `PIIDetectionGate` | post_output | Regex scan for emails, phone numbers, SSNs |
| `ResponseLengthGate` | pre_output | Fails if output > 500 characters |
| `AuditMetadataGate` | post_output | Always passes, injects custom metadata |

Users select a gate recipe, view its source code, see the pipeline visualization with the gate's insertion point highlighted, choose a test scenario, and run enforcement. The artifact's `gates_evaluated` list confirms the gate executed.

### Lab 7: Compliance Dashboard

**File:** `labs/lab7_compliance.py`
**Guide mode:** none (full-width layout)

Aggregates all audit artifacts from the session. Provides:

- Summary statistics: total audits, pass/fail counts and rates, average risk score, signing coverage.
- Filterable audit trail table (by status and policy).
- Multi-format export: JSON or CSV download.
- CLI equivalent commands showing how the same export runs from the command line.

## Shared Components

### Guide Rail System (`shared/guide_rail.py`)

Contextual help rendered in the right 25% column (via `st.columns([3, 1])`). Four display modes:

- **linear** — Numbered steps with green/blue/white completion dots.
- **workflows** — Radio-selectable workflow cards with sub-steps.
- **iterative** — Progress bar toward a milestone target with cycle steps.
- **cookbook** — Recipe cards with "Load" buttons.

Data model: `LabGuide` → `GuideStep` / `GuideWorkflow` / `GuideRecipe`. Each step can have a `completion_key` (session state key) and an optional `show_me` callback for auto-fill.

### Artifact Display (`shared/artifact_display.py`)

Reusable components:

- `render_artifact()` — Expander card with PASS/FAIL badge, role, risk score, signed status, gates evaluated, failures, chain info, checksum, and raw JSON.
- `render_risk_gauge()` — HTML horizontal bar (green/red zones) with threshold and score markers.
- `render_signal_breakdown()` — Table of risk factors with weight, triggered status, and contribution.
- `render_artifact_diff()` — Side-by-side JSON comparison.

### Policy Editor (`shared/policy_editor.py`)

- `render_policy_selector()` — Dropdown listing `*.yaml` files from `sample_policies/`.
- `render_policy_editor()` — Text area with live YAML parse validation.
- `load_policy_text()` — Reads a policy file and returns raw text + parsed dict.

## Sample Policies

| File | Version | Roles | Risk Mode | Threshold | Notes |
|------|---------|-------|-----------|-----------|-------|
| `medical_ai.yaml` | 2.0 | doctor, nurse, admin, researcher | risk_scored | 0.7 | Primary demo policy, date-bounded 2026 |
| `medical_ai_child.yaml` | 2.0-restricted | nurse | intersect (extends medical_ai) | — | Restricted child for composition lab |
| `finance_ai.yaml` | 1.5 | analyst, auditor, compliance_officer | strict | 0.5 | Finance sector, date-bounded 2026 |
| `content_moderation.yaml` | 1.0 | moderator, reviewer | strict | 0.3 | Low-tolerance content moderation |
| `high_risk.yaml` | 1.0 | planner, synthesizer, verifier, classifier, reviewer | strict | 0.3 | Aggressive blocking, broad roles |

## SDK Integration Points

The demo-app imports from the `aigc` public API (never from `aigc._internal`):

- `AIGC` — Main orchestrator; `enforce()` runs the full pipeline.
- `InvocationBuilder` — Fluent builder for invocation dicts.
- `AuditChain` — Hash-linked chain of audit artifacts.
- `HMACSigner` — HMAC-SHA256 signer for artifacts.
- `CallbackAuditSink` — Audit sink that calls a Python callback per artifact.
- `AIGCError`, `PolicyValidationError` — Exception hierarchy.
- `EnforcementGate`, `GateResult` — Custom gate plugin base class.
- `FilePolicyLoader` — Default filesystem policy loader.
- `PolicyTestCase`, `PolicyTestSuite`, `expect_pass`, `expect_fail` — Policy testing framework.
- `aigc.policy_loader.load_policy`, `merge_policies`, `validate_policy_dates` — Policy loading and composition.
- `aigc.signing.sign_artifact`, `verify_artifact` — Direct signing/verification.

## Development

### Adding a New Lab

1. Create `labs/lab{N}_{name}.py` with a `render()` function and optional `get_guide() -> LabGuide`.
2. Register it in `app.py`'s `LABS` dict.
3. Add any new session state keys to `shared/state.py`'s `init_state()` defaults.
4. Add mock scenarios to `shared/ai_client.py` if needed.
5. Create sample policies in `sample_policies/` if the lab requires them.

### Adding a New Gate Recipe

1. Define an `EnforcementGate` subclass in `labs/lab6_custom_gates.py`.
2. Add it to the `GATE_RECIPES` dict with a description and "demonstrates" string.
3. Add matching scenarios to `shared/ai_client.py`.

### Running the App in Development

```bash
cd demo-app
streamlit run app.py --server.runOnSave true
```

The `--server.runOnSave` flag enables hot-reload on file changes.
