# Implementation Status

**Target Version:** `0.9.0` Beta
**Baseline Version:** `0.3.3`
**Active Branch:** `feat/v0.9-02-contract-freeze`
**Last Updated:** 2026-04-15

---

## Overall Progress

Current state:

- PR-01 is complete
- PR-02 is in progress
- workflow runtime implementation still starts in PR-04

| Track | Status | Notes |
|-------|--------|-------|
| Source of truth | complete | Canonical docs and CI truth checks are the baseline for later PRs |
| Contract freeze | in progress | PR-02 is freezing the workflow contract through docs, CI, and sentinel tests |
| Golden-path contract | not started | Starts in PR-03 |
| Minimal session flow | not started | Starts in PR-04 |
| Starters and migration | not started | Starts in PR-05 |
| Diagnostics | not started | Starts in PR-06 |
| Beta proof | not started | Starts in PR-07 |
| Engine hardening | not started | Starts in PR-08 |
| Exports and ops | not started | Starts in PR-09 |
| Optional adapters | not started | Starts in PR-10a and PR-10b |
| Beta freeze | not started | Starts in PR-11 |

---

## Active Source of Truth

- `CLAUDE.md` is the collaborator contract for demo rules, workflow semantics,
  adapter fail-closed boundaries, PR structure, `PR-07` stop-ship, and the
  `origin/main` freeze.
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md` is the one active
  implementation plan.
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` is the target-state design
  contract that PR-02 is locking against the implementation plan.
- `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and this file are the release
  truth packet that must stay aligned with `CLAUDE.md`.

---

## Release Rules

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
  no further public-surface work proceeds until the default path is repaired.
- The default adopter path must succeed without Bedrock or A2A.
- PR-02 is contract freeze only. It updates docs, CI, and sentinel tests only.
- No workflow runtime, public export stubs, workflow CLI commands, demo
  changes, or adapter implementations land in PR-02.
- Workflow runtime implementation begins in PR-04.

---

## PR Status

| PR | Branch | Status | Notes |
|----|--------|--------|-------|
| PR-01 | `feat/v0.9-01-source-of-truth` | complete | Canonical plan, release packet, supersession banners, and CI truth checks |
| PR-02 | `feat/v0.9-02-contract-freeze` | in progress | Freeze lifecycle, `SessionPreCallResult`, `AIGC.open_session(...)`, and evidence separation |
| PR-03 | `feat/v0.9-03-golden-path-contract` | not started | Freeze CLI shape, starter profiles, public-import rules, and docs order |
| PR-04 | `feat/v0.9-04-minimal-session-flow` | not started | Smallest real governed local workflow path |
| PR-05 | `feat/v0.9-05-starters-and-migration` | not started | Starters, thin presets, and migration helpers |
| PR-06 | `feat/v0.9-06-doctor-and-lint` | not started | Diagnostics, stable reason codes, and fix guidance |
| PR-07 | `feat/v0.9-07-beta-proof` | not started | Mandatory stop-ship checkpoint for quickstart, demo, and failure-and-fix proof |
| PR-08 | `feat/v0.9-08-engine-hardening` | not started | Sequencing, approvals, budgets, and validator-hook hardening |
| PR-09 | `feat/v0.9-09-exports-and-ops` | not started | Trace, export, and operator polish |
| PR-10a | `feat/v0.9-10-bedrock-adapter` | not started | Optional Bedrock adapter with alias-backed identity rules |
| PR-10b | `feat/v0.9-10-a2a-adapter` | not started | Optional A2A adapter with strict wire-contract rules |
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | not started | Public API freeze, beta gate verification, and release cut |

---

## PR-02 Deliverables

- [x] create `feat/v0.9-02-contract-freeze` from current `develop`
- [x] rewrite `docs/dev/pr_context.md` for PR-02 branch, scope, and exit gates
- [x] update `RELEASE_GATES.md` for the PR-02 contract-freeze gate
- [x] update `implementation_status.md` for PR-02 progress and deliverables
- [x] freeze lifecycle states and workflow artifact statuses in the canonical
      plan and HLD
- [x] freeze `SessionPreCallResult` and `AIGC.open_session(...)` as
      planned-only workflow contract surfaces
- [x] align `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` to the
      shipped `v0.3.3` invocation-only surface
- [x] extend doc parity checks for PR-02 contract drift
- [x] add lifecycle, public-surface, and protocol-boundary sentinel tests
- [x] verify targeted doc-parity and sentinel test coverage
