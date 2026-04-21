# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Demo App Guidance

When working on `demo-app-react`, `demo-app-api`, or demo-related documentation:

- React + permanent FastAPI backend is the maintained demo architecture
- `demo-app-streamlit` is deprecated reference material only
- `v0.3.3` demo work (Labs 8-10) is historical — see `docs/plans/v0.3.3_IMPLEMENTATION_PLAN.md`
- Active work is `v0.9.0` — see `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` for the canonical plan

**`v0.9.0` demo requirements** (from the plan):

- one `start here` flow following the quickstart
- one intentional failure-and-fix flow using `workflow doctor` or `workflow lint`
- one governed-versus-ungoverned comparison
- one evidence view based on workflow artifacts and correlated invocation checksums
- no fake backend behavior
- the default demo path must succeed without Bedrock or A2A

## Build & Test Commands

```bash
pip install -e .                              # Install in dev mode
python -m pytest                              # Run all tests
python -m pytest tests/test_golden_replay_success.py  # Run a single test file
python -m pytest tests/test_golden_replay_success.py::test_golden_success_produces_audit  # Run a single test
flake8 aigc                                   # Lint Python source
npx markdownlint-cli2 "**/*.md"              # Lint markdown files
```

**Policy schema validation** (inline, as done in CI):
```bash
python -c "
import json, yaml, jsonschema
from pathlib import Path
schema = json.load(open('schemas/policy_dsl.schema.json'))
for p in Path('policies').glob('*.yaml'):
    jsonschema.validate(yaml.safe_load(open(p)), schema)
    print(f'OK: {p}')
"
```

**Generate golden replays from invocation logs:**
```bash
python scripts/generate_golden_replays.py --input logs/invocations.json
```

## Architecture

The SDK enforces governance over AI model invocations through a pipeline:

```
enforce_invocation(invocation)
  → load_policy()              [aigc/_internal/policy_loader.py]
  → run_custom_gates()         [aigc/_internal/gates.py]          # pre_authorization
  → evaluate_guards()          [aigc/_internal/guards.py]
  → validate_role()            [aigc/_internal/validator.py]
  → validate_preconditions()   [aigc/_internal/validator.py]
  → validate_tool_constraints()[aigc/_internal/tools.py]
  → run_custom_gates()         [aigc/_internal/gates.py]          # post_authorization
  → run_custom_gates()         [aigc/_internal/gates.py]          # pre_output
  → validate_schema()          [aigc/_internal/validator.py]
  → validate_postconditions()  [aigc/_internal/validator.py]
  → run_custom_gates()         [aigc/_internal/gates.py]          # post_output
  → compute_risk_score()       [aigc/_internal/risk_scoring.py]
  → generate_audit_artifact()  [aigc/_internal/audit.py]
  → return audit record
```

**`aigc/_internal/enforcement.py`** — Orchestrator. `enforce_invocation(invocation)` is the single entry point. An invocation dict must include: `policy_file`, `input`, `output`, `context`, `model_provider`, `model_identifier`, `role`.

**`aigc/_internal/policy_loader.py`** — Loads YAML policy files, resolves `extends` composition, and validates against JSON Schema. Prefers `schemas/policy_dsl.schema.json` (extended DSL), falls back to `schemas/invocation_policy.schema.json` (legacy).

**`aigc/_internal/validator.py`** — Precondition, schema, and postcondition validation. Supports typed preconditions (type, pattern, enum, min/max constraints) alongside legacy bare-string format.

**`aigc/_internal/audit.py`** — Generates audit artifacts with SHA-256 checksums of input/output, timestamps, risk scores, signing, and policy metadata.

**`aigc/_internal/errors.py`** — Custom exception hierarchy with typed error codes.

**`aigc/_internal/guards.py`** — AST-based guard evaluation engine for conditional policy expansion.

**`aigc/_internal/risk_scoring.py`** — Factor-based risk scoring with strict/risk_scored/warn_only modes.

**`aigc/_internal/signing.py`** — Artifact signing via HMAC-SHA256 with constant-time verification.

**`aigc/_internal/gates.py`** — Custom EnforcementGate plugin system with four insertion points.

### `v0.9.0` Additions (current beta surface on `develop`)

These components are present in the source-only `v0.9.0` beta line on local
`develop`. The published package version remains `0.3.3` until the beta train
is released.

**`AIGC.open_session(...)`** — Public workflow entrypoint. Returns a `GovernanceSession` instance. Workflow adoption is always instance-scoped through this method. There is no module-level `open_session(...)`.

**`GovernanceSession`** — Context manager. Enforces deterministic lifecycle states:
`OPEN → PAUSED | FAILED | COMPLETED | CANCELED → FINALIZED`.
`__exit__` never suppresses exceptions. Clean exit from a non-terminal state auto-finalizes
to `INCOMPLETE`. Exception exit records failure context, transitions to `FAILED`, emits a
`FAILED` workflow artifact, and re-raises.

**`SessionPreCallResult`** — Single-use wrapper around an invocation `PreCallResult` plus
immutable `session_id`, `step_id`, `participant_id`, and workflow-bound replay protection.
Cannot be completed through module-level `enforce_post_call(...)` — must be completed
through the owning `GovernanceSession`.

**Workflow artifact `status` values:** `COMPLETED`, `FAILED`, `CANCELED`, `INCOMPLETE`. `FINALIZED` is a lifecycle state only and is never serialized as an artifact status.

**Optional adapters (advanced tracks):**
- `BedrockTraceAdapter` — normalizes host-supplied parsed Bedrock trace parts. Alias-backed identity required for governed binding. Name-only evidence is insufficient when policy requires authoritative identity.
- `A2AAdapter` — normalizes parsed Agent Card, request metadata, and task envelopes. Validates `supportedInterfaces[].protocolVersion`. Accepts only normative `TASK_STATE_*` wire values. gRPC is out of scope for `v0.9.0`.

**Starter scaffolds:** `minimal`, `standard`, `regulated-high-assurance` — generated by `aigc workflow init`. These compile to ordinary session + policy + manifest behavior with no hidden runtime layer.

**CLI commands (v0.9.0 beta):** `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, `aigc workflow export`, and `aigc policy init`. All six workflow CLI commands ship as of PR-09.

**Starter coverage (v0.9.0):** local multi-step review, approval checkpoint, source-required, and tool-budget flows. Hand-authored workflow DSL stays supported as advanced mode and is not required on the default path.

**Minimum first-user reason codes (v0.9.0):** `WORKFLOW_INVALID_TRANSITION`, `WORKFLOW_APPROVAL_REQUIRED`, `WORKFLOW_SOURCE_REQUIRED`, `WORKFLOW_TOOL_BUDGET_EXCEEDED`, `WORKFLOW_UNSUPPORTED_BINDING`, `WORKFLOW_SESSION_TOKEN_INVALID`, `WORKFLOW_STARTER_INTEGRITY_ERROR`.

**First-adopter docs order (v0.9.0):** workflow quickstart, invocation-only-to-workflow migration, troubleshooting, starter index and recipes, workflow CLI guide, public API boundary, supported environments, operations runbook, adapters last.

**Ownership boundary (critical):** AIGC owns policy loading, ordered governance checks, workflow
constraints, evidence correlation, optional adapter normalization, and audit artifacts. The host
continues to own orchestration, transport, retries, credentials, business state, tool execution,
and provider SDK usage. Never add hidden orchestration, hosted control planes, or transport
ownership to AIGC.

**Evidence model:** Invocation artifacts remain one artifact per invocation attempt. Workflow/session evidence is separate. Invocation artifacts gain additive workflow-correlation metadata only. Raw external payloads are not persisted by default.

## Public API

The `aigc/` top-level package re-exports the stable public API. All implementation lives in `aigc/_internal/`. Never import from `aigc._internal` in host code.

## Policy System

Policies are YAML files validated against `schemas/policy_dsl.schema.json`
(JSON Schema Draft-07). Key fields: `policy_version`, `roles`,
`pre_conditions.required`, `post_conditions.required`, `output_schema`,
`conditions`, `tools`, `retry_policy`, `guards`, `risk`,
`composition_strategy`. The full DSL spec is in
`policies/policy_dsl_spec.md`.

## Testing Patterns

Tests use **golden replays** — deterministic fixtures in `tests/golden_replays/` that encode expected governance behavior:

- `golden_policy_v1.yaml` + `golden_schema.json` — test policy and output schema
- `golden_invocation_success.json` / `golden_invocation_failure.json` — valid and invalid invocations
- `golden_expected_audit.json` — stable fields to assert against (excludes timestamps/checksums)

Test files follow a naming convention: `test_golden_replay_success.py`, `test_golden_replay_failure.py`, `test_audit_artifact_contract.py`. When adding new governance behaviors, create paired success/failure golden replays.

Only assert **stable** audit fields (`model_provider`, `model_identifier`, `policy_version`, `role`). Timestamps and checksums are volatile.

**`v0.9.0` additional test patterns** (apply as each PR lands):

- lifecycle tests — `GovernanceSession` state transitions including `OPEN`, `PAUSED`, `FAILED`, `COMPLETED`, `CANCELED`, `FINALIZED`
- context-manager tests — `__exit__` behavior: clean exit → `INCOMPLETE`; exception exit → `FAILED` + re-raise
- replay-prevention tests — `SessionPreCallResult` is single-use; verify a second completion attempt is rejected
- invocation-correlation tests — workflow artifact references correlated invocation artifact IDs
- public-import boundary tests — no example, starter, preset, recipe, or doc snippet may import from `aigc._internal`
- state-machine tests — ordered sequence, allowed transitions, budget accounting, approval checkpoints
- restrictive-composition tests — role sets narrow; ambiguous or widening merges must fail validation
- adapter fixture tests — Bedrock alias-binding, missing-trace rejection; A2A `TASK_STATE_*` acceptance and shorthand rejection

## Pre-Push Code Review (Mandatory)

**Before pushing any branch to a remote, you MUST perform a thorough code review of every file changed in that push.** This is not optional and does not require the user to ask for it.

Use the `superpowers:code-reviewer` agent to perform the review. Pass it the list of changed files (from `git diff --name-only origin/<base>...HEAD` or equivalent) and instruct it to audit every file against the following checklist:

1. **Stale response / race condition** — every async fetch that writes to state must guard against older requests resolving after newer ones. Pattern: capture a cancellation flag or request-generation counter before `await`; check it before calling `setState`.
2. **Shared write contention** — if two async handlers write the same state variable, which one should win and is that enforced?
3. **Gate conditions** — every "readiness" or "success" gate (`setReady(true)`, etc.) must require ALL necessary conditions to hold. Check that error paths cannot reach the gate.
4. **Date/time correctness** — `new Date('YYYY-MM-DD')` parses as UTC; `.getFullYear()/.getMonth()/.getDate()` are local time. Flag any mixing.
5. **Null/undefined safety** — can any code path pass `null`, `undefined`, `{}`, or `[]` to a function expecting real data and silently succeed?
6. **Logic correctness** — do filter conditions, derived values, and conditional renders match the intent in comments and help content?
7. **API contract alignment** — do frontend field names and types match backend response shapes exactly?
8. **Test coverage** — do tests cover the new code paths, including error branches?

**How to act on review findings:**

- **Bug** (incorrect behavior under reachable conditions): fix before pushing.
- **Risk** (incorrect behavior under edge or error conditions): fix before pushing unless the scenario is demonstrably unreachable in this codebase.
- **Style** (formatting, naming, cosmetic): do not block push; note if significant.

Do not push until all bugs and risks are resolved. Run the full test suite and build after fixes to confirm nothing is broken.

## Git Workflow

All code changes must follow this branch flow:

```
feature-branch → local develop → local main → origin/develop (PR) → origin/main (PR)
```

1. Branch off `develop`: `git checkout -b feature/xxx develop`
2. Commit work on the feature branch
3. Merge into local `develop`: `git checkout develop && git merge feature/xxx`
4. Merge into local `main`: `git checkout main && git merge develop`
5. Open a PR to merge into `origin/develop` → merge
6. Open a PR from `origin/develop` → `origin/main` → merge

Never push directly to remote `develop` or `main` — always use PRs for remote merges (branch protection enforces this).

### `origin/main` Freeze — Active Until `v0.9.0` Is GO

**Do NOT open or merge a PR from `origin/develop` → `origin/main` until `v0.9.0` is formally declared a GO.**

During active `v0.9.0` development (PR-01 through PR-10), all remote merges target `origin/develop` only. The `origin/develop` → `origin/main` PR is opened only after all v0.9.0 release gates are satisfied (see `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` — Release Gates section).

The final release sequence is:
1. All PR-01 through PR-10 work is merged to `origin/develop`
2. PR-11 (`feat/v0.9-11-beta-freeze`) lands — public API snapshot tests, full CI matrix, all stop-ship gates pass
3. A `release/v0.9.0` branch is cut from `feat/v0.9-11-beta-freeze`
4. **Only then**: PR from `origin/develop` → `origin/main` is opened and merged

### `v0.9.0` PR Structure

All `v0.9.0` feature branches follow the naming convention `feat/v0.9-NN-description` and target `develop`.

| PR | Branch | Goal |
|----|--------|------|
| PR-01 | `feat/v0.9-01-source-of-truth` | Canonical plan + supersede stale artifacts + CI plan-truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | Freeze session lifecycle, `SessionPreCallResult`, artifact separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | Freeze CLI surface, scaffold profiles, public-import rules, docs order |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | `GovernanceSession`, `AIGC.open_session(...)`, `SessionPreCallResult`, local 2–3 step workflow |
| PR-05 | `feat/v0.9-05-starters-and-migration` | `aigc workflow init`, starter scaffolds, migration helpers, thin presets |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | `aigc workflow lint`, `aigc workflow doctor`, stable reason codes |
| PR-07 | `feat/v0.9-07-beta-proof` | Quickstart docs, clean-env validation, stop-ship checkpoint — **blocks further work if not green** |
| PR-08 | `feat/v0.9-08-engine-hardening` | Ordered transitions, composition, approval checkpoints, `ValidatorHook`, budgets |
| PR-09 | `feat/v0.9-09-exports-and-ops` | `aigc workflow trace`, `aigc workflow export`, operator + audit export modes |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | `BedrockTraceAdapter`, alias-backed identity, fail-closed on missing trace |
| PR-10b | `feat/v0.9-10-a2a-adapter` | `A2AAdapter`, `TASK_STATE_*` validation, gRPC rejection |
| PR-11 | `feat/v0.9-11-beta-freeze` → `release/v0.9.0` | API snapshot tests, full CI matrix, all gates — triggers `origin/main` PR |

PR-07 is a mandatory stop-ship checkpoint. If the golden-path validation fails there, no new public-surface work proceeds until the default adoption path is repaired.

## Dependencies

`PyYAML`, `jsonschema`, `pytest`, `pytest-cov`, `flake8` — listed in `pyproject.toml`.
