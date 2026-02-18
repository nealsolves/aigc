# AIGC ↔ TRACE Integration Architecture

**Status:** Planned | Work lives in the TRACE repository
**Last Updated:** 2026-02-17

---

## 1. What is TRACE?

TRACE (Temporal Root-cause Analytics & Correlation Engine) is an agentic RAG
system for root-cause analysis. It is the primary host application for which
AIGC was designed, but AIGC has no dependency on TRACE internals and is fully
portable to any Python system that invokes AI models.

TRACE repository: <https://github.com/nealsolves/trace/tree/develop>

TRACE uses AIGC to govern:

- Model invocations across planner, verifier, and synthesizer agents
- Tool usage constraints (which tools, how many calls)
- Output schema compliance (structured RCA outputs)
- Audit trail generation for compliance reporting

---

## 2. Integration Architecture

AIGC integrates with TRACE at five specific points in the TRACE architecture:

```text
┌───────────────────────────────────────────────────────────────────┐
│                         TRACE v5.0                                │
│                                                                   │
│   ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│   │  Orchestrator│───▶│ Tool Executor│───▶│  Model Provider    │  │
│   │  (Planner/  │    │              │    │  (Anthropic, etc.) │  │
│   │   Executor) │    └──────┬───────┘    └────────┬───────────┘  │
│   └──────┬──────┘           │                     │              │
│          │            ┌─────▼─────┐         ┌─────▼─────┐        │
│          │            │ ❶ AIGC    │         │ ❷ AIGC    │        │
│          │            │ Tool Gate │         │ Provider  │        │
│          │            │           │         │ Gate      │        │
│          │            └───────────┘         └───────────┘        │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐│
│   │  Compliance  │───▶│   State      │───▶│  Audit Sink        ││
│   │  Pipeline    │    │   Manager    │    │  (SQLite/DynamoDB) ││
│   └──────┬───────┘    └──────┬───────┘    └────────────────────┘│
│          │                   │                                   │
│    ┌─────▼─────┐       ┌────▼──────┐                            │
│    │ ❸ AIGC    │       │ ❹ AIGC    │                            │
│    │ Compliance│       │ Audit     │                            │
│    │ Extension │       │ Correlator│                            │
│    └───────────┘       └───────────┘                            │
│                                                                  │
│          ❺ AIGC Policy Registry (shared policies for all gates)  │
│                                                                  │
└───────────────────────────────────────────────────────────────────┘
```

### ❶ Tool Invocation Gate

Intercepts tool execution in TRACE's `ToolExecutor`. Enforces tool allowlists
and per-tool call caps defined in the policy.

```python
# In TRACE's tool_executor.py
from aigc.enforcement import enforce_invocation

class GovernedToolExecutor(ToolExecutor):
    async def execute(self, tool_name, params, context):
        audit = enforce_invocation({
            "policy_file": context.governance_policy,
            "model_provider": context.provider,
            "model_identifier": context.model,
            "role": context.agent_role,
            "input": {"tool": tool_name, "params": params},
            "output": {},  # pre-invocation check
            "context": context.to_governance_context(),
        })
        result = await super().execute(tool_name, params, context)
        return result, audit
```

### ❷ Provider Governance Gate

Wraps TRACE's provider layer. Enforces that only approved models are used
for each role and that invocation outputs conform to declared schemas.

```python
# Governed provider wrapper
class GovernedLLMProvider(BaseLLM):
    async def generate(self, messages, tools=None):
        response = await self.inner.generate(messages, tools)
        audit = enforce_invocation({
            "policy_file": self.policy_file,
            "model_provider": self.provider_name,
            "model_identifier": self.model_id,
            "role": self.current_role,
            "input": {"messages": messages},
            "output": response,
            "context": self.governance_context,
        })
        return response, audit
```

### ❸ Compliance Pipeline Extension

TRACE's mandatory compliance pipeline (`verify_references → redact_pii`)
can delegate governance decisions to AIGC for policy-driven compliance
rules beyond reference verification and PII redaction.

### ❹ Audit Correlator

Extracts AIGC audit artifacts and correlates them with TRACE's native
audit log (session events, tool calls, compliance decisions) to produce
unified governance reports.

### ❺ Policy Registry

A shared directory of AIGC policies governing all integration points.
Policies are versioned and validated in CI.

```text
policies/
├── trace_planner.yaml        ← policy for planner role
├── trace_verifier.yaml       ← policy for verifier role
├── trace_synthesizer.yaml    ← policy for synthesis role
├── trace_tools.yaml          ← tool-level governance
└── base_policy.yaml          ← default fallback
```

---

## 3. Audit Artifact Storage

AIGC produces artifacts; TRACE persists them. Recommended storage strategies:

| Deployment | Storage Strategy |
| ---------- | ---------------- |
| Local / dev | SQLite `audit_log` table via TRACE's StateManager |
| AWS | DynamoDB audit table + S3 archival |
| CI/CD | Golden trace fixtures in `tests/golden_traces/` |

The `JsonFileAuditSink` and `CallbackAuditSink` built into the SDK
(`aigc.sinks`) are the bridge. TRACE-specific sinks (SQLite, DynamoDB)
live in the TRACE repository.

---

## 4. Implementation Plan

These work items live in the **TRACE repository**, not this SDK.

### 4.1 Tool Invocation Gate (Phase 3.5)

**Problem:** TRACE's tool executor (`core/tools/tool_executor.py`) has no
governance. Tools execute without policy checks.

**Deliverables (in TRACE repo):**

- `GovernedToolExecutor` wrapper that calls AIGC enforcement before tool
  execution
- Maps TRACE's tool call context to an AIGC invocation dict
- Captures tool name, parameters, and agent role from TRACE session state
- Stores audit artifacts in TRACE's `audit_log` via `SQLiteAuditSink`

**Acceptance criteria:**

- Tool call to `search_knowledge_base` with a planner role and valid
  policy passes governance
- Tool call to `generate_rca_draft` exceeding `max_calls: 1` raises
  `GovernanceViolationError`
- Audit artifacts appear in TRACE's `audit_log` table
- TRACE golden trace GT-001 still passes with governance enabled

**Files to create/modify (in TRACE repo):**

| File | Action |
| ---- | ------ |
| `core/tools/governed_executor.py` | Create — AIGC-governed tool executor |
| `core/tools/tool_executor.py` | Wire governed executor as default |
| `tests/integration/test_governed_tools.py` | Create |

### 4.2 Provider Governance Gate (Phase 3.6)

**Problem:** TRACE's provider layer (`core/providers/`) has no governance.
Any model can be used for any role.

**Deliverables (in TRACE repo):**

- `GovernedLLMProvider` wrapper that enforces AIGC policies on model
  invocations
- Maps TRACE's provider context (model, role, messages, response) to
  AIGC invocations
- Validates that the model used matches the role's governance policy
- Produces audit artifacts for every LLM call

**Acceptance criteria:**

- Planner role using `claude-sonnet-4` with a planner policy passes
- Planner role using an unauthorized model raises
  `GovernanceViolationError`
- Audit artifacts include `model_provider` and `model_identifier`
- Provider swap (Anthropic to Bedrock) does not require governance changes

**Files to create/modify (in TRACE repo):**

| File | Action |
| ---- | ------ |
| `core/providers/governed_llm.py` | Create — governed provider wrapper |
| `core/providers/factory.py` | Wire governed provider |
| `tests/integration/test_governed_providers.py` | Create |

### 4.3 Audit Correlation (Phase 3.7)

**Problem:** TRACE has its own `audit_log`. AIGC produces separate audit
artifacts. There is no unified view.

**Deliverables (in TRACE repo):**

- Audit correlator that joins TRACE session events with AIGC audit
  artifacts
- Correlation key: `session_id` + timestamp range
- Export format: unified JSON report for compliance review
- Queryable: "Show me all governance decisions for session X"

**Acceptance criteria:**

- Given a TRACE session ID, retrieve all AIGC audit artifacts for that
  session
- Report includes both TRACE compliance events (`verify_references`,
  `redact_pii`) and AIGC governance decisions
- Export produces valid JSON matching a defined schema

**Files to create (in TRACE repo):**

| File | Action |
| ---- | ------ |
| `core/compliance/audit_correlator.py` | Create |
| `schemas/compliance/governance_report_v1.json` | Create — report schema |
| `tests/compliance/test_audit_correlation.py` | Create |

---

## 5. Phase 3 TRACE Definition of Done

- [ ] TRACE tool executor governed by AIGC policies
- [ ] TRACE provider layer governed by AIGC policies
- [ ] TRACE audit log correlates with AIGC artifacts
- [ ] End-to-end TRACE + AIGC integration test passes

The AIGC SDK itself is complete and installable. These items are tracked
in the TRACE repository.
