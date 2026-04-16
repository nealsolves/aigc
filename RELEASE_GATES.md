# Release Gates

This file tracks the entry and exit gates for the `v0.9.0` beta train.

Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
`v0.9.0` is formally declared a GO.

---

## `v0.9.0` Branch Map

| PR | Branch | Goal |
|----|--------|------|
| PR-01 | `feat/v0.9-01-source-of-truth` | Canonical plan, release packet, and CI truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | Freeze session lifecycle, `SessionPreCallResult`, and artifact separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | Freeze CLI shape, starter profiles, public-import rules, and docs order |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | Land the smallest real governed local workflow path |
| PR-05 | `feat/v0.9-05-starters-and-migration` | Ship starters, thin presets, and migration helpers |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | Ship `workflow doctor`, `workflow lint`, and stable reason codes |
| PR-07 | `feat/v0.9-07-beta-proof` | Mandatory stop-ship checkpoint for quickstart, demo, and failure-and-fix proof |
| PR-08 | `feat/v0.9-08-engine-hardening` | Harden workflow sequencing, approvals, budgets, and validator hooks |
| PR-09 | `feat/v0.9-09-exports-and-ops` | Ship trace, export, and operator polish |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | Add optional Bedrock adapter with alias-backed identity binding |
| PR-10b | `feat/v0.9-10-a2a-adapter` | Add optional A2A adapter with strict wire-contract validation |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Freeze the beta and start the final release sequence only after all gates pass |

---

## PR-01 — Source-of-Truth Gate

Branch:

- `feat/v0.9-01-source-of-truth`

Checklist:

- [ ] `CLAUDE.md` and `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` are
      present and treated as the canonical `v0.9.0` inputs
- [ ] `docs/plans/v0.9.0_DOCS_ONLY_PR_PLAN.md` constrains PR-01 to docs-only
      plus CI truth enforcement
- [ ] `docs/dev/pr_context.md` reflects the `v0.9.0` PR table
- [ ] `RELEASE_GATES.md` reflects the `v0.9.0` PR table and beta gates
- [ ] `implementation_status.md` reflects the `v0.9.0` PR table and start
      state
- [ ] stale `v0.9.0` plan variants are marked as superseded or historical input
- [ ] CI fails if more than one active `v0.9.0` implementation plan exists
- [ ] CI fails if `CLAUDE.md`, `docs/dev/pr_context.md`, `RELEASE_GATES.md`,
      and `implementation_status.md` disagree on branch names, PR numbering,
      `PR-07` stop-ship, or the `origin/main` freeze
- [ ] no runtime behavior changes land in PR-01
- [ ] no schema behavior changes land in PR-01
- [ ] no public API changes land in PR-01

---

## PR-02 — Contract Freeze Gate

Branch:

- `feat/v0.9-02-contract-freeze`

Checklist:

- [ ] `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` and
      `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` freeze lifecycle states,
      workflow artifact statuses, `SessionPreCallResult`, and
      `AIGC.open_session(...)`
- [ ] `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` keep the shipped
      `v0.3.3` surface honest while naming workflow surfaces as planned-only
- [ ] `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and
      `implementation_status.md` align on the PR-02 branch, scope, and exit
      criteria
- [ ] CI fails on PR-02 contract drift across the canonical plan, HLD,
      onboarding docs, and release packet
- [ ] public-surface sentinel tests confirm no workflow runtime or workflow CLI
      surface shipped early
- [ ] protocol-boundary contract tests freeze Bedrock and A2A fail-closed
      rules without runtime adapters
- [ ] no workflow runtime, schema, CLI, demo, adapter, or version changes land
      in PR-02

---

## PR-03 — Golden-Path Contract Freeze Gate

Branch:

- `feat/v0.9-03-golden-path-contract`

Checklist:

- [ ] `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` and
      `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` freeze the golden-path CLI
      command inventory, scaffold profiles, starter coverage, docs order, and
      minimum first-user reason-code set
- [ ] `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` keep the shipped
      `v0.3.3` surface honest while naming `aigc policy init` and
      `aigc workflow ...` commands as planned-only
- [ ] `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and
      `implementation_status.md` align on the PR-03 branch, scope, and exit
      criteria
- [ ] CI fails on PR-03 contract drift across the canonical plan, HLD,
      onboarding docs, and release packet
- [ ] staged CLI sentinel tests prove the current shipped CLI still exposes no
      `workflow` or `policy init` commands while freezing the future command
      names in docs
- [ ] public-import boundary tests confirm maintained onboarding examples and
      demo code use public `aigc` imports only
- [ ] no workflow runtime, starter-generation, shipped CLI, schema, adapter,
      demo-behavior, or version changes land in PR-03

---

## Capability Gates

### PR-02 — Contract Freeze

- [ ] session lifecycle states are frozen and tested
- [ ] workflow artifact status values are frozen and tested
- [ ] `SessionPreCallResult` semantics are frozen and tested
- [ ] `AIGC.open_session(...)` is the workflow entrypoint contract
- [ ] Bedrock and A2A boundary tests fail closed

### PR-03 — Golden-Path Contract Freeze

- [ ] golden-path CLI surface is frozen
- [ ] scaffold profiles are frozen
- [ ] starter coverage is frozen
- [ ] public-import-only rules are frozen
- [ ] docs order for first adopters is frozen
- [ ] first-failure reason-code coverage is frozen

### PR-04 — Minimal Working Session Flow

- [ ] `GovernanceSession` lifecycle is implemented end to end
- [ ] `SessionPreCallResult` is single-use and session-bound
- [ ] a local `2`-step or `3`-step workflow completes with correlated evidence
- [ ] the host remains responsible for orchestration and provider calls

### PR-05 — Starters, Presets, and Migration Helpers

- [ ] `aigc workflow init` ships starter scaffolds
- [ ] `aigc policy init` ships starter policies
- [ ] starter examples run on the PR-04 session flow
- [ ] invocation-only migration path is documented and smoke-tested

### PR-06 — Doctor, Lint, and Plain-English Diagnostics

- [ ] `aigc workflow lint` covers schema, transitions, bindings, budgets,
      starter integrity, and public-import safety
- [ ] `aigc workflow doctor` covers runtime and evidence diagnosis
- [ ] stable reason codes and next-action guidance exist for common failures

### PR-07 — Quickstart, Demo, and Beta Proof

- [ ] PR-07 is the mandatory stop-ship checkpoint
- [ ] clean-environment quickstart succeeds within the `15` minute target
- [ ] at least one intentional failure-and-fix flow passes end to end
- [ ] the default adopter path succeeds without Bedrock or A2A
- [ ] no internal-code reading is required on the default path
- [ ] no fake backend behavior exists in the demo

### PR-08 — Workflow Engine Hardening

- [ ] restrictive composition is enforced and widening merges fail validation
- [ ] approvals, budgets, transitions, and handoffs behave deterministically
- [ ] validator hooks have typed contracts, bounded timeouts, and auditable
      provenance

### PR-09 — Trace, Export, CLI, and Operator Polish

- [ ] `aigc workflow trace` reconstructs workflow timelines correctly
- [ ] `aigc workflow export` supports operator and audit modes
- [ ] sink failures surface explicitly without weakening required fail-closed
      paths

### PR-10a — Bedrock Adapter

- [ ] alias-backed identity is required for governed participant binding
- [ ] missing required trace fails closed
- [ ] ambiguous identity fails closed

### PR-10b — A2A Adapter

- [ ] only supported `1.0` JSON-RPC and HTTP+JSON bindings are accepted
- [ ] normative `TASK_STATE_*` wire values are accepted
- [ ] shorthand task-state values are rejected
- [ ] unsupported gRPC transport fails with a typed protocol violation

### PR-11 — Public API Freeze and Beta Release

- [ ] public API snapshot tests pass
- [ ] workflow CLI help text and JSON shapes are frozen
- [ ] export portability and integrity verification pass
- [ ] the release remains explicitly labeled Beta

---

## Beta Stop-Ship Gate

`v0.9.0` beta readiness is blocked until all of the following are true:

- [ ] clean-environment docs-to-working-app success exists for the default path
- [ ] quickstart completes within the `15` minute target budget
- [ ] at least two public-import-only starter examples reach PASS
- [ ] at least one failure-and-fix path is validated end to end
- [ ] `workflow doctor` and `workflow lint` explain that failure clearly
- [ ] no internal-code reading is required
- [ ] no advanced manifest authoring is mandatory on the default path
- [ ] workflow trace visibility and evidence visibility exist on the default
      path
- [ ] the default adopter path succeeds without Bedrock or A2A

---

## `v0.9.0` Beta Release Gate

`v0.9.0` beta ships only if all of the following are true:

- [ ] PR-01 through PR-10 work is merged to `origin/develop`
- [ ] Bucket 1 build-time evidence is collected and reviewed
- [ ] locked decisions are published and test-backed
- [ ] the golden-path contract is frozen before later surface expansion
- [ ] quickstart, starters, migration, diagnostics, exports, and adapters all
      pass their required tests
- [ ] approval checkpoints, validator hooks, and budgets fail closed
- [ ] Bedrock identity rules and A2A wire-contract rules are test-backed
- [ ] package smoke passes for base install and optional extras
- [ ] `feat/v0.9-11-beta-freeze` lands
- [ ] `release/v0.9.0` is cut from the PR-11 result
- [ ] only then is the `origin/develop` -> `origin/main` PR opened
