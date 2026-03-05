# The Three C's of AIGC: Contract, Control, Check

## The Framework

AIGC (Auditable Intelligence Governance Contract) enforces three governance functions at the AI invocation boundary. Every AI model call passes through all three. No exceptions.

These three functions are the minimum viable governance for any AI system operating in production.

**Contract. Control. Check.**

---

## 1. Contract: Policy-as-Code

The Contract defines what the AI system is allowed to do. Not as a guideline. Not as a PDF reviewed quarterly. As a declarative policy that the system enforces at runtime.

**What it governs:**

Role authorization. Which agents, services, or users can invoke which AI capabilities. Unlisted roles are rejected. The allowlist is exhaustive.

Output schema. What shape the AI's response must take. If the model returns a narrative when the system requires structured data, the Contract rejects it before the output reaches any downstream process.

Preconditions and postconditions. What must be true before the AI is invoked and what must be true after. These are not optional checks. They are enforcement gates.

Conditional guards. Runtime context triggers policy expansion. An enterprise-tier customer invocation can activate stricter postconditions than a standard invocation. The base policy is never weakened. Guards only add constraints.

**The engineering principle:**

Governance is data, not code. The Contract is a declarative YAML file validated against JSON Schema at load time. There is no executable policy logic. No Turing-complete expression language. No side effects.

This means a compliance officer, an auditor, or a regulator can read the policy file and understand exactly what the system enforces. The governance logic is not buried in application code. It is visible, versioned, and schema-validated.

**What this replaces:**

Governance-by-documentation. The common pattern where AI policies exist in SharePoint, are reviewed annually, and have no enforcement mechanism. Contract makes governance executable at the speed of the system it governs.

---

## 2. Control: Fail-Closed Enforcement

The Control function determines what happens when something violates the Contract. The answer is always the same: the system stops.

**Fail-closed is the default behavior.**

Missing preconditions. The system stops. Invalid output schema. The system stops. Unauthorized role. The system stops. Tool call exceeding its budget. The system stops.

There is no "warn and continue." There is no "log and proceed." There is no degradation into permissiveness. The default answer is no.

**The enforcement pipeline:**

Every AI invocation passes through an ordered sequence of validation gates:

Policy loading and schema validation. Guard evaluation and conditional expansion. Role authorization. Precondition validation. Output schema validation. Postcondition enforcement. Tool constraint enforcement. Audit artifact generation.

All gates run or none do. Exceptions short-circuit the pipeline. The policy is never mutated during enforcement.

**Inbound and outbound enforcement:**

Control operates in both directions. Before the AI model is invoked, preconditions validate that the request is authorized, properly structured, and contextually valid. After the model responds, postconditions and schema validation confirm the output meets the Contract before it reaches any user, system, or downstream process.

The AI model never sees an unauthorized request. The user never sees a non-compliant response.

**The engineering principle:**

Enforcement is deterministic. Given the same invocation and the same policy, the system produces the same pass or fail decision. Every time. The governance layer introduces zero probabilistic behavior. That is the entire architectural purpose: a deterministic boundary around a probabilistic core.

**What this replaces:**

Advisory governance. The pattern where AI guardrails log warnings but do not prevent action. Control makes governance structural rather than observational. It does not monitor violations. It prevents them.

---

## 3. Check: Tamper-Evident Audit Trail

The Check function produces forensic evidence. Every enforcement, whether it passes or fails, generates a structured audit artifact.

**What the artifact contains:**

Policy version. Which governance contract was active. Model provider and identifier. Which AI model was called. Role. Who or what initiated the invocation. Enforcement result. Pass or fail. Input checksum. SHA-256 hash of the request. Output checksum. SHA-256 hash of the response. Failure details. If enforcement failed, which gate failed and why. Timestamp. When enforcement occurred. Context. Session, tenant, and correlation identifiers for downstream tracing.

**Tamper-evidence is structural, not procedural.**

Checksums are computed from canonical JSON (deterministic key ordering, no whitespace variance, UTF-8 encoding). Any party can independently recompute the checksums and verify integrity. If any field in the artifact is altered after generation, the checksums will not match. The record is self-verifying.

**Both PASS and FAIL produce artifacts.**

This is a critical design decision. Failed enforcement attempts are as important to audit as successful ones. An unauthorized role attempting to invoke a restricted AI capability is exactly the kind of event regulators and security teams need to trace. AIGC records it before propagating the exception.

**The engineering principle:**

Audit is mandatory. There is no silent mode. There is no "lightweight" enforcement path that skips artifact generation. If the system ran, there is a record. Artifacts are append-only. They are created, never updated or deleted.

**What this replaces:**

Retroactive compliance. The pattern where organizations reconstruct what their AI did after an incident, from application logs, user reports, and engineer memory. Check makes compliance contemporaneous. The evidence is generated at the moment of enforcement, not assembled after the fact.

---

## The Three C's as Architectural Layers

| Function | Governance Question | Enforcement Behavior |
|----------|-------------------|---------------------|
| **Contract** | What is allowed? | Declarative policy, schema-validated, versioned |
| **Control** | What happens when rules are broken? | Fail-closed, deterministic, no advisory mode |
| **Check** | What is the evidence? | Tamper-evident artifacts, mandatory, append-only |

These are not optional features. They are not modules to be enabled selectively. They are the minimum governance architecture for production AI.

Remove the Contract and the system has no declared boundaries.
Remove the Control and the system has boundaries that do not enforce.
Remove the Check and the system has enforcement that cannot be proven.

All three must be present. All three must execute at the speed of the AI system they govern.

---

## Provider Independence

AIGC governs invocations, not providers. The Three C's apply identically whether the AI model is from OpenAI, Anthropic, Google, AWS Bedrock, or an internally hosted model.

This is an architectural requirement, not a convenience feature. In any enterprise with multiple AI providers across business units, governance must be uniform. A single governance standard across all providers is the only way to maintain auditability at scale.

The Contract does not reference provider-specific APIs. The Control does not depend on provider-specific safety features. The Check does not rely on provider-specific logging.

Governance is the organization's responsibility. Not the vendor's.

---

## Where the Three C's Sit in the Broader Architecture

The Three C's operate within the deterministic wrapper described in the AIGC Production Stack:

The **Invariant Layer** defines the hard constraints. The Contract encodes them.

**Confidence Gates** route decisions by certainty. The Contract defines the thresholds. The Control enforces them.

The **Evaluation Gate** validates outputs before action. This is Control at the output boundary.

The **Replay Engine** reconstructs decision sequences. The Check provides the forensic data.

**Graceful Degradation** returns the system to a safe state when AI fails. The Control ensures failure is contained, not propagated.

The Three C's are not separate from the five-layer architecture. They are the governance functions that the five layers implement.

---
