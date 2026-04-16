# PR Context — `v0.9.0` PR-02 Contract Freeze

Date: 2026-04-15
Status: Draft
Active branch: `feat/v0.9-02-contract-freeze`

---

## Branch Sequence

One branch per PR. All remote merges during active `v0.9.0` work target
`origin/develop` only.

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
| PR-11 | `feat/v0.9-11-beta-freeze` -> `release/v0.9.0` | Freeze the beta and open the final release sequence only after all gates pass |

---

## PR Summary

This PR freezes the workflow contract for the `v0.9.0` beta before workflow
runtime implementation starts.

Theme:

- contract freeze and public-surface guardrails

PR type:

- docs, CI, and sentinel tests only

---

## Goal

Freeze session lifecycle, workflow artifact status mapping,
`SessionPreCallResult`, `AIGC.open_session(...)`, invocation-vs-workflow
evidence separation, and Bedrock/A2A fail-closed boundaries without adding
workflow runtime behavior in this PR.

---

## In Scope

- update the release packet for the PR-02 branch, scope, and exit criteria
- freeze workflow lifecycle and artifact-status rules in the canonical plan and
  HLD
- freeze `SessionPreCallResult` and `AIGC.open_session(...)` as planned-only
  workflow contract surfaces
- keep `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` aligned to the
  shipped `v0.3.3` invocation-only surface while naming workflow surfaces as
  planned-only
- extend CI truth checks for PR-02 contract drift
- add lifecycle, public-surface, and protocol-boundary sentinel tests

---

## Out of Scope

- workflow or session runtime implementation
- public export stubs or placeholder workflow classes
- workflow CLI behavior or new workflow CLI commands
- workflow schemas
- demo-app behavior changes
- Bedrock or A2A adapter runtime work
- package-version bumps
- `origin/develop` -> `origin/main` release promotion

---

## Binding Inputs

- `CLAUDE.md`
- `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md`
- `docs/decisions/ADR-0011-v090-beta-scope-sdk-boundary-and-non-goals.md`

---

## Contract Notes

- Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
  `v0.9.0` is formally declared a GO.
- PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
  no further public-surface work proceeds until the default path is repaired.
- The default adopter path must succeed without Bedrock or A2A.
- `CLAUDE.md` is binding for the seven demo rules, workflow lifecycle
  semantics, adapter fail-closed constraints, the PR table, and the
  `origin/main` freeze.
- `GovernanceSession`, `SessionPreCallResult`, and `AIGC.open_session(...)`
  remain planned-only contract surfaces in PR-02. No placeholder runtime
  exports ship in this branch.
- The frozen workflow entrypoint is `AIGC.open_session(...)`; there is no
  module-level `open_session(...)` public API in `v0.9.0`.
- PR-02 is docs, CI, and sentinel tests only. Workflow runtime implementation
  starts in PR-04.

---

## Reviewer Focus

- confirm the PR is docs, CI, and sentinel tests only
- confirm the canonical plan, HLD, `README.md`, and
  `docs/PUBLIC_INTEGRATION_CONTRACT.md` agree on lifecycle states, workflow
  artifact statuses, `SessionPreCallResult`, and `AIGC.open_session(...)`
- confirm the current public surface remains invocation-only
- confirm Bedrock and A2A boundary rules are frozen in tests without runtime
  adapters
- confirm there are no runtime, schema, CLI, demo, or package-version changes

---

## Exit Gate

- `docs/dev/pr_context.md`, `RELEASE_GATES.md`, and `implementation_status.md`
  are aligned to the PR-02 branch and scope
- the canonical plan and HLD freeze the workflow contract without adding
  runtime placeholders
- `README.md` and `docs/PUBLIC_INTEGRATION_CONTRACT.md` keep the shipped
  `v0.3.3` surface honest while naming workflow surfaces as planned-only
- doc truth checks fail closed on PR-02 contract drift
- public-surface sentinel tests prove no workflow runtime or CLI surface
  shipped early
- protocol-boundary tests prove Bedrock and A2A fail-closed contract rules
  stay frozen without adapter implementations
- no workflow runtime, schema, CLI, demo, or package changes land in PR-02
