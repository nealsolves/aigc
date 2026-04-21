# Release Gates

This file tracks the release gates for the `v0.9.0` beta train.

Do NOT open or merge a PR from `origin/develop` -> `origin/main` until
`v0.9.0` is formally declared a GO.

PR-07 is the mandatory stop-ship checkpoint. If the golden path fails there,
no further public-surface work proceeds until the default path is repaired.

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

- [x] one canonical implementation plan is active
- [x] stale plan variants are marked superseded or historical
- [x] `CLAUDE.md`, `docs/dev/pr_context.md`, `implementation_status.md`, and this file share one PR/branch map
- [x] CI truth checks fail on release-packet drift

## PR-03 — Golden-Path Contract Freeze Gate

- [x] the beta CLI inventory is frozen as `aigc policy init`, `aigc workflow init`, `aigc workflow lint`, and `aigc workflow doctor`
- [x] scaffold profiles are frozen as `minimal`, `standard`, and `regulated-high-assurance`
- [x] starter coverage is frozen as local multi-step review, approval checkpoint, source required, and tool budget
- [x] public-import boundary rules are frozen across docs, starters, presets, and demo code
- [x] first-adopter docs order is frozen

## PR-06 — Doctor And Lint Gate

- [x] `aigc workflow lint` covers schema, transition references, unsupported bindings, budgets, starter integrity, and public-import safety
- [x] `aigc workflow doctor` covers policy, starter, workflow-artifact, and audit-artifact diagnosis
- [x] stable first-user reason codes and next actions exist for common failures

## PR-07 — Beta Proof Gate

- [x] clean-environment docs-to-working-app validation exists
- [x] minimal starter reaches `COMPLETED`
- [x] standard starter reaches `COMPLETED`
- [x] at least one intentional failure-and-fix path is validated end to end
- [x] the broken asset diagnosed by `workflow doctor` is the same generated starter that was broken and later rerun
- [x] demo failure diagnosis uses the real broken starter directory rather than synthetic backend fixtures
- [x] the default adopter path succeeds without Bedrock or A2A
- [x] no maintained public docs, demos, or starters import `aigc._internal`

## PR-08 — Engine Hardening Gate

- [x] restrictive composition rejects widening workflow merges
- [x] approvals, budgets, transitions, handoffs, participants, roles, and protocol constraints behave deterministically
- [x] validator hooks are wired internally through ordinary session creation and remain internal-only in the beta contract
- [x] workflow-step exceptions raised by public session methods are catchable through `aigc` and `aigc.errors`
- [x] failed Phase B attempts clean up session tokens deterministically

## PR-09 — Exports and Ops Gate

- [x] `aigc workflow trace` — timeline reconstruction from workflow and invocation artifacts
- [x] `aigc workflow export` — operator and audit export modes with checksum integrity reporting
- [x] operator-facing export portability and timeline reconstruction

## Deferred To PR-10 And Later

- [ ] optional Bedrock and A2A adapter tracks

---

## Beta Stop-Ship Gate

`v0.9.0` beta readiness is blocked until all of the following are true:

- [x] clean-environment docs-to-working-app success exists for the default path
- [x] quickstart completes within the `15` minute target budget
- [x] at least two public-import-only starter examples reach PASS
- [x] at least one failure-and-fix path is validated end to end
- [x] `workflow doctor` and `workflow lint` explain that failure clearly
- [x] no internal-code reading is required
- [x] no advanced manifest authoring is mandatory on the default path
- [x] workflow or invocation evidence visibility exists on the default path
- [x] the default adopter path succeeds without Bedrock or A2A

## `v0.9.0` Beta Release Gate

`v0.9.0` beta ships only if all of the following are true:

- [ ] PR-01 through PR-10 work is merged to `origin/develop`
- [x] the golden-path contract is frozen before later public-surface expansion
- [x] quickstart, starters, migration, diagnostics, beta proof, and engine hardening are test-backed on local `develop`
- [x] PR-09 operator polish lands
- [ ] optional adapter work lands
- [ ] `feat/v0.9-11-beta-freeze` lands
- [ ] `release/v0.9.0` is cut from the PR-11 result
- [ ] only then is the `origin/develop` -> `origin/main` PR opened
